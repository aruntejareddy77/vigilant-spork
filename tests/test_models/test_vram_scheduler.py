"""
tests/test_models/test_vram_scheduler.py
Unit tests for VRAMScheduler memory budgeting, LRU swapping, and audit trail events.
"""
import json
from pathlib import Path
import time
import pytest

from sovereign.audit.ledger import AuditLedger
from sovereign.models.manifest import (
    EngineConfig,
    EngineType,
    ModelCapability,
    ModelManifest,
    load_manifest,
)
from sovereign.models.registry import ModelRegistry
from sovereign.models.scheduler import VRAMExceededError, VRAMScheduler

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "models"


@pytest.fixture
def populated_registry() -> ModelRegistry:
    registry = ModelRegistry()
    registry.discover_models(FIXTURES_DIR)
    return registry


@pytest.fixture
def temp_audit_ledger(tmp_path) -> AuditLedger:
    ledger_path = tmp_path / "audit_vram.jsonl"
    return AuditLedger(ledger_path)


def test_vram_scheduler_budget_and_loading(populated_registry, temp_audit_ledger):
    """Verify normal loading within available VRAM budget."""
    scheduler = VRAMScheduler(
        registry=populated_registry,
        total_vram_mb=24576,
        reserve_headroom_mb=2048,
        audit_ledger=temp_audit_ledger,
    )
    assert scheduler.usable_vram_mb == 22528
    assert scheduler.current_allocated_mb == 0
    assert scheduler.available_vram_mb == 22528

    # Load Mock Model (1024 MB)
    a_mock = scheduler.ensure_loaded("mock-default-model")
    assert a_mock.is_loaded is True
    assert scheduler.is_loaded("mock-default-model") is True
    assert scheduler.current_allocated_mb == 1024
    assert scheduler.available_vram_mb == 22528 - 1024

    # Calling ensure_loaded again on already loaded model returns cached instance without reloading
    a_mock_again = scheduler.ensure_loaded("mock-default-model")
    assert a_mock is a_mock_again
    assert scheduler.current_allocated_mb == 1024


def test_vram_scheduler_lru_eviction(temp_audit_ledger):
    """Verify LRU model eviction when memory budget threshold is exceeded."""
    registry = ModelRegistry()

    def add_mock_manifest(model_id: str, vram_mb: int) -> ModelManifest:
        m = ModelManifest(
            model_id=model_id,
            name=f"Model {model_id}",
            family="test",
            capabilities=[ModelCapability.REASONING],
            context_window=4096,
            vram_estimate_mb=vram_mb,
            engine=EngineConfig(type=EngineType.MOCK),
        )
        registry.register_manifest(m)
        return m

    # Register 3 models: A (8000MB), B (4000MB), C (5000MB)
    add_mock_manifest("model-a", 8000)
    add_mock_manifest("model-b", 4000)
    add_mock_manifest("model-c", 5000)

    # Setup scheduler with usable budget = 12,000 MB (14,000 total - 2,000 reserve)
    scheduler = VRAMScheduler(
        registry=registry,
        total_vram_mb=14000,
        reserve_headroom_mb=2000,
        audit_ledger=temp_audit_ledger,
    )
    assert scheduler.usable_vram_mb == 12000

    # 1. Load Model A (8000 MB)
    scheduler.ensure_loaded("model-a")
    time.sleep(0.01)

    # 2. Load Model B (4000 MB) -> Total 12000 MB (100% capacity)
    scheduler.ensure_loaded("model-b")
    time.sleep(0.01)
    assert scheduler.current_allocated_mb == 12000
    assert scheduler.is_loaded("model-a") is True
    assert scheduler.is_loaded("model-b") is True

    # 3. Load Model C (5000 MB) -> Exceeds budget; Model A is oldest -> Evict Model A
    scheduler.ensure_loaded("model-c")
    assert scheduler.is_loaded("model-a") is False
    assert scheduler.is_loaded("model-b") is True
    assert scheduler.is_loaded("model-c") is True
    assert scheduler.current_allocated_mb == 4000 + 5000  # 9000 MB

    # Verify audit events: MODEL_UNLOADED and MODEL_SWAPPED
    lines = [
        json.loads(line)
        for line in temp_audit_ledger.ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    event_types = [e["event_type"] for e in lines]
    assert "MODEL_LOADED" in event_types
    assert "MODEL_UNLOADED" in event_types
    assert "MODEL_SWAPPED" in event_types


def test_vram_scheduler_exceeds_total_budget():
    """Verify VRAMExceededError is raised when single model exceeds usable budget."""
    registry = ModelRegistry()
    m = ModelManifest(
        model_id="monster-model-70b",
        name="Monster Model 70B",
        family="giant",
        capabilities=[ModelCapability.REASONING],
        context_window=4096,
        vram_estimate_mb=40000,  # 40GB
        engine=EngineConfig(type=EngineType.MOCK),
    )
    registry.register_manifest(m)

    scheduler = VRAMScheduler(
        registry=registry,
        total_vram_mb=24576,
        reserve_headroom_mb=2048,
    )

    with pytest.raises(VRAMExceededError) as exc_info:
        scheduler.ensure_loaded("monster-model-70b")
    assert "exceeds the total usable VRAM budget" in str(exc_info.value)
