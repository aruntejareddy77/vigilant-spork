"""
src/sovereign/models/manifest.py
Declarative Model Manifest schema and validation.
"""
from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, Field, field_validator
import yaml


class ModelCapability(str, Enum):
    """Capabilities that a model can declare and fulfill."""
    TEXT_DRAFTING = "text_drafting"
    REASONING = "reasoning"
    CODE_GENERATION = "code_generation"
    VISION_MULTIMODAL = "vision_multimodal"
    EMBEDDING = "embedding"
    CALCULATION = "calculation"


class EngineType(str, Enum):
    """Supported local inference engines."""
    SGLANG = "sglang"
    VLLM = "vllm"
    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"
    MOCK = "mock"


class EngineConfig(BaseModel):
    """Configuration for connecting to or starting a model engine."""
    model_config = ConfigDict(extra="forbid")

    type: EngineType
    endpoint_url: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("endpoint_url")
    @classmethod
    def validate_loopback_only(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        parsed = urlparse(v)
        hostname = (parsed.hostname or "").lower()
        if hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError(
                f"Endpoint URL host '{hostname}' is not permitted. All inference endpoints "
                "must bind strictly to localhost (127.0.0.1 or ::1) to enforce sovereign zero-egress."
            )
        return v


class IntegrityConfig(BaseModel):
    """Cryptographic integrity and supply-chain references for model weights."""
    model_config = ConfigDict(extra="forbid")

    weights_path: Optional[str] = None
    weights_sha256: Optional[str] = None

    @field_validator("weights_sha256")
    @classmethod
    def validate_sha256_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cleaned = v.strip().lower()
        if len(cleaned) != 64 or not all(c in "0123456789abcdef" for c in cleaned):
            raise ValueError("weights_sha256 must be a valid 64-character lowercase hex digest.")
        return cleaned


class ModelManifest(BaseModel):
    """Declarative specification for an air-gapped local model."""
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0.0", description="Schema version of the manifest")
    model_id: str = Field(min_length=1, description="Unique identifier for model, e.g. qwen-2.5-14b-instruct")
    name: str = Field(min_length=1, description="Human-readable model name")
    family: str = Field(min_length=1, description="Model family, e.g. qwen, florence, llama")
    capabilities: List[ModelCapability] = Field(min_length=1, description="Declared capabilities")
    context_window: int = Field(gt=0, description="Maximum context window in tokens")
    quantization: Optional[str] = Field(default=None, description="Quantization format, e.g. AWQ, GPTQ, FP16, GGUF")
    vram_estimate_mb: int = Field(gt=0, description="Estimated VRAM usage in MB including weights and baseline KV cache")
    engine: EngineConfig = Field(description="Engine connection parameters")
    integrity: Optional[IntegrityConfig] = Field(default=None, description="Supply chain integrity hashes")

    def has_capability(self, capability: Union[ModelCapability, str]) -> bool:
        """Returns True if the manifest declares the specified capability."""
        if isinstance(capability, str):
            try:
                cap_enum = ModelCapability(capability)
            except ValueError:
                return False
        else:
            cap_enum = capability
        return cap_enum in self.capabilities


def load_manifest(manifest_path: Union[str, Path]) -> ModelManifest:
    """
    Loads and parses a YAML or JSON model manifest file.
    """
    path = Path(manifest_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Model manifest file not found: {path}")

    content = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        data = yaml.safe_load(content)
    elif suffix == ".json":
        data = json.loads(content)
    else:
        # Attempt YAML parser as superset of JSON
        try:
            data = yaml.safe_load(content)
        except Exception as e:
            raise ValueError(f"Unsupported manifest format for '{path}': {e}")

    if not isinstance(data, dict):
        raise ValueError(f"Manifest content at '{path}' must be a mapping/object.")

    return ModelManifest.model_validate(data)
