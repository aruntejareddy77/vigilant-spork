"""
tests/test_attestation/test_startup_guard.py
Unit and CLI integration tests for startup attestation guard and fail-closed enforcement.
"""
import json
from pathlib import Path
import pytest
from click.testing import CliRunner

from sovereign.attestation.signer import generate_manifest, sign_manifest
from sovereign.attestation.verifier import AttestationError, AttestationGuard
from sovereign.audit.ledger import AuditLedger
from sovereign.cli import cli


def test_startup_guard_valid_manifest(temp_dir: Path):
    """Verify that AttestationGuard passes cleanly on uncorrupted assets in full and sparse modes."""
    f1 = temp_dir / "weights.bin"
    f1.write_bytes(b"WEIGHTS_ABC_123")
    f2 = temp_dir / "vocab.json"
    f2.write_text('{"tokens": 32000}', encoding="utf-8")

    manifest = generate_manifest(temp_dir, ["weights.bin", "vocab.json"])
    priv_pem = Path("tests/fixtures/test_ed25519_private.pem").read_bytes()
    pub_pem = Path("tests/fixtures/test_ed25519_public.pub").read_bytes()

    sig = sign_manifest(manifest, priv_pem)
    manifest_dict = manifest.model_dump()
    manifest_dict["signature"] = sig

    manifest_file = temp_dir / "attestation_manifest.json"
    manifest_file.write_text(json.dumps(manifest_dict), encoding="utf-8")

    guard = AttestationGuard(pub_pem)

    # 1. Warm sparse check
    res_sparse = guard.verify_manifest(manifest_file, root_dir=temp_dir, full_attest=False)
    assert res_sparse.is_valid is True
    assert res_sparse.mode == "sparse"
    assert res_sparse.files_checked == 2
    assert len(res_sparse.discrepancies) == 0

    # 2. Cold full byte check
    res_full = guard.verify_manifest(manifest_file, root_dir=temp_dir, full_attest=True)
    assert res_full.is_valid is True
    assert res_full.mode == "full"
    assert res_full.files_checked == 2


def test_startup_guard_fails_closed_on_tamper(temp_dir: Path):
    """Verify that AttestationGuard raises AttestationError by default on modified file."""
    f1 = temp_dir / "binary.exe"
    f1.write_bytes(b"SECURE_BINARY_ORIGINAL")

    manifest = generate_manifest(temp_dir, ["binary.exe"])
    priv_pem = Path("tests/fixtures/test_ed25519_private.pem").read_bytes()
    pub_pem = Path("tests/fixtures/test_ed25519_public.pub").read_bytes()

    sig = sign_manifest(manifest, priv_pem)
    manifest_dict = manifest.model_dump()
    manifest_dict["signature"] = sig
    manifest_file = temp_dir / "attestation_manifest.json"
    manifest_file.write_text(json.dumps(manifest_dict), encoding="utf-8")

    # Tamper with the binary
    f1.write_bytes(b"CORRUPTED_BINARY_INJECT")

    guard = AttestationGuard(pub_pem)

    with pytest.raises(AttestationError) as exc_info:
        guard.verify_manifest(manifest_file, root_dir=temp_dir, full_attest=True)

    assert "Startup attestation failed with" in str(exc_info.value)
    assert "binary.exe" in str(exc_info.value)


def test_startup_guard_dev_mode_bypass(temp_dir: Path):
    """Verify that --dev-mode prevents startup crash and logs an audit warning."""
    f1 = temp_dir / "model.bin"
    f1.write_bytes(b"ORIGINAL_MODEL_DATA")

    manifest = generate_manifest(temp_dir, ["model.bin"])
    priv_pem = Path("tests/fixtures/test_ed25519_private.pem").read_bytes()
    pub_pem = Path("tests/fixtures/test_ed25519_public.pub").read_bytes()

    manifest_dict = manifest.model_dump()
    manifest_dict["signature"] = sign_manifest(manifest, priv_pem)
    manifest_file = temp_dir / "attestation_manifest.json"
    manifest_file.write_text(json.dumps(manifest_dict), encoding="utf-8")

    # Delete the model file to simulate missing large model
    f1.unlink()

    ledger_path = temp_dir / "audit_ledger.jsonl"
    ledger = AuditLedger(ledger_path)
    guard = AttestationGuard(pub_pem)

    # In dev_mode, does NOT raise
    res = guard.verify_manifest(
        manifest_file,
        root_dir=temp_dir,
        dev_mode=True,
        audit_ledger=ledger,
    )
    assert res.is_valid is False
    assert len(res.discrepancies) == 1
    assert "Missing file: model.bin" in res.discrepancies[0]

    # Verify audit warning was logged
    with open(ledger_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    assert len(records) == 1
    assert records[0]["event_type"] == "ATTESTATION_WARNING_BYPASS"


def test_cli_attest_generate_sign_verify_workflow(temp_dir: Path):
    """Test full sovereign attest generate -> sign -> verify CLI lifecycle."""
    runner = CliRunner()

    f1 = temp_dir / "app.py"
    f1.write_text("print('sovereign')", encoding="utf-8")

    manifest_path = temp_dir / "manifest.json"
    priv_path = Path("tests/fixtures/test_ed25519_private.pem")
    pub_path = Path("tests/fixtures/test_ed25519_public.pub")

    # 1. Generate
    res_gen = runner.invoke(cli, ["attest", "generate", "--dir", str(temp_dir), "--output", str(manifest_path)])
    assert res_gen.exit_code == 0
    assert "[OK] Generated attestation manifest" in res_gen.output

    # 2. Sign
    res_sign = runner.invoke(cli, ["attest", "sign", "--manifest", str(manifest_path), "--key", str(priv_path)])
    assert res_sign.exit_code == 0
    assert "[OK] Successfully signed" in res_sign.output

    # 3. Verify
    res_verify = runner.invoke(
        cli,
        [
            "attest",
            "verify",
            "--manifest",
            str(manifest_path),
            "--key",
            str(pub_path),
            "--dir",
            str(temp_dir),
            "--full",
        ],
    )
    assert res_verify.exit_code == 0
    assert "[OK] Startup attestation PASSED." in res_verify.output
