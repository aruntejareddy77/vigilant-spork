"""
src/sovereign/cli.py
Unified CLI entry point for the Sovereign AI Workbench.
"""
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request
import click

from sovereign.audit.canonical import GENESIS_PREVIOUS_HASH
from sovereign.audit.ledger import AuditLedger
from sovereign.audit.mirror import AuditMirror
from sovereign.audit.verifier import verify_ledger
from sovereign.config.settings import DEFAULT_POLICY_PATH
from sovereign.network.monitor import NetworkMonitor
from sovereign.network.policy import NetworkPolicyEngine
from sovereign.network.ring_buffer import ConnectionRingBuffer
from sovereign.network.test_egress import run_egress_probes
from sovereign.server.config import BindingSecurityError, validate_server_binding


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Sovereign AI Workbench - Self-Hosted Air-Gapped Industrial Platform."""
    pass


def _send_api_request(
    endpoint: str,
    method: str = "GET",
    server_url: str = "http://127.0.0.1:8000",
    payload: Optional[Dict[str, Any]] = None,
    role: Optional[str] = None,
    token: Optional[str] = None,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """Send an authenticated HTTP request to the Sovereign Workbench API."""
    url = f"{server_url.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Sovereign-CLI/0.1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif role:
        headers["X-Sovereign-Role"] = role.lower()

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")
            return json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as exc:
        err_msg = exc.reason
        try:
            err_body = exc.read().decode("utf-8")
            err_json = json.loads(err_body)
            err_msg = err_json.get("detail", err_body)
        except Exception:
            pass
        click.echo(f"[ERROR] API request failed ({exc.code}): {err_msg}", err=True)
        sys.exit(1)
    except urllib.error.URLError as exc:
        click.echo(f"[ERROR] Connection failed to {server_url}: {exc.reason}", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"[ERROR] Unexpected request error: {exc}", err=True)
        sys.exit(1)


# ==========================================
# Sovereign Audit Commands
# ==========================================

@cli.group()
def audit():
    """Manage and verify cryptographic audit ledgers."""
    pass


@audit.command("verify")
@click.argument("ledger_path", default="audit_ledger.jsonl", type=click.Path(dir_okay=False))
def audit_verify(ledger_path: str):
    """
    Traverse and verify the cryptographic integrity of the audit ledger.
    Pinpoints tampered records or broken hash chains.
    """
    path = Path(ledger_path)
    if not path.exists():
        click.echo(f"[ERROR] Ledger file not found: {path}", err=True)
        sys.exit(1)

    result = verify_ledger(path)
    if result.is_valid:
        click.echo(
            f"[OK] Audit ledger integrity verified.\n"
            f"     Records checked : {result.records_checked}\n"
            f"     Tip hash        : {result.tip_hash}"
        )
        sys.exit(0)
    else:
        click.echo(
            f"[FAIL] Cryptographic audit chain TAMPER detected!\n"
            f"       Error Sequence : {result.error_seq}\n"
            f"       Diagnostic     : {result.error_message}",
            err=True,
        )
        sys.exit(1)


@audit.command("inspect")
@click.argument("ledger_path", default="audit_ledger.jsonl", type=click.Path(dir_okay=False))
def audit_inspect(ledger_path: str):
    """
    Display statistics, record counts, and session information for an audit ledger.
    """
    path = Path(ledger_path)
    if not path.exists():
        click.echo(f"[ERROR] Ledger file not found: {path}", err=True)
        sys.exit(1)

    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                try:
                    records.append(json.loads(line_str))
                except json.JSONDecodeError:
                    pass

    total_records = len(records)
    if total_records == 0:
        click.echo(f"Ledger file: {path} (Empty, 0 records)")
        sys.exit(0)

    sessions = set(r.get("session_id") for r in records if "session_id" in r)
    first_time = records[0].get("timestamp_iso", "N/A")
    last_time = records[-1].get("timestamp_iso", "N/A")
    genesis_prev = records[0].get("previous_hash", GENESIS_PREVIOUS_HASH)
    tip_hash = records[-1].get("entry_hash", "N/A")

    click.echo("=== Sovereign Audit Ledger Inspection ===")
    click.echo(f"File Path        : {path.resolve()}")
    click.echo(f"Total Records    : {total_records}")
    click.echo(f"Unique Sessions  : {len(sessions)}")
    click.echo(f"First Timestamp  : {first_time}")
    click.echo(f"Last Timestamp   : {last_time}")
    click.echo(f"Genesis PrevHash : {genesis_prev}")
    click.echo(f"Tip Hash         : {tip_hash}")
    click.echo("=========================================")
    sys.exit(0)


@audit.command("export")
@click.option("--session-id", required=True, help="Session identifier to isolate and export.")
@click.option("--ledger-path", default="audit_ledger.jsonl", type=click.Path(dir_okay=False), help="Path to JSONL ledger.")
@click.option("--db-path", default=None, type=click.Path(dir_okay=False), help="Path to SQLite mirror (optional).")
@click.option("--output", default=None, type=click.Path(dir_okay=False), help="Output destination file.")
@click.option("--format", "fmt", type=click.Choice(["json", "jsonl"], case_sensitive=False), default="jsonl", help="Export format.")
def audit_export(session_id: str, ledger_path: str, db_path: Optional[str], output: Optional[str], fmt: str):
    """
    Extract a standalone audit slice for a specific session_id.
    """
    events_data = []

    if db_path and Path(db_path).exists():
        mirror = AuditMirror(db_path)
        slice_events = mirror.export_session_slice(session_id)
        events_data = [e.model_dump() for e in slice_events]
    else:
        l_path = Path(ledger_path)
        if not l_path.exists():
            click.echo(f"[ERROR] Ledger file not found: {l_path}", err=True)
            sys.exit(1)

        with open(l_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    try:
                        rec = json.loads(line_str)
                        if rec.get("session_id") == session_id:
                            events_data.append(rec)
                    except json.JSONDecodeError:
                        pass

    if fmt == "json":
        formatted_output = json.dumps(events_data, indent=2, ensure_ascii=False)
    else:
        formatted_output = "\n".join(json.dumps(r, ensure_ascii=False) for r in events_data)

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(formatted_output + ("\n" if fmt == "jsonl" and formatted_output else ""))
        click.echo(f"[OK] Exported {len(events_data)} events for session '{session_id}' to {output}")
    else:
        click.echo(formatted_output)

    sys.exit(0)


# ==========================================
# Sovereign Network Commands
# ==========================================

@cli.group()
def network():
    """Inspect network policies, socket telemetry, and isolation boundaries."""
    pass


@network.command("status")
@click.option("--policy-path", default=str(DEFAULT_POLICY_PATH), type=click.Path(dir_okay=False))
def network_status(policy_path: str):
    """
    Display current network isolation policy, allowed CIDRs, and active rules.
    """
    path = Path(policy_path)
    if not path.exists():
        click.echo(f"[ERROR] Policy file not found: {path}", err=True)
        sys.exit(1)

    engine = NetworkPolicyEngine(path)
    click.echo("=== Sovereign Network Isolation Policy ===")
    click.echo(f"Policy Name          : {engine.policy_name}")
    click.echo(f"Policy File          : {path.resolve()}")
    click.echo(f"Default Action       : {engine.default_action}")
    click.echo(f"Denied Ports         : {engine.denied_ports}")
    click.echo(f"Allowed Loopback     : {[str(c) for c in engine.allowed_loopback]}")
    click.echo(f"Allowed Intranet CIDR: {[str(c) for c in engine.allowed_intranet]}")
    click.echo("==========================================")
    sys.exit(0)


@network.command("monitor")
@click.option("--policy-path", default=str(DEFAULT_POLICY_PATH), type=click.Path(dir_okay=False))
@click.option("--interval", default=0.5, type=float, help="Polling interval in seconds.")
def network_monitor(policy_path: str, interval: float):
    """
    Run the live socket telemetry watcher, streaming connection events to stdout.
    """
    engine = NetworkPolicyEngine(policy_path)
    ring_buffer = ConnectionRingBuffer(capacity=500)

    def on_event(event):
        status_tag = f"[{event.verdict}]"
        click.echo(
            f"{event.timestamp_iso} {status_tag:<8} {event.protocol.upper():<4} "
            f"pid={event.pid or 0:<6} {event.process_name:<18} "
            f"{event.local_address} -> {event.remote_address or 'listening'} ({event.reason})"
        )

    monitor = NetworkMonitor(
        policy_engine=engine,
        ring_buffer=ring_buffer,
        poll_interval=interval,
        event_callback=on_event,
    )

    click.echo("Starting Sovereign Socket Telemetry Monitor (Ctrl+C to terminate)...")
    monitor.start()
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        click.echo("\nStopping network monitor...")
        monitor.stop()
        sys.exit(0)


# ==========================================
# Sovereign Synthetic Egress Testing
# ==========================================

@cli.command("test-egress")
@click.option("--timeout", default=1.0, type=float, help="Per-probe socket connection timeout in seconds.")
@click.option("--policy-path", default=str(DEFAULT_POLICY_PATH), type=click.Path(dir_okay=False))
@click.option("--ledger-path", default="audit_ledger.jsonl", type=click.Path(dir_okay=False))
def test_egress(timeout: float, policy_path: str, ledger_path: str):
    """
    Execute synthetic egress probes across DNS, HTTP, HTTPS, NTP, and raw sockets.
    Validates that 100% of outbound connections are blocked.
    """
    p_path = Path(policy_path)
    engine = NetworkPolicyEngine(p_path) if p_path.exists() else None

    l_path = Path(ledger_path)
    ledger = AuditLedger(l_path) if l_path.exists() else None

    click.echo("=== Sovereign Synthetic Egress Probe Suite ===")
    click.echo(f"Probing external network egress (timeout={timeout:.1f}s)...")

    results = run_egress_probes(policy_engine=engine, audit_ledger=ledger, timeout=timeout)

    all_blocked = True
    click.echo("\n" + "-" * 78)
    click.echo(f"{'Protocol':<12} | {'Target Destination':<22} | {'Latency':<9} | {'Verdict':<8} | Reason")
    click.echo("-" * 78)

    for r in results:
        dest = f"{r.target_host}:{r.target_port}"
        verdict = r.outcome
        latency_str = f"{r.latency_ms:.1f}ms"
        click.echo(f"{r.protocol:<12} | {dest:<22} | {latency_str:<9} | {verdict:<8} | {r.reason}")
        if r.outcome != "BLOCKED":
            all_blocked = False

    click.echo("-" * 78)

    if all_blocked:
        click.echo("\n[SECURE] 100% of outbound synthetic connections blocked.")
        click.echo("         Zero external network egress empirically verified.")
        sys.exit(0)
    else:
        click.echo("\n[SECURITY ALERT] Unpermitted outbound connection succeeded!", err=True)
        click.echo("                 The environment has network egress leaks.", err=True)
        sys.exit(1)


# ==========================================
# Sovereign Startup Attestation Commands
# ==========================================

@cli.group()
def attest():
    """Generate, sign, and verify cryptographic asset attestation manifests."""
    pass


@attest.command("generate")
@click.option("--dir", "root_dir", default=".", type=click.Path(file_okay=False), help="Root directory containing assets.")
@click.option("--output", default="attestation_manifest.json", type=click.Path(dir_okay=False), help="Output manifest path.")
@click.option("--files", default=None, help="Comma-separated relative file paths to catalog.")
def attest_generate(root_dir: str, output: str, files: Optional[str]):
    """
    Generate an unsigned attestation manifest calculating full SHA-256 and 64MB sparse chunk hashes.
    """
    from sovereign.attestation.signer import generate_manifest

    r_dir = Path(root_dir).resolve()
    if files:
        file_list = [f.strip() for f in files.split(",") if f.strip()]
    else:
        # Index files in root directory
        file_list = [
            p.relative_to(r_dir).as_posix()
            for p in r_dir.rglob("*")
            if p.is_file() and not p.name.endswith(".json") and not p.name.endswith(".pyc")
        ]

    manifest = generate_manifest(r_dir, file_list)
    out_path = Path(output)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest.model_dump(), f, indent=2, ensure_ascii=False)

    click.echo(f"[OK] Generated attestation manifest with {len(manifest.entries)} entries at {out_path}")
    sys.exit(0)


@attest.command("sign")
@click.option("--manifest", required=True, type=click.Path(dir_okay=False), help="Path to attestation_manifest.json.")
@click.option("--key", "key_path", required=True, type=click.Path(dir_okay=False), help="Path to Ed25519 private key PEM.")
def attest_sign(manifest: str, key_path: str):
    """
    Sign an attestation manifest with an Ed25519 private key.
    """
    from sovereign.attestation.signer import sign_manifest

    m_path = Path(manifest)
    k_path = Path(key_path)

    if not m_path.exists():
        click.echo(f"[ERROR] Manifest file not found: {m_path}", err=True)
        sys.exit(1)
    if not k_path.exists():
        click.echo(f"[ERROR] Private key file not found: {k_path}", err=True)
        sys.exit(1)

    with open(m_path, "r", encoding="utf-8") as f:
        manifest_dict = json.load(f)
    with open(k_path, "rb") as f:
        priv_key_pem = f.read()

    sig = sign_manifest(manifest_dict, priv_key_pem)
    manifest_dict["signature"] = sig

    with open(m_path, "w", encoding="utf-8") as f:
        json.dump(manifest_dict, f, indent=2, ensure_ascii=False)

    click.echo(f"[OK] Successfully signed {m_path} with Ed25519 signature.")
    click.echo(f"     Signature: {sig[:32]}...{sig[-16:]}")
    sys.exit(0)


@attest.command("verify")
@click.option("--manifest", default="attestation_manifest.json", type=click.Path(dir_okay=False))
@click.option("--key", "key_path", required=True, type=click.Path(dir_okay=False), help="Path to Ed25519 public key.")
@click.option("--dir", "root_dir", default=None, type=click.Path(file_okay=False), help="Base directory for cataloged assets.")
@click.option("--full", "full_attest", is_flag=True, default=False, help="Perform full byte-by-byte SHA-256 verification.")
@click.option("--dev-mode", is_flag=True, default=False, help="Bypass fail-closed halt on discrepancies.")
def attest_verify(manifest: str, key_path: str, root_dir: Optional[str], full_attest: bool, dev_mode: bool):
    """
    Verify attestation manifest signature and validate asset checksums.
    """
    from sovereign.attestation.verifier import AttestationError, AttestationGuard

    m_path = Path(manifest)
    k_path = Path(key_path)

    if not m_path.exists():
        click.echo(f"[ERROR] Manifest not found: {m_path}", err=True)
        sys.exit(1)
    if not k_path.exists():
        click.echo(f"[ERROR] Public key not found: {k_path}", err=True)
        sys.exit(1)

    with open(k_path, "rb") as f:
        pub_key_pem = f.read()

    guard = AttestationGuard(pub_key_pem)
    try:
        res = guard.verify_manifest(
            manifest_path=m_path,
            root_dir=root_dir,
            full_attest=full_attest,
            dev_mode=dev_mode,
        )
    except AttestationError as exc:
        click.echo(f"[FAIL] Attestation verification failed:\n{exc}", err=True)
        sys.exit(1)

    if res.is_valid:
        click.echo(
            f"[OK] Startup attestation PASSED.\n"
            f"     Mode           : {res.mode}\n"
            f"     Files verified : {res.files_checked}\n"
            f"     Duration       : {res.duration_ms:.1f}ms"
        )
        sys.exit(0)
    else:
        click.echo(f"[WARNING] Attestation discrepancies detected ({len(res.discrepancies)}) with --dev-mode:")
        for d in res.discrepancies:
            click.echo(f"  - {d}")
        sys.exit(0)


# ==========================================
# Sovereign Deliverable Lineage Commands
# ==========================================

@cli.group()
def lineage():
    """Verify cryptographic lineage and trace forward provenance of deliverables."""
    pass


@lineage.command("verify")
@click.argument("deliverable", type=click.Path(dir_okay=False))
@click.option("--ledger", "ledger_path", default=None, type=click.Path(dir_okay=False), help="Path to audit ledger for sequence span verification.")
def lineage_verify(deliverable: str, ledger_path: Optional[str]):
    """
    Verify deliverable integrity, sidecar manifest, embedded metadata, and audit ledger span.
    """
    from sovereign.lineage.verifier import LineageVerifier

    result = LineageVerifier.verify_lineage(deliverable, ledger_path=ledger_path)

    click.echo("=== Sovereign Deliverable Lineage Verification ===")
    click.echo(f"Deliverable File     : {result.deliverable_path}")
    click.echo(f"Computed SHA-256     : {result.file_sha256_computed or 'N/A'}")
    click.echo(f"Recorded SHA-256     : {result.file_sha256_recorded or 'N/A'}")
    click.echo(f"Sidecar Exists       : {'PASS' if result.sidecar_exists else 'FAIL'}")
    click.echo(f"File Hash Integrity  : {'PASS' if result.file_hash_valid else 'FAIL'}")
    if result.embedded_metadata_found:
        click.echo(f"Embedded Metadata    : {'PASS' if result.embedded_metadata_valid else 'FAIL'}")
    else:
        click.echo(f"Embedded Metadata    : N/A (clean or non-embedded format)")

    if "span" in result.details:
        click.echo(f"Audit Ledger Span    : {'PASS' if result.audit_span_valid else 'FAIL'} ({result.details['span']})")
    else:
        click.echo(f"Audit Ledger Span    : SKIPPED (ledger not provided/found)")

    if result.is_valid:
        click.echo("[OK] Lineage verification PASSED. Deliverable is authentic and uncorrupted.")
        sys.exit(0)
    else:
        click.echo(f"[FAIL] Lineage verification FAILED: {result.error_message}", err=True)
        sys.exit(1)


@lineage.command("trace")
@click.argument("query", type=str)
@click.option("--dir", "search_dir", default=".", type=click.Path(file_okay=False), help="Root directory to search for .lineage.json sidecars.")
def lineage_trace(query: str, search_dir: str):
    """
    Trace forward provenance: locate all deliverables derived from a source file or SHA-256 hash.
    """
    from sovereign.lineage.verifier import LineageVerifier

    results = LineageVerifier.trace_provenance(query=query, search_dir=search_dir)

    click.echo("=== Sovereign Provenance Forward Trace ===")
    click.echo(f"Query Target         : {query}")
    click.echo(f"Search Directory     : {Path(search_dir).resolve()}")
    click.echo(f"Matching Deliverables: {len(results)}")
    click.echo("------------------------------------------")

    if not results:
        click.echo("No matching deliverables found.")
        sys.exit(0)

    for i, res in enumerate(results, start=1):
        click.echo(f"[{i}] Deliverable: {res.deliverable_path}")
        click.echo(f"    Match Type : {res.match_type} ({res.matched_id})")
        click.echo(f"    Deliverable SHA-256: {res.deliverable_sha256[:16]}...")
        click.echo(f"    Session ID : {res.session_id}")
        click.echo(f"    Generated  : {res.generated_iso}")
        click.echo(f"    Sidecar    : {res.sidecar_path}")

    sys.exit(0)


# ==========================================
# Sovereign Model Management Commands
# ==========================================

@cli.group()
def model():
    """Inspect registered models, view capabilities, and register new manifests."""
    pass


@model.command("list")
@click.option("--dir", "models_dir", default="models", type=click.Path(file_okay=False), help="Directory to discover model manifests.")
def model_list(models_dir: str):
    """
    List all available registered models, engine types, and capabilities.
    """
    from sovereign.models.registry import ModelRegistry

    registry = ModelRegistry()
    d_path = Path(models_dir)
    if d_path.exists():
        registry.discover_models(d_path)

    manifests = registry.list_manifests()
    click.echo("=== Sovereign Model Catalog ===")
    click.echo(f"Models Directory     : {d_path.resolve() if d_path.exists() else 'Directory not found'}")
    click.echo(f"Total Models Found   : {len(manifests)}")
    click.echo("--------------------------------------------------------------------------------")

    if not manifests:
        click.echo("No model manifests found.")
        sys.exit(0)

    click.echo(f"{'MODEL ID':<26} {'ENGINE':<10} {'QUANT':<8} {'VRAM(MB)':<10} {'CAPABILITIES'}")
    click.echo("-" * 80)
    for m in sorted(manifests, key=lambda x: x.model_id):
        caps = ",".join(c.value for c in m.capabilities)
        click.echo(
            f"{m.model_id:<26} {m.engine.type.value:<10} {m.quantization or 'None':<8} "
            f"{m.vram_estimate_mb:<10} {caps}"
        )
    sys.exit(0)


@model.command("inspect")
@click.argument("model_id", type=str)
@click.option("--dir", "models_dir", default="models", type=click.Path(file_okay=False), help="Directory containing model manifests.")
def model_inspect(model_id: str, models_dir: str):
    """
    Display full configuration and integrity details for a model manifest.
    """
    from sovereign.models.registry import ModelRegistry

    registry = ModelRegistry()
    d_path = Path(models_dir)
    if d_path.exists():
        registry.discover_models(d_path)

    manifest = registry.get_manifest(model_id)
    if not manifest:
        click.echo(f"[ERROR] Model '{model_id}' not found in registry ({models_dir}).", err=True)
        sys.exit(1)

    click.echo(f"=== Model Manifest: {manifest.model_id} ===")
    click.echo(manifest.model_dump_json(indent=2))
    sys.exit(0)


@model.command("register")
@click.argument("manifest_path", type=click.Path(dir_okay=False))
def model_register(manifest_path: str):
    """
    Validate and register a new model manifest file into the workbench.
    """
    from sovereign.models.registry import ModelRegistry

    p = Path(manifest_path)
    if not p.exists():
        click.echo(f"[ERROR] Manifest file not found: {p}", err=True)
        sys.exit(1)

    registry = ModelRegistry()
    try:
        manifest = registry.register_from_file(p)
    except Exception as e:
        click.echo(f"[FAIL] Manifest validation failed: {e}", err=True)
        sys.exit(1)

    click.echo(f"[OK] Successfully registered model '{manifest.model_id}' ({manifest.name}).")
    click.echo(f"     Engine       : {manifest.engine.type.value}")
    click.echo(f"     Capabilities : {[c.value for c in manifest.capabilities]}")
    click.echo(f"     VRAM Estimate: {manifest.vram_estimate_mb} MB")
    sys.exit(0)


@model.command("route")
@click.argument("prompt", type=str)
@click.option("--dir", "models_dir", default="models", type=click.Path(file_okay=False), help="Directory containing model manifests.")
@click.option("--image", "image_path", default=None, type=click.Path(dir_okay=False), help="Path to image file for multimodal testing.")
@click.option("--model", "model_override", default=None, type=str, help="Explicit model ID override.")
def model_route(prompt: str, models_dir: str, image_path: Optional[str], model_override: Optional[str]):
    """
    Test task auto-routing: classify prompt and display selected model and VRAM requirement.
    """
    from sovereign.models.registry import ModelRegistry
    from sovereign.models.router import TaskRouter

    registry = ModelRegistry()
    d_path = Path(models_dir)
    if d_path.exists():
        registry.discover_models(d_path)

    if not registry.list_manifests():
        click.echo(f"[ERROR] No models registered in '{models_dir}'.", err=True)
        sys.exit(1)

    image_bytes = None
    if image_path:
        img_p = Path(image_path)
        if not img_p.exists():
            click.echo(f"[ERROR] Image file not found: {img_p}", err=True)
            sys.exit(1)
        image_bytes = img_p.read_bytes()

    router = TaskRouter(registry)
    try:
        decision = router.route(
            prompt=prompt,
            image_bytes=image_bytes,
            model_override=model_override,
        )
    except Exception as e:
        click.echo(f"[FAIL] Routing failed: {e}", err=True)
        sys.exit(1)

    click.echo("=== Sovereign Task Routing Decision ===")
    click.echo(f"Prompt               : {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    click.echo(f"Classified Capability: {decision.capability.value}")
    click.echo(f"Selected Model ID    : {decision.model_id}")
    click.echo(f"VRAM Estimate        : {decision.vram_estimate_mb} MB")
    click.echo(f"Manual Override      : {'Yes' if decision.is_override else 'No'}")
    click.echo(f"Routing Rationale    : {decision.rationale}")
    sys.exit(0)


@model.command("vram")
@click.option("--server-url", default=None, help="Workbench server URL to query live metrics.")
@click.option("--dir", "models_dir", default="models", type=click.Path(file_okay=False), help="Directory containing model manifests.")
@click.option("--total-vram", default=24576, type=int, help="Total GPU VRAM budget in MB.")
@click.option("--reserve", default=2048, type=int, help="Safety reserve headroom in MB.")
def model_vram(server_url: Optional[str], models_dir: str, total_vram: int, reserve: int):
    """
    Display GPU VRAM memory budget, active allocations, safety reserve, and headroom.
    """
    total_mb = total_vram
    reserve_mb = reserve
    usable_mb = max(0, total_vram - reserve)
    allocated_mb = 0
    available_mb = usable_mb
    loaded_models: List[Any] = []

    if server_url:
        try:
            data = _send_api_request("/api/models/vram", method="GET", server_url=server_url)
            total_mb = data.get("total_mb", total_mb)
            usable_mb = data.get("usable_mb", usable_mb)
            allocated_mb = data.get("allocated_mb", allocated_mb)
            available_mb = data.get("available_mb", available_mb)
            loaded_models = data.get("loaded_models", [])
            reserve_mb = max(0, total_mb - usable_mb)
        except SystemExit:
            raise
        except Exception:
            pass
    else:
        try:
            from sovereign.models.registry import ModelRegistry
            from sovereign.models.scheduler import VRAMScheduler

            registry = ModelRegistry()
            d_path = Path(models_dir)
            if d_path.exists():
                registry.discover_models(d_path)
            scheduler = VRAMScheduler(
                registry=registry,
                total_vram_mb=total_vram,
                reserve_headroom_mb=reserve,
            )
            total_mb = scheduler.total_vram_mb
            reserve_mb = scheduler.reserve_headroom_mb
            usable_mb = scheduler.usable_vram_mb
            allocated_mb = scheduler.current_allocated_mb
            available_mb = scheduler.available_vram_mb
            loaded_models = scheduler.list_loaded_models()
        except Exception:
            pass

    used_pct = (allocated_mb / usable_mb * 100.0) if usable_mb > 0 else 0.0
    bar_len = 20
    filled = int(bar_len * (allocated_mb / usable_mb)) if usable_mb > 0 else 0
    filled = min(bar_len, max(0, filled))
    bar = "=" * filled + "-" * (bar_len - filled)

    click.echo("=== Sovereign GPU VRAM Budget & Allocation ===")
    click.echo(f"Total Budget       : {total_mb:>6,d} MB ({total_mb / 1024:.1f} GB)")
    click.echo(f"Safety Reserve     : {reserve_mb:>6,d} MB ({reserve_mb / 1024:.1f} GB)")
    click.echo(f"Usable Envelope    : {usable_mb:>6,d} MB ({usable_mb / 1024:.1f} GB)")
    click.echo(f"Active Allocation  : {allocated_mb:>6,d} MB ({allocated_mb / 1024:.1f} GB)")
    click.echo(f"Allocated MB       : {allocated_mb:>6,d} MB")
    click.echo(f"Available Headroom : {available_mb:>6,d} MB ({available_mb / 1024:.1f} GB)")
    click.echo(f"Memory Envelope    : [{bar}] {used_pct:.1f}% used")
    click.echo("----------------------------------------------")
    click.echo(f"Loaded Models ({len(loaded_models)}):")
    if not loaded_models:
        click.echo("  No models currently loaded in VRAM.")
    else:
        for m in loaded_models:
            m_id = m.get("model_id", m) if isinstance(m, dict) else str(m)
            vram = m.get("vram_mb", "N/A") if isinstance(m, dict) else ""
            vram_str = f" ({vram} MB)" if vram else ""
            click.echo(f"  • {m_id}{vram_str}")
    click.echo("==============================================")
    sys.exit(0)


# ==========================================
# Sovereign Tool Commands
# ==========================================

@cli.group()
def tool():
    """Inspect and manage registered agent tools and schemas."""
    pass


@tool.command("list")
@click.option("--role", "role_filter", default=None, type=click.Choice(["admin", "engineer", "auditor"], case_sensitive=False), help="Filter by user role clearance.")
@click.option("--workspace", default=".", type=click.Path(), help="Workspace root directory.")
def tool_list(role_filter: Optional[str], workspace: str):
    """
    List all registered tools, their descriptions, and required role clearances.
    """
    from sovereign.tools.schemas import UserRole
    from sovereign.tools.registry import ToolRegistry
    from sovereign.tools.builtin import register_builtin_tools

    registry = ToolRegistry()
    register_builtin_tools(registry, workspace)

    role = UserRole(role_filter.lower()) if role_filter else None
    tools = registry.list_tools(user_role=role)

    click.echo(f"=== Registered Sovereign Tools ({len(tools)}) ===")
    if not tools:
        click.echo("No tools available for the specified clearance level.")
        sys.exit(0)

    for t in tools:
        click.echo(f"  • {t.name:<22} [{t.required_role.value.upper():<8}] - {t.description}")
    sys.exit(0)


@tool.command("inspect")
@click.argument("tool_name", type=str)
@click.option("--workspace", default=".", type=click.Path(), help="Workspace root directory.")
def tool_inspect(tool_name: str, workspace: str):
    """
    Display the detailed JSON parameter schema and metadata for a tool.
    """
    from sovereign.tools.registry import ToolRegistry
    from sovereign.tools.builtin import register_builtin_tools

    registry = ToolRegistry()
    register_builtin_tools(registry, workspace)

    tool_def = registry.get_tool(tool_name)
    if not tool_def:
        click.echo(f"[ERROR] Tool '{tool_name}' not found.", err=True)
        sys.exit(1)

    click.echo(f"Tool Name    : {tool_def.name}")
    click.echo(f"Required Role: {tool_def.required_role.value.upper()}")
    click.echo(f"Description  : {tool_def.description}")
    click.echo("Parameters Schema:")
    click.echo(json.dumps(tool_def.parameters_schema, indent=2))
    sys.exit(0)


# ==========================================
# Sovereign Workflow Commands
# ==========================================

@cli.group()
def workflow():
    """Execute and manage stateful agentic workflows."""
    pass


def _build_workflow_runtime(workspace_root: str, db_path: str, ledger_path: Optional[str] = None):
    """Internal factory building standard agent workflow runtime."""
    import uuid
    from sovereign.orchestration.state import GraphState
    from sovereign.orchestration.graph import StateGraph, END
    from sovereign.orchestration.checkpointer import SQLiteCheckpointer
    from sovereign.orchestration.runtime import AgentRuntime, interrupt
    from sovereign.audit.ledger import AuditLedger
    from sovereign.tools.registry import ToolRegistry
    from sovereign.tools.builtin import register_builtin_tools

    registry = ToolRegistry()
    register_builtin_tools(registry, workspace_root)
    checkpointer = SQLiteCheckpointer(db_path)
    ledger = AuditLedger(ledger_path) if ledger_path else None

    builder = StateGraph()

    def analyze_step(state: GraphState):
        prompt = state.values.get("prompt", "")
        is_calc = any(kw in prompt.lower() for kw in ("calc", "calculate", "+", "*", "sqrt", "math"))
        return {"values": {"is_calc": is_calc, "plan": f"Plan for: {prompt}"}}

    def execute_step(state: GraphState):
        prompt = state.values.get("prompt", "")
        if state.values.get("is_calc"):
            expr = prompt.lower().replace("calculate", "").replace("calc", "").strip()
            if not expr:
                expr = "2 + 2"
            try:
                res = registry.execute_tool("execute_calculation", {"expression": expr})
                return {"values": {"output": f"Calculation Result: {res['result']}", "trace": res.get("trace", "")}}
            except Exception as e:
                return {"values": {"output": f"Calculation Error: {e}"}, "last_error": str(e)}
        else:
            return {"values": {"output": f"Task processed: {prompt}"}}

    def review_step(state: GraphState):
        prompt = state.values.get("prompt", "")
        if any(kw in prompt.lower() for kw in ("report", "deliverable", "deploy", "release", "approve")):
            interrupt({
                "action": "deliverable_signoff",
                "prompt": prompt,
                "summary": state.values.get("output", "Analysis ready"),
            })
        return {"values": {"approved": True}}

    def finalize_step(state: GraphState):
        return {"values": {"completed": True}}

    builder.add_node("analyze", analyze_step)
    builder.add_node("execute", execute_step)
    builder.add_node("review", review_step)
    builder.add_node("finalize", finalize_step)

    builder.set_entry_point("analyze")
    builder.add_edge("analyze", "execute")
    builder.add_edge("execute", "review")
    builder.add_edge("review", "finalize")
    builder.add_edge("finalize", END)

    return AgentRuntime(builder, checkpointer=checkpointer, audit_ledger=ledger)


@workflow.command("run")
@click.argument("prompt", type=str)
@click.option("--thread-id", "thread_id", default=None, help="Explicit thread session ID.")
@click.option("--db", "db_path", default="agent_state.sqlite", help="SQLite state database.")
@click.option("--ledger", "ledger_path", default=None, help="Audit ledger path.")
@click.option("--workspace", default=".", help="Workspace directory for file/tool operations.")
def workflow_run(prompt: str, thread_id: Optional[str], db_path: str, ledger_path: Optional[str], workspace: str):
    """
    Launch a multi-step agent workflow for the given prompt.
    """
    import uuid
    from sovereign.orchestration.state import GraphState

    runtime = _build_workflow_runtime(workspace, db_path, ledger_path)
    tid = thread_id or f"wf-{uuid.uuid4().hex[:8]}"

    click.echo(f"=== Running Sovereign Workflow ===")
    click.echo(f"Thread ID : {tid}")
    click.echo(f"Prompt    : {prompt}")

    initial_state = GraphState(thread_id=tid, values={"prompt": prompt})
    final_state = runtime.run(initial_state)

    click.echo(f"Status    : {final_state.status}")
    click.echo(f"Steps     : {final_state.step_count}")

    if final_state.status == "SUSPENDED":
        click.echo("\n[PAUSED] Workflow paused at Human-in-the-Loop approval gate.")
        click.echo(f"Pending Action : {final_state.pending_approval}")
        click.echo(f"To resume, run: sovereign workflow resume {tid} --decision approve")
        sys.exit(0)
    elif final_state.status == "COMPLETED":
        click.echo(f"Output    : {final_state.values.get('output', 'Workflow completed successfully')}")
        sys.exit(0)
    else:
        click.echo(f"[FAILED] Error: {final_state.last_error}", err=True)
        sys.exit(1)


@workflow.command("resume")
@click.argument("thread_id", type=str)
@click.option("--decision", required=True, type=click.Choice(["approve", "reject"], case_sensitive=False), help="Decision: approve or reject")
@click.option("--notes", default=None, help="Operator notes or reasoning.")
@click.option("--role", "actor_role", default="operator", help="Role of the approving operator.")
@click.option("--db", "db_path", default="agent_state.sqlite", help="SQLite state database.")
@click.option("--ledger", "ledger_path", default=None, help="Audit ledger path.")
@click.option("--workspace", default=".", help="Workspace directory.")
def workflow_resume(thread_id: str, decision: str, notes: Optional[str], actor_role: str, db_path: str, ledger_path: Optional[str], workspace: str):
    """
    Resume an interrupted/suspended workflow upon operator approval or rejection.
    """
    runtime = _build_workflow_runtime(workspace, db_path, ledger_path)

    try:
        resumed_state = runtime.resume(
            thread_id=thread_id,
            decision=decision,
            notes=notes,
            actor_role=actor_role,
        )
    except Exception as exc:
        click.echo(f"[ERROR] Failed to resume workflow: {exc}", err=True)
        sys.exit(1)

    click.echo(f"=== Resumed Workflow: {thread_id} ===")
    click.echo(f"Decision  : {decision.upper()}")
    click.echo(f"Status    : {resumed_state.status}")
    if resumed_state.status == "COMPLETED":
        click.echo(f"Output    : {resumed_state.values.get('output', 'Workflow completed')}")
        sys.exit(0)
    elif resumed_state.status == "FAILED":
        click.echo(f"Outcome   : Rejected / Halted ({resumed_state.last_error})")
        sys.exit(0)
    else:
        click.echo(f"Status    : {resumed_state.status}")
        sys.exit(0)


@workflow.command("list")
@click.option("--status", default=None, type=click.Choice(["RUNNING", "SUSPENDED", "COMPLETED", "FAILED"], case_sensitive=False), help="Filter threads by status.")
@click.option("--db", "db_path", default="agent_state.sqlite", help="SQLite state database.")
def workflow_list(status: Optional[str], db_path: str):
    """
    List tracked workflow session threads and their status.
    """
    from sovereign.orchestration.checkpointer import SQLiteCheckpointer

    cp_path = Path(db_path)
    if not cp_path.exists():
        click.echo(f"No state database found at '{db_path}'. 0 threads tracked.")
        sys.exit(0)

    with SQLiteCheckpointer(cp_path) as cp:
        threads = cp.list_threads(status=status.upper() if status else None)

    click.echo(f"=== Sovereign Workflow Threads ({len(threads)}) ===")
    if not threads:
        click.echo("No threads found.")
        sys.exit(0)

    for t in threads:
        click.echo(f"  • {t['thread_id']:<20} [{t['status']:<9}] Updated: {t['updated_iso']}")
    sys.exit(0)


# ==========================================
# Sovereign Server Management
# ==========================================

@cli.command("serve")
@click.option("--host", default="127.0.0.1", help="Binding host interface.")
@click.option("--port", default=8000, type=int, help="Server port.")
@click.option("--workers", default=1, type=int, help="Uvicorn workers.")
@click.option("--reload", is_flag=True, help="Enable auto-reload.")
def serve_command(host: str, port: int, workers: int, reload: bool):
    """
    Launch the Sovereign Workbench FastAPI server and static UI.
    Fails closed on 0.0.0.0, ::, or unauthorized public IPs per UI-02.
    """
    try:
        validate_server_binding(host)
    except BindingSecurityError as exc:
        click.echo(f"[ERROR] Security Binding Violation: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Starting Sovereign Workbench server on http://{host}:{port} (workers={workers})...")
    import uvicorn
    uvicorn.run(
        "sovereign.server.app:create_app",
        host=host,
        port=port,
        factory=True,
        workers=workers,
        reload=reload,
    )


# ==========================================
# Sovereign Task Operations
# ==========================================

@cli.group()
def task():
    """Submit, monitor, inspect, and approve stateful agent tasks."""
    pass


@task.command("submit")
@click.argument("prompt", type=str)
@click.option("--file", "files", multiple=True, type=click.Path(), help="Input file(s) for task processing.")
@click.option("--role", default="engineer", type=click.Choice(["admin", "engineer", "auditor"], case_sensitive=False), help="User role clearance.")
@click.option("--token", default=None, help="Bearer authorization token.")
@click.option("--model", default=None, help="Explicit model ID override.")
@click.option("--stream", is_flag=True, help="Stream agent reasoning trace and steps to stdout.")
@click.option("--server-url", default="http://127.0.0.1:8000", help="Workbench server base URL.")
def task_submit(prompt: str, files: tuple, role: str, token: Optional[str], model: Optional[str], stream: bool, server_url: str):
    """
    Submit a task to the Sovereign Agentic Runtime.
    Restricts Auditor role per least-privilege policy (UI-05).
    """
    if role.lower() == "auditor":
        click.echo(
            "[ERROR] Auditor role is restricted from submitting tasks per least-privilege policy (UI-05)",
            err=True,
        )
        sys.exit(1)

    payload = {
        "prompt": prompt,
        "files": list(files) if files else [],
        "model_override": model,
    }

    res = _send_api_request(
        endpoint="/api/tasks",
        method="POST",
        server_url=server_url,
        payload=payload,
        role=role,
        token=token,
    )

    task_id = res.get("task_id", "N/A")
    thread_id = res.get("thread_id", "N/A")
    status = res.get("status", "SUBMITTED")

    click.echo(f"[OK] Task submitted successfully.")
    click.echo(f"     Task ID   : {task_id}")
    click.echo(f"     Thread ID : {thread_id}")
    click.echo(f"     Status    : {status}")

    if stream:
        click.echo(f"Streaming execution trace for {task_id}...")
        seen_steps = 0
        max_polls = 60
        for _ in range(max_polls):
            time.sleep(0.5)
            status_data = _send_api_request(
                endpoint=f"/api/tasks/{task_id}",
                method="GET",
                server_url=server_url,
                role=role,
                token=token,
            )
            steps = status_data.get("steps", [])
            while seen_steps < len(steps):
                step = steps[seen_steps]
                node = step.get("node_name", "agent")
                thought = step.get("thought", "")
                step_st = step.get("status", "")
                click.echo(f"[{node}] {thought or step_st}")
                seen_steps += 1
            if status_data.get("status") in ("COMPLETED", "FAILED", "SUSPENDED", "REJECTED"):
                click.echo(f"Task finished with status: {status_data.get('status')}")
                break


@task.command("status")
@click.argument("task_id", type=str)
@click.option("--server-url", default="http://127.0.0.1:8000", help="Workbench server base URL.")
@click.option("--token", default=None, help="Bearer authorization token.")
@click.option("--role", default="engineer", help="User role.")
def task_status(task_id: str, server_url: str, token: Optional[str], role: str):
    """
    Fetch and display task execution status, steps, and pending HITL approval.
    """
    data = _send_api_request(
        endpoint=f"/api/tasks/{task_id}",
        method="GET",
        server_url=server_url,
        role=role,
        token=token,
    )

    status = data.get("status", "UNKNOWN")
    steps = data.get("steps", [])
    pending_approval = data.get("pending_approval")
    artifacts = data.get("artifacts", [])

    click.echo(f"=== Sovereign Task Status: {task_id} ===")
    click.echo(f"Status           : {status}")
    click.echo(f"Completed Steps  : {len(steps)}")
    click.echo(f"Pending Approval : {pending_approval if pending_approval else 'None'}")
    click.echo(f"Artifacts        : {', '.join(artifacts) if artifacts else 'None'}")

    if pending_approval:
        click.echo("\n[ATTENTION] Task is paused at Human-in-the-Loop approval gate.")
        click.echo(f"Action Details   : {pending_approval}")
        click.echo(f"To approve: sovereign task approve {task_id}")
        click.echo(f"To reject : sovereign task reject {task_id}")


@task.command("logs")
@click.argument("task_id", type=str)
@click.option("--follow", is_flag=True, help="Follow logs until completion.")
@click.option("--server-url", default="http://127.0.0.1:8000", help="Workbench server base URL.")
@click.option("--token", default=None, help="Bearer authorization token.")
@click.option("--role", default="engineer", help="User role.")
def task_logs(task_id: str, follow: bool, server_url: str, token: Optional[str], role: str):
    """
    Display execution trace logs for a task.
    """
    seen_steps = 0
    while True:
        data = _send_api_request(
            endpoint=f"/api/tasks/{task_id}",
            method="GET",
            server_url=server_url,
            role=role,
            token=token,
        )
        steps = data.get("steps", [])
        if seen_steps == 0:
            click.echo(f"=== Execution Trace: {task_id} (Status: {data.get('status')}) ===")
        while seen_steps < len(steps):
            step = steps[seen_steps]
            idx = step.get("step_index", seen_steps + 1)
            node = step.get("node_name", "unknown")
            st = step.get("status", "COMPLETED")
            elapsed = step.get("elapsed_ms", 0.0)
            thought = step.get("thought", "")
            click.echo(f"[{idx}] {node} [{st}] ({elapsed:.1f}ms): {thought}")
            seen_steps += 1

        if not follow or data.get("status") in ("COMPLETED", "FAILED", "SUSPENDED", "REJECTED"):
            break
        time.sleep(1.0)


@task.command("approve")
@click.argument("task_id", type=str)
@click.option("--notes", default=None, help="Operator review notes.")
@click.option("--role", default="engineer", type=click.Choice(["admin", "engineer", "auditor"], case_sensitive=False), help="User role.")
@click.option("--token", default=None, help="Bearer authorization token.")
@click.option("--server-url", default="http://127.0.0.1:8000", help="Workbench server base URL.")
def task_approve(task_id: str, notes: Optional[str], role: str, token: Optional[str], server_url: str):
    """
    Approve a suspended task deliverable and resume workflow execution.
    Restricts Auditor role per least-privilege policy (UI-05).
    """
    if role.lower() == "auditor":
        click.echo(
            "[ERROR] Auditor role is restricted from approving tasks per least-privilege policy (UI-05)",
            err=True,
        )
        sys.exit(1)

    payload = {
        "decision": "approve",
        "notes": notes or "Operator approved via CLI",
    }
    res = _send_api_request(
        endpoint=f"/api/tasks/{task_id}/resume",
        method="POST",
        server_url=server_url,
        payload=payload,
        role=role,
        token=token,
    )
    click.echo(f"=== Resumed Task: {task_id} ===")
    click.echo(f"Decision  : APPROVE")
    click.echo(f"Status    : {res.get('status', 'RESUMED')}")


@task.command("reject")
@click.argument("task_id", type=str)
@click.option("--reason", default=None, help="Rejection rationale.")
@click.option("--role", default="engineer", type=click.Choice(["admin", "engineer", "auditor"], case_sensitive=False), help="User role.")
@click.option("--token", default=None, help="Bearer authorization token.")
@click.option("--server-url", default="http://127.0.0.1:8000", help="Workbench server base URL.")
def task_reject(task_id: str, reason: Optional[str], role: str, token: Optional[str], server_url: str):
    """
    Reject a suspended task deliverable and halt workflow execution.
    Restricts Auditor role per least-privilege policy (UI-05).
    """
    if role.lower() == "auditor":
        click.echo(
            "[ERROR] Auditor role is restricted from rejecting tasks per least-privilege policy (UI-05)",
            err=True,
        )
        sys.exit(1)

    payload = {
        "decision": "reject",
        "notes": reason or "Operator rejected via CLI",
    }
    res = _send_api_request(
        endpoint=f"/api/tasks/{task_id}/resume",
        method="POST",
        server_url=server_url,
        payload=payload,
        role=role,
        token=token,
    )
    click.echo(f"=== Resumed Task: {task_id} ===")
    click.echo(f"Decision  : REJECT")
    click.echo(f"Status    : {res.get('status', 'REJECTED')}")


if __name__ == "__main__":
    cli()
