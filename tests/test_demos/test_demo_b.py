"""
tests/test_demos/test_demo_b.py
End-to-End Automated Integration Test Suite for Demo Workflow B (Industrial Code & Sandbox / DEMO-02).
Tests industrial sensor telemetry ingestion, AST network security isolation,
seeded KeyError execution failure in CodeSandbox, bounded self-correction loop (Attempt 1 of 3),
verified execution with peak vibration detection, and runnable code artifact bundle export.
"""
import csv
from pathlib import Path
import pytest

from sovereign.deliverables.code_export import CodeArtifactExporter
from sovereign.sandbox.executor import (
    CodeSandbox,
    SandboxSecurityViolation,
    validate_script_safety,
)


def test_demo_b_sandbox_network_isolation():
    """
    Validates static AST security filtering (validate_script_safety):
    - Blocks network imports (socket, urllib, requests, http) per ASVS V5.1 and Threat T-06-02.
    - Allows standard library mathematical and engineering modules.
    """
    malicious_scripts = [
        "import socket\ns = socket.socket()",
        "import requests\nr = requests.get('http://127.0.0.1')",
        "import urllib.request\nurllib.request.urlopen('http://localhost')",
        "from http import client\nconn = client.HTTPConnection('localhost')",
        "import aiohttp\n",
        "import httpx\n",
    ]

    for script in malicious_scripts:
        with pytest.raises(SandboxSecurityViolation, match="Network import prohibited"):
            validate_script_safety(script)

    # Valid industrial script should pass AST validation cleanly
    benign_script = """
import csv
import math
import statistics
import sys

def compute_fft():
    return math.sqrt(2.0)
"""
    validate_script_safety(benign_script)


def test_demo_b_flawed_execution_and_auto_fix(samples_dir: Path, tmp_path: Path):
    """
    Validates Demo B self-correction loop in isolated CodeSandbox:
    1. Ingests samples/historian_sensor_telemetry.csv (10,000 rows).
    2. Executes script with seeded KeyError ('vibration_rms').
    3. Verifies failure: exit_code != 0, KeyError in stderr.
    4. Simulates reflection node self-correction: patches column to 'vib_rms_g'.
    5. Re-executes patched script: exit_code == 0, detects peak vibration > 5.0g and anomaly window.
    """
    csv_path = samples_dir / "historian_sensor_telemetry.csv"
    assert csv_path.exists(), f"Sample CSV missing at {csv_path}"

    csv_content = csv_path.read_text(encoding="utf-8")

    # Initial script with intentional defect: accesses non-existent column 'vibration_rms'
    flawed_script = """
import csv
import sys

def run_vibration_analysis():
    anomalies = []
    max_vib = 0.0
    record_count = 0

    with open("historian_sensor_telemetry.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=1):
            record_count += 1
            # Flawed column key: 'vibration_rms' instead of 'vib_rms_g'
            vib = float(row["vibration_rms"])
            if vib > max_vib:
                max_vib = vib
            if vib > 2.8:
                anomalies.append((row_num, row["timestamp"], vib, float(row["bearing_temp_c"])))

    print(f"[INFO] Analyzed {record_count} telemetry records.")
    print(f"[ALERT] ANOMALY detected: {len(anomalies)} out-of-range readings. Peak vibration: {max_vib:.2f}g")

if __name__ == "__main__":
    run_vibration_analysis()
"""

    sandbox = CodeSandbox(timeout_seconds=15.0, base_scratch_dir=tmp_path / "scratch")

    # Attempt 1: Execute flawed code in sandbox
    res1 = sandbox.execute(
        code=flawed_script,
        input_files={"historian_sensor_telemetry.csv": csv_content},
        session_id="session-demo-b-test",
    )

    assert res1.exit_code != 0, f"Expected initial failure, got exit code {res1.exit_code}"
    assert "KeyError" in res1.stderr
    assert "vibration_rms" in res1.stderr

    # Bounded Self-Correction Loop (Attempt 1 of 3)
    retry_count = 0
    max_retries = 3

    # Inspect headers from CSV content to emulate agent reflection
    header_line = csv_content.splitlines()[0]
    available_columns = [col.strip() for col in header_line.split(",")]
    assert "vib_rms_g" in available_columns

    # Agent reflection patches column name
    patched_script = flawed_script.replace('row["vibration_rms"]', 'row["vib_rms_g"]')
    retry_count += 1
    assert retry_count <= max_retries

    # Attempt 2: Re-execute patched code in sandbox
    res2 = sandbox.execute(
        code=patched_script,
        input_files={"historian_sensor_telemetry.csv": csv_content},
        session_id="session-demo-b-test",
    )

    assert res2.exit_code == 0, f"Expected exit code 0 on patched execution, got {res2.exit_code}. Stderr: {res2.stderr}"
    assert "ANOMALY detected" in res2.stdout
    assert "Analyzed 10000 telemetry records" in res2.stdout
    assert "Peak vibration: 5." in res2.stdout  # Peak vibration reached > 5.0g


def test_demo_b_code_bundle_export(samples_dir: Path, tmp_path: Path):
    """
    Validates deliverable export via CodeArtifactExporter:
    - Generates vibration_analysis.py with sovereign provenance header.
    - Generates vibration_analysis.log with exit code 0 and stdout trace.
    - Copies sample historian CSV into output directory.
    - Emits W3C PROV-O .lineage.json sidecar manifest.
    """
    csv_path = samples_dir / "historian_sensor_telemetry.csv"
    out_dir = tmp_path / "output"

    verified_code = """
import csv

def run_analysis():
    with open("historian_sensor_telemetry.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = sum(1 for _ in reader)
    print(f"Verified {count} telemetry records.")

if __name__ == "__main__":
    run_analysis()
"""
    log_output = (
        "[EXECUTION LOG]\n"
        "Session ID: session-demo-b-export\n"
        "Exit Code : 0\n"
        "Duration  : 0.128s\n"
        "Stdout:\n"
        "Verified 10000 telemetry records.\n"
        "Stderr:\n"
    )

    bundle = CodeArtifactExporter.export_reproducible_bundle(
        output_dir=out_dir,
        script_name="vibration_analysis.py",
        script_code=verified_code,
        execution_log=log_output,
        sample_input_path=csv_path,
        allowed_root=tmp_path,
    )

    # Validate bundle dictionary
    assert "script" in bundle
    assert "log" in bundle
    assert "sidecar" in bundle
    assert "input" in bundle

    # Validate physical files exist on disk
    assert bundle["script"].exists()
    assert bundle["log"].exists()
    assert bundle["sidecar"].exists()
    assert bundle["input"].exists()

    # Validate script content and provenance header
    script_text = bundle["script"].read_text(encoding="utf-8")
    assert "Sovereign AI Workbench - Reproducible Code Artifact" in script_text
    assert "vibration_analysis.py" in script_text
    assert "def run_analysis():" in script_text

    # Validate execution log
    log_text = bundle["log"].read_text(encoding="utf-8")
    assert "Exit Code : 0" in log_text
    assert "Verified 10000 telemetry records." in log_text

    # Validate copied sample input fixture
    copied_csv = bundle["input"].read_text(encoding="utf-8")
    assert "timestamp,machine_id,vib_rms_g" in copied_csv

    # Validate lineage sidecar
    sidecar_text = bundle["sidecar"].read_text(encoding="utf-8")
    assert "vibration_analysis.py" in sidecar_text
    assert "sovereign-code-v1" in sidecar_text
