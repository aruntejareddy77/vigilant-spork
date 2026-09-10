"""
src/sovereign/models/adapters/engines.py
Specialized engine adapters for SGLang, vLLM, Ollama, and llama.cpp.
"""
from typing import Any, Dict, List, Optional

from sovereign.models.adapters.http_local import LocalHTTPModelAdapter
from sovereign.models.manifest import ModelManifest
from sovereign.models.types import ChatMessage, ModelResponse


class SGLangAdapter(LocalHTTPModelAdapter):
    """
    Adapter for SGLang server (RadixAttention, structured grammar constraints).
    Default loopback endpoint: http://127.0.0.1:30000/v1
    """

    def __init__(self, manifest: ModelManifest, timeout_seconds: float = 60.0):
        if not manifest.engine.endpoint_url:
            manifest.engine.endpoint_url = "http://127.0.0.1:30000/v1"
        super().__init__(manifest, timeout_seconds=timeout_seconds)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        regex: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> ModelResponse:
        """Adds support for SGLang regex/schema guided grammar constraints."""
        extra_kwargs = dict(kwargs)
        if regex:
            extra_kwargs["regex"] = regex
        if json_schema:
            extra_kwargs["json_schema"] = json_schema
        return super().generate(prompt, system_prompt=system_prompt, **extra_kwargs)


class VLLMAdapter(LocalHTTPModelAdapter):
    """
    Adapter for vLLM server (PagedAttention, high continuous batching).
    Default loopback endpoint: http://127.0.0.1:8000/v1
    """

    def __init__(self, manifest: ModelManifest, timeout_seconds: float = 60.0):
        if not manifest.engine.endpoint_url:
            manifest.engine.endpoint_url = "http://127.0.0.1:8000/v1"
        super().__init__(manifest, timeout_seconds=timeout_seconds)


class OllamaAdapter(LocalHTTPModelAdapter):
    """
    Adapter for Ollama server (GGUF, single-binary edge inference).
    Default loopback endpoint: http://127.0.0.1:11434/v1
    """

    def __init__(self, manifest: ModelManifest, timeout_seconds: float = 60.0):
        if not manifest.engine.endpoint_url:
            manifest.engine.endpoint_url = "http://127.0.0.1:11434/v1"
        super().__init__(manifest, timeout_seconds=timeout_seconds)


class LlamaCppAdapter(LocalHTTPModelAdapter):
    """
    Adapter for llama-server (llama.cpp HTTP server).
    Default loopback endpoint: http://127.0.0.1:8080/v1
    """

    def __init__(self, manifest: ModelManifest, timeout_seconds: float = 60.0):
        if not manifest.engine.endpoint_url:
            manifest.engine.endpoint_url = "http://127.0.0.1:8080/v1"
        super().__init__(manifest, timeout_seconds=timeout_seconds)
