"""
Global Pytest Fixtures for Sovereign AI Workbench
Provides temporary directories, isolated ledger environments, and sample audit data.
"""
import shutil
import tempfile
from pathlib import Path
from typing import Generator
import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provides an isolated temporary directory cleaned up after each test."""
    path = Path(tempfile.mkdtemp(prefix="sovereign_test_"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def sample_payload() -> dict:
    """Provides a representative audit event payload."""
    return {
        "action": "model_inference",
        "model_name": "qwen2.5-coder-7b",
        "input_tokens": 128,
        "output_tokens": 64,
        "temperature": 0.2,
        "tags": ["security", "audit", "air-gap"],
        "metadata": {
            "prompt_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "execution_time_ms": 45.2,
        },
    }
