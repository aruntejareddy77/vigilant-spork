"""
tests/test_models/test_mock_adapter.py
Unit tests for deterministic MockModelAdapter.
"""
import json
import math
from pathlib import Path
import pytest

from sovereign.models.adapters.mock import MockModelAdapter
from sovereign.models.manifest import load_manifest
from sovereign.models.types import ChatMessage

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "models"


@pytest.fixture
def mock_adapter() -> MockModelAdapter:
    manifest = load_manifest(FIXTURES_DIR / "mock_default.yaml")
    return MockModelAdapter(manifest)


def test_mock_adapter_lifecycle(mock_adapter):
    """Verify load, unload, memory footprint, and health check."""
    assert not mock_adapter.is_loaded
    assert mock_adapter.get_memory_footprint_mb() == 0
    assert mock_adapter.health_check() is True

    # Load
    assert mock_adapter.load() is True
    assert mock_adapter.is_loaded is True
    assert mock_adapter.get_memory_footprint_mb() == 1024

    # Unload
    assert mock_adapter.unload() is True
    assert mock_adapter.is_loaded is False
    assert mock_adapter.get_memory_footprint_mb() == 0


def test_mock_adapter_code_generation(mock_adapter):
    """Verify code prompt produces runnable python code."""
    res = mock_adapter.generate("Please write a python script to calculate pipe velocity")
    assert "def execute_engineering_calculation" in res.text
    assert "import math" in res.text
    assert res.finish_reason == "stop"
    assert res.usage["completion_tokens"] > 0
    assert res.latency_ms >= 0


def test_mock_adapter_json_generation(mock_adapter):
    """Verify json prompt produces valid parseable JSON."""
    res = mock_adapter.generate("Output the result as a json object conforming to schema")
    parsed = json.loads(res.text)
    assert parsed["status"] == "success"
    assert "parameters" in parsed
    assert "items" in parsed


def test_mock_adapter_calculation_and_inspection(mock_adapter):
    """Verify calculation trace and inspection report templates."""
    calc_res = mock_adapter.generate("Calculate the minimum wall thickness using ASME formula")
    assert "Engineering Calculation Trace" in calc_res.text
    assert "ASME B31.3" in calc_res.text

    insp_res = mock_adapter.generate("Draft an approval note for fractionator column inspection")
    assert "Plant Equipment Inspection & Approval Note" in insp_res.text
    assert "Visual Findings" in insp_res.text


def test_mock_adapter_chat(mock_adapter):
    """Verify multi-turn chat completions."""
    messages = [
        ChatMessage(role="system", content="You are a refinery assistant."),
        ChatMessage(role="user", content="Write a python script to calculate pipe fluid velocity"),
    ]
    res = mock_adapter.generate_chat(messages)
    assert "def execute_engineering_calculation" in res.text


def test_mock_adapter_embeddings(mock_adapter):
    """Verify deterministic vector embeddings and unit normalization."""
    texts = ["Refinery distillation column T-401", "Storage tank Tk-102 crude oil"]
    vecs = mock_adapter.embed(texts)

    assert len(vecs) == 2
    assert len(vecs[0]) == 768
    assert len(vecs[1]) == 768

    # Unit norm check: sum(x^2) ~ 1.0
    norm0 = math.sqrt(sum(x * x for x in vecs[0]))
    assert pytest.approx(norm0, rel=1e-3) == 1.0

    # Determinism: identical text yields identical vectors
    vecs_again = mock_adapter.embed(["Refinery distillation column T-401"])
    assert vecs[0] == vecs_again[0]

    # Distinct texts yield distinct vectors
    assert vecs[0] != vecs[1]


def test_mock_adapter_vision_infer(mock_adapter):
    """Verify simulated vision region extraction."""
    dummy_image = b"FAKE_JPEG_IMAGE_BYTES_FOR_TESTING"
    res = mock_adapter.vision_infer(dummy_image, "Locate all valves in this P&ID drawing")

    assert len(res.vision_regions) == 3
    labels = {r.label for r in res.vision_regions}
    assert "control_valve_CV102" in labels
    assert "centrifugal_feed_pump_P101" in labels
    for region in res.vision_regions:
        assert len(region.box_2d) == 4
        assert region.confidence >= 0.90
