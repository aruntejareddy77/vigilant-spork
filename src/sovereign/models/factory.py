"""
src/sovereign/models/factory.py
Dynamic adapter factory mapping declarative engine types to concrete implementations.
"""
from typing import Dict, Type

from sovereign.models.adapter import BaseModelAdapter
from sovereign.models.adapters.mock import MockModelAdapter
from sovereign.models.adapters.engines import (
    SGLangAdapter,
    VLLMAdapter,
    OllamaAdapter,
    LlamaCppAdapter,
)
from sovereign.models.manifest import EngineType, ModelManifest


ADAPTER_MAPPING: Dict[EngineType, Type[BaseModelAdapter]] = {
    EngineType.MOCK: MockModelAdapter,
    EngineType.SGLANG: SGLangAdapter,
    EngineType.VLLM: VLLMAdapter,
    EngineType.OLLAMA: OllamaAdapter,
    EngineType.LLAMACPP: LlamaCppAdapter,
}


def create_adapter(manifest: ModelManifest) -> BaseModelAdapter:
    """
    Instantiates the appropriate BaseModelAdapter concrete implementation
    based on the declared manifest.engine.type.
    """
    engine_type = manifest.engine.type
    adapter_cls = ADAPTER_MAPPING.get(engine_type)
    if not adapter_cls:
        raise ValueError(
            f"Unsupported engine type '{engine_type}'. "
            f"Supported engines are: {[e.value for e in ADAPTER_MAPPING.keys()]}"
        )

    return adapter_cls(manifest)
