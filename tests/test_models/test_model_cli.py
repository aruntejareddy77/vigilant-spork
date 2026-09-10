"""
tests/test_models/test_model_cli.py
Integration tests for sovereign model CLI commands (list, inspect, register).
"""
from pathlib import Path
from click.testing import CliRunner

from sovereign.cli import cli

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "models"


def test_cli_model_list():
    """Verify sovereign model list command output."""
    runner = CliRunner()
    res = runner.invoke(cli, ["model", "list", "--dir", str(FIXTURES_DIR)])
    assert res.exit_code == 0, res.output
    assert "Sovereign Model Catalog" in res.output
    assert "qwen-2.5-14b-instruct" in res.output
    assert "florence-2-large" in res.output
    assert "bge-large-en-v1.5" in res.output
    assert "sglang" in res.output
    assert "vllm" in res.output


def test_cli_model_inspect():
    """Verify sovereign model inspect command output."""
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["model", "inspect", "qwen-2.5-14b-instruct", "--dir", str(FIXTURES_DIR)],
    )
    assert res.exit_code == 0, res.output
    assert "Model Manifest: qwen-2.5-14b-instruct" in res.output
    assert '"model_id": "qwen-2.5-14b-instruct"' in res.output
    assert '"vram_estimate_mb": 10240' in res.output


def test_cli_model_inspect_missing():
    """Verify inspecting a non-existent model returns error."""
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["model", "inspect", "non-existent-model", "--dir", str(FIXTURES_DIR)],
    )
    assert res.exit_code == 1
    assert "not found in registry" in res.output


def test_cli_model_register_valid(tmp_path):
    """Verify registering a valid manifest file via CLI."""
    runner = CliRunner()
    manifest_file = FIXTURES_DIR / "mock_default.yaml"
    res = runner.invoke(cli, ["model", "register", str(manifest_file)])
    assert res.exit_code == 0, res.output
    assert "[OK] Successfully registered model 'mock-default-model'" in res.output
    assert "Engine       : mock" in res.output


def test_cli_model_register_missing_file():
    """Verify registering a non-existent file returns error."""
    runner = CliRunner()
    res = runner.invoke(cli, ["model", "register", "non_existent_manifest.yaml"])
    assert res.exit_code == 1
    assert "Manifest file not found" in res.output
