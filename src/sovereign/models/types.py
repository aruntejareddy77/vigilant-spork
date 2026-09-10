"""
src/sovereign/models/types.py
Data structures and exchange types for local model serving.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    """Represents a single conversational turn."""
    model_config = ConfigDict(extra="forbid")

    role: str = Field(description="Role of the author: system, user, assistant, or tool")
    content: str = Field(description="Content of the message")
    name: Optional[str] = Field(default=None, description="Optional name of the participant or tool")


class VisionRegion(BaseModel):
    """Normalized spatial bounding box and semantic label identified in an image."""
    model_config = ConfigDict(extra="forbid")

    box_2d: List[float] = Field(
        description="Normalized coordinates [ymin, xmin, ymax, xmax] scaled 0.0 to 1.0"
    )
    label: str = Field(description="Detected object class or schematic component (e.g. valve, pump)")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")


class ModelResponse(BaseModel):
    """Standardized response container across all local model backends."""
    model_config = ConfigDict(extra="forbid")

    text: str = Field(description="Primary text generation output")
    usage: Dict[str, int] = Field(
        default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        description="Token consumption metrics"
    )
    finish_reason: Optional[str] = Field(default="stop", description="Reason inference finished")
    latency_ms: float = Field(default=0.0, description="Total inference latency in milliseconds")
    vision_regions: List[VisionRegion] = Field(default_factory=list, description="Extracted vision regions")
    raw_payload: Optional[Dict[str, Any]] = Field(default=None, description="Raw engine response dictionary")
