"""
src/sovereign/models/adapters/mock.py
Deterministic Mock Model Adapter for offline testing and 0-GPU environments.
"""
import hashlib
import json
import math
import struct
import time
from typing import Any, List, Optional

from sovereign.models.adapter import BaseModelAdapter
from sovereign.models.manifest import ModelManifest
from sovereign.models.types import ChatMessage, ModelResponse, VisionRegion


class MockModelAdapter(BaseModelAdapter):
    """
    In-memory deterministic model adapter simulating multi-modal inference,
    chat completions, structured JSON generation, and vector embeddings without GPU hardware.
    """

    def __init__(self, manifest: ModelManifest):
        super().__init__(manifest)
        self._is_loaded: bool = False
        self.simulated_latency_ms: float = float(
            manifest.engine.parameters.get("simulated_latency_ms", 5.0)
        )

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def load(self) -> bool:
        self._is_loaded = True
        return True

    def unload(self) -> bool:
        self._is_loaded = False
        return True

    def health_check(self) -> bool:
        return True

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> ModelResponse:
        """Generates deterministic text, code, JSON, or calculations based on prompt keywords."""
        start_time = time.perf_counter()
        p_lower = prompt.lower()

        if "json" in p_lower or "schema" in p_lower:
            text = json.dumps({
                "status": "success",
                "model": self.model_id,
                "summary": "Mock structured response generated deterministically",
                "parameters": {
                    "temperature": kwargs.get("temperature", 0.0),
                    "context_length": len(prompt),
                },
                "items": ["component_alpha", "component_beta", "component_gamma"]
            }, indent=2)
        elif any(k in p_lower for k in ("python", "script", "def ", "code", "bash")):
            text = (
                "# Sovereign AI Workbench - Deterministic Code Generator\n"
                "import math\n\n"
                "def execute_engineering_calculation(flow_rate: float, diameter: float) -> float:\n"
                "    \"\"\"Calculates fluid velocity (m/s) in pipe.\"\"\"\n"
                "    area = math.pi * ((diameter / 2.0) ** 2)\n"
                "    return round(flow_rate / area, 4)\n\n"
                "if __name__ == '__main__':\n"
                "    vel = execute_engineering_calculation(0.05, 0.1)\n"
                "    print(f'Computed velocity: {vel} m/s')\n"
            )
        elif any(k in p_lower for k in ("formula", "calculate", "thermodynamics", "reynolds", "pressure")):
            text = (
                "### Engineering Calculation Trace\n\n"
                "1. **Governing Standard:** ASME B31.3 Process Piping Clause 304.1.2\n"
                "2. **Input Parameters:**\n"
                "   - Design Pressure ($P$): 2.50 MPa\n"
                "   - Outside Diameter ($D$): 219.10 mm (NPS 8)\n"
                "   - Allowable Stress ($S$): 137.00 MPa (ASTM A106 Gr. B)\n"
                "   - Joint Quality Factor ($E$): 1.00\n"
                "   - Wall Thickness Factor ($Y$): 0.40\n"
                "3. **Equation:** $t = \\frac{P \\cdot D}{2(S \\cdot E + P \\cdot Y)}$\n"
                "4. **Calculation:** $t = \\frac{2.50 \\times 219.10}{2(137.00 \\times 1.00 + 2.50 \\times 0.40)} = \\frac{547.75}{276.00} = 1.9846\\text{ mm}$\n"
                "5. **Conclusion:** Nominal wall thickness meets minimum safety criteria.\n"
            )
        elif any(k in p_lower for k in ("inspection", "approval note", "report", "memo")):
            text = (
                "# Plant Equipment Inspection & Approval Note\n\n"
                "**Facility:** Sovereign Refinery Unit 4 (Crude Distillation)\n"
                "**Equipment Tag:** T-401 Fractionator Column\n"
                "**Inspection Date:** 2026-09-10\n\n"
                "## 1. Visual Findings\n"
                "- External insulation cladding intact across upper trays.\n"
                "- Minor surface oxidation noted on nozzle N3 flange bolts; ultrasonic thickness testing indicates 12.4mm (minimum required: 9.5mm).\n\n"
                "## 2. Engineering Recommendation\n"
                "Authorize continued operation for next 12-month inspection interval with scheduled bolt replacement during Q4 turnaround.\n"
            )
        else:
            text = (
                f"Sovereign Workbench Assistant ({self.model_id}): Processed request "
                f"containing {len(prompt)} characters. Analysis complete."
            )

        prompt_tokens = max(1, len(prompt.split()))
        completion_tokens = max(1, len(text.split()))
        latency_ms = round((time.perf_counter() - start_time) * 1000 + self.simulated_latency_ms, 2)

        return ModelResponse(
            text=text,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            finish_reason="stop",
            latency_ms=latency_ms,
            vision_regions=[],
            raw_payload={"mock": True, "engine": "mock", "model_id": self.model_id},
        )

    def generate_chat(
        self,
        messages: List[ChatMessage],
        **kwargs: Any
    ) -> ModelResponse:
        """Executes multi-turn conversation turn."""
        last_user_msg = ""
        for m in reversed(messages):
            if m.role == "user":
                last_user_msg = m.content
                break
        if not last_user_msg and messages:
            last_user_msg = messages[-1].content

        return self.generate(last_user_msg, **kwargs)

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generates deterministic 768-dimensional normalized unit vectors.
        Identical input texts produce exact identical vectors.
        """
        embeddings: List[List[float]] = []
        dim = 768

        for text in texts:
            raw_vec: List[float] = []
            # Use SHA-256 blocks with deterministic salts to generate float components
            text_bytes = text.encode("utf-8")
            for block_idx in range(dim // 8):  # 8 floats per 32-byte hash
                h = hashlib.sha256(text_bytes + struct.pack(">I", block_idx)).digest()
                ints = struct.unpack(">8i", h)
                floats = [val / 2147483647.0 for val in ints]
                raw_vec.extend(floats)

            # L2 normalization to unit hypersphere
            norm = math.sqrt(sum(x * x for x in raw_vec))
            norm = norm if norm > 1e-12 else 1.0
            unit_vec = [round(x / norm, 6) for x in raw_vec]
            embeddings.append(unit_vec)

        return embeddings

    def vision_infer(
        self,
        image_bytes: bytes,
        prompt: str,
        **kwargs: Any
    ) -> ModelResponse:
        """Simulates multimodal visual analysis returning structured region coordinates."""
        img_len = len(image_bytes)
        regions = [
            VisionRegion(
                box_2d=[0.12, 0.15, 0.35, 0.45],
                label="control_valve_CV102",
                confidence=0.97
            ),
            VisionRegion(
                box_2d=[0.55, 0.40, 0.88, 0.75],
                label="centrifugal_feed_pump_P101",
                confidence=0.94
            ),
            VisionRegion(
                box_2d=[0.20, 0.70, 0.42, 0.92],
                label="pressure_transmitter_PT104",
                confidence=0.91
            )
        ]

        desc = (
            f"Vision analysis completed over image payload ({img_len} bytes). "
            f"Identified 3 schematic equipment tags: CV102 (control valve), "
            f"P101 (feed pump), and PT104 (pressure transmitter)."
        )

        return ModelResponse(
            text=desc,
            usage={"prompt_tokens": len(prompt.split()), "completion_tokens": 42, "total_tokens": 42},
            finish_reason="stop",
            latency_ms=self.simulated_latency_ms,
            vision_regions=regions,
            raw_payload={"mock_vision": True, "image_size": img_len},
        )
