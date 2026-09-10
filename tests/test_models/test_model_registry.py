"""
tests/test_models/test_model_registry.py
Unit tests for ModelRegistry catalog, capability filtering, and dynamic discovery.
"""
from pathlib import Path
import pytest

from sovereign.models.manifest import ModelCapability, load_manifest
from sovereign.models.registry import ModelRegistry

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "models"


def test_registry_registration_and_retrieval():
    """Verify registration and lookup by model_id."""
    registry = ModelRegistry()
    assert len(registry.list_manifests()) == 0

    manifest = load_manifest(FIXTURES_DIR / "qwen_reasoning.yaml")
    registry.register_manifest(manifest)

    assert len(registry.list_manifests()) == 1
    retrieved = registry.get_manifest("qwen-2.5-14b-instruct")
    assert retrieved is not None
    assert retrieved.name == "Qwen 2.5 14B Instruct"
    assert retrieved.family == "qwen"

    # Non-existent returns None
    assert registry.get_manifest("non-existent") is None


def test_registry_capability_filtering():
    """Verify filtering models by capability."""
    registry = ModelRegistry()
    registry.register_from_file(FIXTURES_DIR / "qwen_reasoning.yaml")
    registry.register_from_file(FIXTURES_DIR / "qwen_coder.yaml")
    registry.register_from_file(FIXTURES_DIR / "florence_vision.yaml")
    registry.register_from_file(FIXTURES_DIR / "bge_embedding.yaml")

    # Coding models
    coder_models = registry.find_by_capability(ModelCapability.CODE_GENERATION)
    assert len(coder_models) == 1
    assert coder_models[0].model_id == "qwen-2.5-coder-32b"

    # Vision models
    vision_models = registry.find_by_capability(ModelCapability.VISION_MULTIMODAL)
    assert len(vision_models) == 1
    assert vision_models[0].model_id == "florence-2-large"

    # Reasoning models (both reasoning and coder declare reasoning)
    reasoning_models = registry.find_by_capability(ModelCapability.REASONING)
    assert len(reasoning_models) == 2
    ids = {m.model_id for m in reasoning_models}
    assert "qwen-2.5-14b-instruct" in ids
    assert "qwen-2.5-coder-32b" in ids


def test_registry_discover_models():
    """Verify recursive directory discovery."""
    registry = ModelRegistry()
    count = registry.discover_models(FIXTURES_DIR)
    assert count >= 5
    assert registry.get_manifest("mock-default-model") is not None
    assert registry.get_manifest("bge-large-en-v1.5") is not None


def test_registry_hot_registration_without_restart(tmp_path):
    """Verify runtime hot-adding of a new model manifest."""
    registry = ModelRegistry()
    registry.register_from_file(FIXTURES_DIR / "mock_default.yaml")
    assert len(registry.list_manifests()) == 1

    # Dynamically create new manifest file during runtime
    new_model_yaml = """
schema_version: "1.0.0"
model_id: "dynamic-hot-added-model"
name: "Dynamic Hot Added Model"
family: "custom"
capabilities:
  - "calculation"
context_window: 8192
vram_estimate_mb: 2048
engine:
  type: "mock"
"""
    p = tmp_path / "dynamic_model.yaml"
    p.write_text(new_model_yaml, encoding="utf-8")

    # Hot register
    registered = registry.register_from_file(p)
    assert registered.model_id == "dynamic-hot-added-model"
    assert len(registry.list_manifests()) == 2
    assert registry.get_manifest("dynamic-hot-added-model") is not None


def test_registry_unregister_and_clear():
    """Verify model unregistration and clear methods."""
    registry = ModelRegistry()
    registry.register_from_file(FIXTURES_DIR / "mock_default.yaml")
    assert len(registry.list_manifests()) == 1

    assert registry.unregister("mock-default-model") is True
    assert registry.unregister("mock-default-model") is False
    assert len(registry.list_manifests()) == 0

    registry.register_from_file(FIXTURES_DIR / "mock_default.yaml")
    registry.clear()
    assert len(registry.list_manifests()) == 0
