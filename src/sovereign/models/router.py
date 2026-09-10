"""
src/sovereign/models/router.py
Task classification and intelligent capability-based model auto-routing.
"""
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from sovereign.audit.ledger import AuditLedger
from sovereign.models.manifest import ModelCapability, ModelManifest
from sovereign.models.registry import ModelRegistry

logger = logging.getLogger("sovereign.models.router")


class RoutingDecision(BaseModel):
    """Result of an auto-routing or manual override model selection."""
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(description="Selected model ID")
    capability: ModelCapability = Field(description="Classified or assigned primary capability")
    rationale: str = Field(description="Detailed rationale explaining model selection")
    vram_estimate_mb: int = Field(description="Estimated VRAM allocation in MB")
    is_override: bool = Field(default=False, description="True if selected via explicit manual override")


class TaskClassifier:
    """
    Deterministic rule-based intent classifier mapping incoming user prompts,
    data payloads, and modalities into required ModelCapabilities.
    """

    VISION_KEYWORDS = {
        "image", "photo", "drawing", "p&id", "schematic", "blueprint",
        "valve", "piping", "bounding box", "diagram", "defect", "flange"
    }

    CODE_KEYWORDS = {
        "python", "script", "sql", "def ", "import ", "bash", "lambda",
        "class ", "function", "compile", "syntax", "code"
    }

    CALC_KEYWORDS = {
        "formula", "pressure", "thermodynamics", "reynolds", "enthalpy",
        "calculate", "thickness", "asme", "equation", "stress", "flow rate"
    }

    DRAFT_KEYWORDS = {
        "draft", "memo", "approval note", "report", "summary", "executive",
        "formal letter", "findings", "recommendation"
    }

    @classmethod
    def classify(
        cls,
        prompt: str,
        has_image: bool = False,
        is_embedding_batch: bool = False,
    ) -> ModelCapability:
        """Determines primary capability required to fulfill the task."""
        # 1. Image data / Multimodal has highest priority
        if has_image:
            return ModelCapability.VISION_MULTIMODAL

        p_lower = prompt.lower()

        # 2. Embedding batch
        if is_embedding_batch:
            return ModelCapability.EMBEDDING

        # 3. Explicit vision keywords in text-only request asking for visual analysis
        if any(w in p_lower for w in ("p&id", "drawing", "schematic", "bounding box", "inspection photo")):
            return ModelCapability.VISION_MULTIMODAL

        # 4. Code syntax & programming requests
        if any(w in p_lower for w in cls.CODE_KEYWORDS) or re.search(r"\b(def|class|import|return)\b", p_lower):
            return ModelCapability.CODE_GENERATION

        # 5. Engineering calculations & math
        if any(w in p_lower for w in cls.CALC_KEYWORDS):
            return ModelCapability.CALCULATION

        # 6. Formal documentation & report drafting
        if any(w in p_lower for w in cls.DRAFT_KEYWORDS):
            return ModelCapability.TEXT_DRAFTING

        # 7. Default general reasoning
        return ModelCapability.REASONING


class TaskRouter:
    """
    Routes user tasks to the optimal registered model based on task classification,
    model capabilities, resource estimates, and manual override flags.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        audit_ledger: Optional[AuditLedger] = None
    ):
        self.registry = registry
        self.audit_ledger = audit_ledger

    def route(
        self,
        prompt: str,
        image_bytes: Optional[bytes] = None,
        model_override: Optional[str] = None,
        session_id: Optional[str] = None,
        is_embedding: bool = False,
    ) -> RoutingDecision:
        """
        Selects the best model for the incoming request, emits an audit event,
        and returns a complete RoutingDecision.
        """
        # 1. Check for manual override (FR-MM-6)
        if model_override:
            manifest = self.registry.get_manifest(model_override)
            if not manifest:
                raise KeyError(
                    f"Manual model override failed: '{model_override}' is not registered in the catalog."
                )
            decision = RoutingDecision(
                model_id=manifest.model_id,
                capability=manifest.capabilities[0],
                rationale=f"Manual user override (--model {model_override})",
                vram_estimate_mb=manifest.vram_estimate_mb,
                is_override=True,
            )
        else:
            # 2. Classify task intent
            capability = TaskClassifier.classify(
                prompt=prompt,
                has_image=bool(image_bytes),
                is_embedding_batch=is_embedding,
            )

            # 3. Query candidate models
            candidates = self.registry.find_by_capability(capability)
            if candidates:
                def candidate_rank(m: ModelManifest):
                    # Prefer real production engines over mock when available
                    is_mock = 1 if m.engine.type.value == "mock" else 0
                    # Specialized name affinity
                    name_lower = m.model_id.lower()
                    affinity = 0
                    if capability == ModelCapability.CODE_GENERATION and "coder" in name_lower:
                        affinity = -2
                    elif capability == ModelCapability.VISION_MULTIMODAL and any(k in name_lower for k in ("vision", "florence", "vl")):
                        affinity = -2
                    elif capability == ModelCapability.EMBEDDING and any(k in name_lower for k in ("embed", "bge")):
                        affinity = -2
                    # Focused specialization: fewer declared capabilities means more dedicated model
                    specialization = len(m.capabilities)
                    return (is_mock, affinity, specialization, m.vram_estimate_mb)

                selected = sorted(candidates, key=candidate_rank)[0]
                rationale = (
                    f"Auto-routed: Task classified as '{capability.value}'. "
                    f"Selected specialized model '{selected.model_id}' ({selected.vram_estimate_mb}MB VRAM)."
                )
            else:
                # Fallback to general reasoning models, or any available model
                fallbacks = self.registry.find_by_capability(ModelCapability.REASONING)
                if not fallbacks:
                    fallbacks = self.registry.list_manifests()

                if not fallbacks:
                    raise RuntimeError("No models registered in catalog to route task.")

                selected = sorted(fallbacks, key=lambda m: m.vram_estimate_mb)[0]
                rationale = (
                    f"Fallback: No model declared '{capability.value}'. "
                    f"Routing to general model '{selected.model_id}'."
                )

            decision = RoutingDecision(
                model_id=selected.model_id,
                capability=capability,
                rationale=rationale,
                vram_estimate_mb=selected.vram_estimate_mb,
                is_override=False,
            )

        # 4. Audit Trail Logging (SOVG-01)
        if self.audit_ledger:
            try:
                self.audit_ledger.append_event(
                    session_id=session_id or "task-routing",
                    event_type="MODEL_ROUTED",
                    actor_role="task-router",
                    payload={
                        "prompt_preview": prompt[:120],
                        "classified_capability": decision.capability.value,
                        "selected_model_id": decision.model_id,
                        "rationale": decision.rationale,
                        "is_override": decision.is_override,
                        "vram_estimate_mb": decision.vram_estimate_mb,
                    },
                )
            except Exception as e:
                logger.error(f"Failed to record MODEL_ROUTED event in audit ledger: {e}")

        return decision
