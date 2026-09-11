"""
tests/test_deliverables/test_code_artifact_export.py
Unit tests for CodeArtifactExporter bundling runnable scripts, execution logs,
sample fixtures, lineage sidecars, and reproducibility verification.
"""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from sovereign.deliverables.code_export import CodeArtifactExporter
from sovereign.lineage.models import (
    DeliverableInfo,
    LineageMetadata,
    ModelInfo,
)
from sovereign.tools.builtin.files import PathSecurityViolation


def test_export_reproducible_bundle_complete(tmp_path):
    """Test exporting runnable .py, .log, fixture, and .lineage.json sidecar."""
    output_dir = tmp_path / "output_bundle"
    output_dir.mkdir()

    # Create a dummy sample fixture
    fixture_path = tmp_path / "sample_telemetry.csv"
    fixture_path.write_text("timestamp,pressure,temp\n0,2.5,150\n10,2.6,152\n", encoding="utf-8")

    # Script code that reads the fixture and computes average pressure
    script_code = (
        "import csv\n"
        "from pathlib import Path\n\n"
        "fixture = Path('sample_telemetry.csv')\n"
        "if fixture.exists():\n"
        "    with open(fixture) as f:\n"
        "        rows = list(csv.DictReader(f))\n"
        "    pressures = [float(r['pressure']) for r in rows]\n"
        "    avg_p = sum(pressures) / len(pressures)\n"
        "    print(f'AVERAGE_PRESSURE={avg_p:.2f}')\n"
        "else:\n"
        "    print('AVERAGE_PRESSURE=DEFAULT')\n"
    )

    execution_log = (
        "[INFO] Initializing sensor simulation sandbox...\n"
        "[EXEC] python calc_pressure.py\n"
        "[STDOUT] AVERAGE_PRESSURE=2.55\n"
        "[INFO] Exit Code: 0 | Duration: 42ms\n"
    )

    meta = LineageMetadata(
        deliverable=DeliverableInfo(file_name="calc_pressure.py"),
        session_id="session-code-1234",
        user_id="code_engineer",
        user_role="Lead Systems Engineer",
        model=ModelInfo(model_id="qwen-2.5-coder-32b", weights_sha256="aabbccddeeff0011"),
        audit_start_seq=5,
        audit_end_seq=10,
        audit_tip_hash="11223344556677889900aabbccddeeff",
    )

    bundle = CodeArtifactExporter.export_reproducible_bundle(
        output_dir=output_dir,
        script_name="calc_pressure.py",
        script_code=script_code,
        execution_log=execution_log,
        sample_input_path=fixture_path,
        lineage_metadata=meta,
    )

    assert "script" in bundle
    assert "log" in bundle
    assert "sidecar" in bundle
    assert "input" in bundle

    script_p = bundle["script"]
    log_p = bundle["log"]
    sidecar_p = bundle["sidecar"]
    input_p = bundle["input"]

    assert script_p.exists()
    assert log_p.exists()
    assert sidecar_p.exists()
    assert input_p.exists()

    # Verify script content has sovereign provenance header
    code_text = script_p.read_text(encoding="utf-8")
    assert "Sovereign AI Workbench - Reproducible Code Artifact" in code_text
    assert "session-code-1234" in code_text
    assert "qwen-2.5-coder-32b" in code_text

    # Verify log content
    assert "AVERAGE_PRESSURE=2.55" in log_p.read_text(encoding="utf-8")

    # Verify sidecar metadata
    sidecar_data = json.loads(sidecar_p.read_text(encoding="utf-8"))
    assert sidecar_data["session_id"] == "session-code-1234"
    assert sidecar_data["deliverable"]["file_sha256"] != ""

    # Test Reproducibility: Execute the exported script in output_dir
    res = subprocess.run(
        [sys.executable, str(script_p)],
        cwd=output_dir,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "AVERAGE_PRESSURE=2.55" in res.stdout


def test_export_code_path_fencing(tmp_path):
    """Verify that attempting to export outside allowed root raises PathSecurityViolation."""
    allowed_root = tmp_path / "allowed_root"
    allowed_root.mkdir()
    forbidden_dir = tmp_path / "forbidden_dir"

    with pytest.raises(PathSecurityViolation):
        CodeArtifactExporter.export_reproducible_bundle(
            output_dir=forbidden_dir,
            script_name="malicious.py",
            script_code="print('evil')",
            execution_log="fail",
            allowed_root=allowed_root,
        )

    with pytest.raises(PathSecurityViolation):
        CodeArtifactExporter.export_reproducible_bundle(
            output_dir=str(allowed_root / "dir\x00"),
            script_name="null.py",
            script_code="print('null')",
            execution_log="null",
            allowed_root=allowed_root,
        )
