"""
tests/test_demos/conftest.py
Shared test fixtures for SIH demonstration workflow integration test suites.
"""
from pathlib import Path
import pytest


@pytest.fixture(scope="session")
def samples_dir() -> Path:
    """Returns the resolved root path to deterministic demo sample assets."""
    samples_path = Path(__file__).resolve().parent.parent.parent / "samples"
    samples_path.mkdir(parents=True, exist_ok=True)
    return samples_path


@pytest.fixture
def deliverable_output_dir(tmp_path: Path) -> Path:
    """Returns an isolated temporary directory for deliverable outputs."""
    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
