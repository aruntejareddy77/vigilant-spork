"""
src/sovereign/vision/__init__.py
Sovereign Computer Vision & Engineering Drawing Revision Comparison Package
"""
from sovereign.vision.diff import DiffBoundingBox, DiffChangeType, DrawingDiffEngine
from sovereign.vision.overlay import VisualOverlayRenderer
from sovereign.vision.register import (
    ChangeRegister,
    ChangeRegisterGenerator,
    ChangeRegisterItem,
)
from sovereign.vision.tools import (
    DIFF_DRAWINGS_TOOL_DEF,
    handle_diff_drawings,
    register_vision_tools,
)

__all__ = [
    "DiffBoundingBox",
    "DiffChangeType",
    "DrawingDiffEngine",
    "VisualOverlayRenderer",
    "ChangeRegisterItem",
    "ChangeRegister",
    "ChangeRegisterGenerator",
    "DIFF_DRAWINGS_TOOL_DEF",
    "handle_diff_drawings",
    "register_vision_tools",
]
