"""
src/sovereign/vision/__init__.py
Sovereign Computer Vision & Engineering Drawing Revision Comparison Package
"""
from sovereign.vision.diff import DiffBoundingBox, DiffChangeType, DrawingDiffEngine
from sovereign.vision.overlay import VisualOverlayRenderer

__all__ = [
    "DiffBoundingBox",
    "DiffChangeType",
    "DrawingDiffEngine",
    "VisualOverlayRenderer",
]
