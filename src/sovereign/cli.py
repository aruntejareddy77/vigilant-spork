"""
src/sovereign/cli.py
Unified CLI entry point for the Sovereign AI Workbench.
"""
import json
from pathlib import Path
import sys
import time
from typing import Optional
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


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Sovereign AI Workbench - Self-Hosted Air-Gapped Industrial Platform."""
    pass


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


if __name__ == "__main__":
    cli()
