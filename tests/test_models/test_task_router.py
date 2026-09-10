"""
tests/test_models/test_task_router.py
Unit tests for TaskClassifier, TaskRouter, and audit log integration.
"""
import json
from pathlib import Path
import pytest

from sovereign.audit.ledger import AuditLedger
from sovereign.models.manifest import ModelCapability
from sovereign.models.registry import ModelRegistry
from sovereign.models.router import TaskClassifier, TaskRouter

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "models"


@pytest.fixture
def populated_registry() -> ModelRegistry:
    registry = ModelRegistry()
    registry.discover_models(FIXTURES_DIR)
    return registry


@pytest.fixture
def temp_audit_ledger(tmp_path) -> AuditLedger:
    ledger_path = tmp_path / "audit.jsonl"
    return AuditLedger(ledger_path)


def test_task_classifier_categories():
    """Verify deterministic classification rules."""
    # 1. Vision with image bytes
    assert TaskClassifier.classify("Analyze this", has_image=True) == ModelCapability.VISION_MULTIMODAL

    # 2. Vision text query
    assert TaskClassifier.classify("Check this P&ID drawing for valves") == ModelCapability.VISION_MULTIMODAL

    # 3. Code generation
    assert TaskClassifier.classify("Write a python script to parse historian data") == ModelCapability.CODE_GENERATION
    assert TaskClassifier.classify("def execute_calculation(x): return x * 2") == ModelCapability.CODE_GENERATION

    # 4. Engineering calculation
    assert TaskClassifier.classify("Calculate Reynolds number and pressure drop across orifice") == ModelCapability.CALCULATION
    assert TaskClassifier.classify("Apply ASME B31.3 formula for minimum thickness") == ModelCapability.CALCULATION

    # 5. Text drafting
    assert TaskClassifier.classify("Draft an approval note for unit turnaround") == ModelCapability.TEXT_DRAFTING
    assert TaskClassifier.classify("Prepare executive summary report") == ModelCapability.TEXT_DRAFTING

    # 6. Embeddings
    assert TaskClassifier.classify("Text to vectorize", is_embedding_batch=True) == ModelCapability.EMBEDDING

    # 7. General reasoning
    assert TaskClassifier.classify("What are the advantages of combined cycle turbines?") == ModelCapability.REASONING


def test_task_router_auto_selection(populated_registry):
    """Verify routing selects the best registered model matching capability."""
    router = TaskRouter(populated_registry)

    # Coding task -> qwen-2.5-coder-32b
    dec_code = router.route("Write a python script to parse log files")
    assert dec_code.model_id == "qwen-2.5-coder-32b"
    assert dec_code.capability == ModelCapability.CODE_GENERATION
    assert not dec_code.is_override

    # Vision task -> florence-2-large
    dec_vision = router.route("Find components in schematic", image_bytes=b"DUMMY_BYTES")
    assert dec_vision.model_id == "florence-2-large"
    assert dec_vision.capability == ModelCapability.VISION_MULTIMODAL

    # Drafting task -> qwen-2.5-14b-instruct
    dec_draft = router.route("Draft an approval note for equipment maintenance")
    assert dec_draft.model_id == "qwen-2.5-14b-instruct"
    assert dec_draft.capability == ModelCapability.TEXT_DRAFTING


def test_task_router_manual_override(populated_registry):
    """Verify manual override bypasses auto-classifier."""
    router = TaskRouter(populated_registry)

    # Even though prompt is code, override to 14b reasoning
    dec = router.route(
        "Write python code",
        model_override="qwen-2.5-14b-instruct",
    )
    assert dec.model_id == "qwen-2.5-14b-instruct"
    assert dec.is_override is True
    assert "Manual user override" in dec.rationale

    # Non-existent override raises KeyError
    with pytest.raises(KeyError):
        router.route("Write python code", model_override="non-existent-model")


def test_task_router_audit_logging(populated_registry, temp_audit_ledger):
    """Verify routing decisions are captured in the cryptographic audit ledger."""
    router = TaskRouter(populated_registry, audit_ledger=temp_audit_ledger)

    decision = router.route(
        prompt="Write a python script to calculate flow rate",
        session_id="session-route-test-101",
    )
    assert decision.model_id == "qwen-2.5-coder-32b"

    # Verify audit ledger record
    lines = [
        json.loads(line)
        for line in temp_audit_ledger.ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    ev = lines[0]
    assert ev["event_type"] == "MODEL_ROUTED"
    assert ev["session_id"] == "session-route-test-101"
    assert ev["actor_role"] == "task-router"
    assert ev["payload"]["selected_model_id"] == "qwen-2.5-coder-32b"
    assert ev["payload"]["classified_capability"] == "code_generation"
