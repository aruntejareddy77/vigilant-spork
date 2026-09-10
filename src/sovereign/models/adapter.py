"""
src/sovereign/models/adapter.py
Abstract base class for all sovereign model inference adapters.
"""
from abc import ABC, abstractmethod
from typing import Any, List, Optional

from sovereign.models.manifest import ModelManifest
from sovereign.models.types import ChatMessage, ModelResponse


class BaseModelAdapter(ABC):
    """
    Uniform abstract adapter interface decoupling orchestrator logic
    from underlying inference runtimes (SGLang, vLLM, Ollama, llama.cpp, Mock).
    """

    def __init__(self, manifest: ModelManifest):
        self.manifest = manifest

    @property
    def model_id(self) -> str:
        """Convenience property for model identifier."""
        return self.manifest.model_id

    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """Returns True if model weights are loaded and ready for inference."""
        pass

    @abstractmethod
    def load(self) -> bool:
        """Loads model into active VRAM/memory or establishes engine session."""
        pass

    @abstractmethod
    def unload(self) -> bool:
        """Unloads model weights from VRAM/memory."""
        pass

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> ModelResponse:
        """Executes single-turn text generation or reasoning."""
        pass

    @abstractmethod
    def generate_chat(
        self,
        messages: List[ChatMessage],
        **kwargs: Any
    ) -> ModelResponse:
        """Executes multi-turn conversation turn."""
        pass

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Computes dense vector embeddings for input text snippets."""
        pass

    @abstractmethod
    def vision_infer(
        self,
        image_bytes: bytes,
        prompt: str,
        **kwargs: Any
    ) -> ModelResponse:
        """Executes multimodal vision-language reasoning over an input image."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Verifies engine endpoint responsiveness and readiness."""
        pass

    def get_memory_footprint_mb(self) -> int:
        """
        Returns estimated or active VRAM memory allocation in MB.
        Defaults to manifest estimate if loaded, or 0 if unloaded.
        """
        return self.manifest.vram_estimate_mb if self.is_loaded else 0
