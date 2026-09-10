"""
tests/test_models/test_adapter_factory.py
Unit tests for create_adapter factory and ModelRegistry adapter caching.
"""
from pathlib import Path
import pytest

from sovereign.models.adapters.engines import (
    LlamaCppAdapter,
    OllamaAdapter,
    SGLangAdapter,
    VLLMAdapter,
)
from sovereign.models.adapters.mock import MockModelAdapter
from sovereign.models.factory import create_adapter
from sovereign.models.manifest import (
    EngineConfig,
    EngineType,
    ModelCapability,
    ModelManifest,
    load_manifest,
)
from sovereign.models.registry import ModelRegistry

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "models"


def test_create_adapter_all_engine_types():
    """Verify factory maps all declared engine types to proper adapter classes."""
    def make_manifest(etype: EngineType) -> ModelManifest:
        return ModelManifest(
            model_id=f"model-{etype.value}",
            name=f"Model {etype.value}",
            family="test",
            capabilities=[ModelCapability.REASONING],
            context_window=4096,
            vram_estimate_mb=1024,
            engine=EngineConfig(type=etype),
        )

    # Mock
    a_mock = create_adapter(make_manifest(EngineType.MOCK))
    assert isinstance(a_mock, MockModelAdapter)

    # SGLang
    a_sg = create_adapter(make_manifest(EngineType.SGLANG))
    assert isinstance(a_sg, SGLangAdapter)

    # vLLM
    a_vl = create_adapter(make_manifest(EngineType.VLLM))
    assert isinstance(a_vl, VLLMAdapter)

    # Ollama
    a_ol = create_adapter(make_manifest(EngineType.OLLAMA))
    assert isinstance(a_ol, OllamaAdapter)

    # llama.cpp
    a_lc = create_adapter(make_manifest(EngineType.LLAMACPP))
    assert isinstance(a_lc, LlamaCppAdapter)


def test_registry_adapter_caching():
    """Verify ModelRegistry instantiates, caches, and unloads adapters."""
    registry = ModelRegistry()
    manifest = load_manifest(FIXTURES_DIR / "mock_default.yaml")
    registry.register_manifest(manifest)

    # 1. First get_adapter call instantiates adapter
    adapter1 = registry.get_adapter("mock-default-model")
    assert isinstance(adapter1, MockModelAdapter)

    # 2. Subsequent call returns cached instance
    adapter2 = registry.get_adapter("mock-default-model")
    assert adapter1 is adapter2

    # 3. Unregistered model raises KeyError
    with pytest.raises(KeyError):
        registry.get_adapter("unregistered-model-id")

    # 4. Load adapter and verify unload_all
    adapter1.load()
    assert adapter1.is_loaded is True

    registry.unload_all()
    assert adapter1.is_loaded is False

    # 5. Unregister model
    assert registry.unregister("mock-default-model") is True
    with pytest.raises(KeyError):
        registry.get_adapter("mock-default-model")
