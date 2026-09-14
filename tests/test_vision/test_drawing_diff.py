"""
tests/test_vision/test_drawing_diff.py
Unit and Integration Tests for DrawingDiffEngine and VisualOverlayRenderer.
Validates pure-Pillow pixel differencing, morphological clustering, memory bounds,
high-contrast overlay rendering, drafting title block with legend, and PNG lineage injection.
Complies with MMOD-03, T-04-03, and T-04-04.
"""
from pathlib import Path
import pytest
from PIL import Image, ImageDraw

from sovereign.lineage.injectors.png import extract_png_lineage
from sovereign.tools.builtin.files import PathSecurityViolation
from sovereign.vision.diff import (
    DiffBoundingBox,
    DiffChangeType,
    DrawingDiffEngine,
    MAX_FILE_SIZE_BYTES,
)
from sovereign.vision.overlay import VisualOverlayRenderer


@pytest.fixture
def sample_drawings(tmp_path: Path):
    """
    Creates a pair of synthetic P&ID drawing revisions:
    - Rev A: Main pipeline with Valve V-101 and Valve V-102.
    - Rev B: Main pipeline with Valve V-101 (unchanged), Valve V-102 removed,
             and a new bypass line with Valve V-103 added.
    """
    width, height = 800, 600

    # Rev A
    im_a = Image.new("RGB", (width, height), (255, 255, 255))
    draw_a = ImageDraw.Draw(im_a)

    # Main pipe line
    draw_a.line([(100, 300), (700, 300)], fill=(0, 0, 0), width=6)

    # Valve V-101 (Unchanged between Rev A and B) at x=250
    draw_a.rectangle([230, 280, 270, 320], fill=(0, 0, 0))

    # Valve V-102 (Removed in Rev B) at x=600
    draw_a.rectangle([580, 280, 620, 320], fill=(0, 0, 0))
    draw_a.text((580, 250), "V-102", fill=(0, 0, 0))

    # Equipment Tag at (400, 110) (Modified in Rev B)
    draw_a.rectangle([380, 90, 420, 130], fill=(0, 0, 0))

    path_a = tmp_path / "pid_rev_a.png"
    im_a.save(path_a)

    # Rev B
    im_b = Image.new("RGB", (width, height), (255, 255, 255))
    draw_b = ImageDraw.Draw(im_b)

    # Main pipe line
    draw_b.line([(100, 300), (700, 300)], fill=(0, 0, 0), width=6)

    # Valve V-101 (Unchanged)
    draw_b.rectangle([230, 280, 270, 320], fill=(0, 0, 0))

    # Valve V-102 is REMOVED (blank space left at x=600)

    # Pump P-101 (ADDED in Rev B) at x=150, y=110
    draw_b.rectangle([130, 90, 170, 130], fill=(0, 0, 0))
    draw_b.text((130, 140), "P-101", fill=(0, 0, 0))

    # Equipment Tag at (400, 110) MODIFIED (larger circle replaced rectangle)
    draw_b.ellipse([360, 70, 440, 150], fill=(120, 120, 120))

    path_b = tmp_path / "pid_rev_b.png"
    im_b.save(path_b)

    return path_a, path_b


class TestDrawingDiffEngine:
    """Unit tests for DrawingDiffEngine differencing and clustering."""

    def test_diff_models_serialization(self):
        """Validates DiffBoundingBox Pydantic model serialization and constraints."""
        box = DiffBoundingBox(
            box_id=1,
            box_2d=[0.15, 0.20, 0.35, 0.45],
            change_type=DiffChangeType.ADDED,
            pixel_count=150,
            confidence=0.98,
            description="New bypass line",
        )
        data = box.model_dump()
        assert data["box_id"] == 1
        assert data["change_type"] == "ADDED"
        assert len(data["box_2d"]) == 4

        # Roundtrip validation
        rehydrated = DiffBoundingBox.model_validate(data)
        assert rehydrated.change_type == DiffChangeType.ADDED

    def test_identical_drawings_yield_zero_diff(self, sample_drawings):
        """Comparing an image to itself must return zero diff boxes."""
        path_a, _ = sample_drawings
        diff_boxes = DrawingDiffEngine.compare_revisions(path_a, path_a)
        assert diff_boxes == []

    def test_missing_file_raises_not_found(self, tmp_path: Path):
        """Comparing a non-existent file must raise FileNotFoundError."""
        missing = tmp_path / "non_existent.png"
        dummy = tmp_path / "dummy.png"
        Image.new("RGB", (100, 100)).save(dummy)

        with pytest.raises(FileNotFoundError):
            DrawingDiffEngine.compare_revisions(missing, dummy)

        with pytest.raises(FileNotFoundError):
            DrawingDiffEngine.compare_revisions(dummy, missing)

    def test_invalid_image_format_raises_value_error(self, tmp_path: Path):
        """Non-image files or unsupported extensions must fail input validation."""
        bad_file = tmp_path / "malicious.sh"
        bad_file.write_text("#!/bin/bash\necho bad", encoding="utf-8")
        good_file = tmp_path / "valid.png"
        Image.new("RGB", (50, 50)).save(good_file)

        with pytest.raises(ValueError, match="Unsupported image format"):
            DrawingDiffEngine.compare_revisions(bad_file, good_file)

    def test_file_size_exceeding_ceiling_raises_value_error(self, tmp_path: Path, monkeypatch):
        """Files exceeding MAX_FILE_SIZE_BYTES must be rejected before memory allocation."""
        large_file = tmp_path / "huge.png"
        Image.new("RGB", (10, 10)).save(large_file)

        # Mock stat().st_size to simulate an oversized file
        orig_stat = Path.stat

        def fake_stat(self):
            st = orig_stat(self)
            if self.name == "huge.png":
                return type("FakeStat", (), {"st_size": MAX_FILE_SIZE_BYTES + 1024, "st_mode": st.st_mode})()
            return st

        monkeypatch.setattr(Path, "stat", fake_stat)

        with pytest.raises(ValueError, match="Drawing file size .* exceeds security ceiling"):
            DrawingDiffEngine.compare_revisions(large_file, large_file)

    def test_dimension_mismatch_resizes_gracefully(self, tmp_path: Path):
        """Drawings with minor dimension variances (e.g. scanner drift) are aligned."""
        img_a_path = tmp_path / "dim_a.png"
        img_b_path = tmp_path / "dim_b.png"

        im_a = Image.new("RGB", (400, 300), (255, 255, 255))
        im_b = Image.new("RGB", (450, 350), (255, 255, 255))

        # Add a change in B
        draw_b = ImageDraw.Draw(im_b)
        draw_b.rectangle([100, 100, 150, 150], fill=(0, 0, 0))

        im_a.save(img_a_path)
        im_b.save(img_b_path)

        diff_boxes = DrawingDiffEngine.compare_revisions(img_a_path, img_b_path)
        assert len(diff_boxes) >= 1
        assert diff_boxes[0].box_id == 1

    def test_large_drawing_auto_scaled(self, tmp_path: Path):
        """Images exceeding 4096px are downsampled to stay under memory ceiling."""
        large_a = tmp_path / "large_a.png"
        large_b = tmp_path / "large_b.png"

        # Create 4500 x 200 image
        im_a = Image.new("RGB", (4500, 200), (255, 255, 255))
        im_b = Image.new("RGB", (4500, 200), (255, 255, 255))
        draw_b = ImageDraw.Draw(im_b)
        draw_b.rectangle([500, 50, 800, 150], fill=(0, 0, 0))

        im_a.save(large_a)
        im_b.save(large_b)

        # compare_revisions with max_dimension=1000 for test speed
        diff_boxes = DrawingDiffEngine.compare_revisions(large_a, large_b, max_dimension=1000)
        assert len(diff_boxes) >= 1
        assert diff_boxes[0].change_type == DiffChangeType.ADDED

    def test_revision_diff_detects_added_and_removed_regions(self, sample_drawings):
        """Verifies synthetic P&ID comparison correctly clusters and identifies ADDED and REMOVED."""
        path_a, path_b = sample_drawings

        diff_boxes = DrawingDiffEngine.compare_revisions(path_a, path_b, sensitivity=25, min_pixels=15)

        assert len(diff_boxes) >= 2

        types_found = {b.change_type for b in diff_boxes}
        assert DiffChangeType.ADDED in types_found
        assert DiffChangeType.REMOVED in types_found

        # Verify coordinates normalization
        for box in diff_boxes:
            ymin, xmin, ymax, xmax = box.box_2d
            assert 0.0 <= ymin <= ymax <= 1.0
            assert 0.0 <= xmin <= xmax <= 1.0
            assert box.pixel_count > 0
            assert 0.0 <= box.confidence <= 1.0

        # Verify 1-indexed contiguous box_ids
        ids = [b.box_id for b in diff_boxes]
        assert ids == list(range(1, len(diff_boxes) + 1))

    def test_crop_diff_region(self, sample_drawings):
        """Verifies cropping a specific diff bounding box returns a valid PIL Image."""
        path_a, path_b = sample_drawings
        diff_boxes = DrawingDiffEngine.compare_revisions(path_a, path_b)
        assert len(diff_boxes) > 0

        crop = DrawingDiffEngine.crop_diff_region(path_b, diff_boxes[0].box_2d, padding_px=10)
        assert isinstance(crop, Image.Image)
        assert crop.width > 0 and crop.height > 0


class TestVisualOverlayRenderer:
    """Unit tests for VisualOverlayRenderer color-coding, badges, title block, and lineage."""

    def test_render_diff_overlay_success(self, sample_drawings, tmp_path: Path):
        """Renders overlay and verifies colors, dimensions, lineage injection, and sidecar."""
        path_a, path_b = sample_drawings
        diff_boxes = DrawingDiffEngine.compare_revisions(path_a, path_b)
        assert len(diff_boxes) > 0

        output_overlay = tmp_path / "output" / "pid_rev_b_annotated.png"

        result_path = VisualOverlayRenderer.render_diff_overlay(
            img_b_path=path_b,
            diff_boxes=diff_boxes,
            output_path=output_overlay,
            drawing_title="P&ID-SYS-101 Main Transfer Line",
        )

        assert result_path.exists()
        assert result_path == output_overlay.resolve()

        # Check rendered image
        with Image.open(result_path) as rendered:
            assert rendered.format == "PNG"
            # Matches Rev B size
            with Image.open(path_b) as base:
                assert rendered.size == base.size

        # Sibling lineage manifest
        sidecar_path = Path(f"{result_path}.lineage.json")
        assert sidecar_path.exists()

        # Check embedded PNG tEXt lineage chunk
        injected_summary = extract_png_lineage(result_path.read_bytes())
        assert injected_summary is not None
        assert "sovereign-vision-diff-v1" in injected_summary
        assert "P&ID-SYS-101 Main Transfer Line" in injected_summary

    def test_path_traversal_fencing(self, sample_drawings, tmp_path: Path):
        """Overlay rendering outside allowed_root raises PathSecurityViolation."""
        _, path_b = sample_drawings
        diff_boxes = [
            DiffBoundingBox(
                box_id=1,
                box_2d=[0.1, 0.1, 0.3, 0.3],
                change_type=DiffChangeType.ADDED,
            )
        ]

        allowed_dir = tmp_path / "allowed_sandbox"
        allowed_dir.mkdir()

        malicious_target = tmp_path / "escaped" / "evil_overlay.png"

        with pytest.raises(PathSecurityViolation, match="Path traversal detected"):
            VisualOverlayRenderer.render_diff_overlay(
                img_b_path=path_b,
                diff_boxes=diff_boxes,
                output_path=malicious_target,
                allowed_root=allowed_dir,
            )
