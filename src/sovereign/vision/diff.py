"""
src/sovereign/vision/diff.py
Dual-layer Engineering Drawing / P&ID Revision Comparison Engine.
Layer 1: Pixel differencing, luminance polarity analysis, morphological clustering.
Complies with MMOD-03, T-04-03 (DoS / memory bounds), and ASVS V5.1/V5.2.4.
"""
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple, Union
from PIL import Image, ImageChops
from pydantic import BaseModel, Field

# Strict memory & dimension ceilings (Threat T-04-03 mitigation)
MAX_IMAGE_PIXELS = 50_000_000
MAX_IMAGE_DIMENSION = 4096
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class DiffChangeType(str, Enum):
    """Classification of detected visual changes between drawing revisions."""
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"


class DiffBoundingBox(BaseModel):
    """
    Normalized spatial bounding box identifying a region of physical difference
    between two engineering drawing revisions.
    """
    box_id: int = Field(..., description="1-indexed identifier matching visual callout badge")
    box_2d: List[float] = Field(..., description="Normalized coordinates [ymin, xmin, ymax, xmax] in [0.0, 1.0]")
    change_type: DiffChangeType = Field(..., description="Classification: ADDED, REMOVED, or MODIFIED")
    pixel_count: int = Field(default=0, description="Total number of thresholded changed pixels in region")
    confidence: float = Field(default=1.0, description="Clustering and detection confidence in [0.0, 1.0]")
    description: Optional[str] = Field(default=None, description="Optional semantic description of change")


class DrawingDiffEngine:
    """
    Pure-Python industrial drawing differencing engine leveraging Pillow.
    Performs memory-bounded pixel differencing, polarity luminance analysis,
    and connected component clustering to isolate modified engineering drawing elements.
    """

    COLOR_ADDED = (0, 200, 83)      # Vivid Green (#00C853)
    COLOR_REMOVED = (213, 0, 0)     # Vivid Red (#D50000)
    COLOR_MODIFIED = (255, 214, 0)  # Vivid Amber (#FFD600)

    @classmethod
    def _validate_image_file(cls, path: Path) -> None:
        """Validates file existence, format extension, and file size bounds."""
        if not path.exists():
            raise FileNotFoundError(f"Drawing file not found: {path}")
        if not path.is_file():
            raise ValueError(f"Path is not a regular file: {path}")
        if path.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError(
                f"Unsupported image format '{path.suffix}'. Allowed extensions: {ALLOWED_IMAGE_EXTENSIONS}"
            )
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"Drawing file size ({file_size} bytes) exceeds security ceiling ({MAX_FILE_SIZE_BYTES} bytes)"
            )

    @classmethod
    def _load_and_normalize(cls, path: Path, max_dimension: int = MAX_IMAGE_DIMENSION) -> Image.Image:
        """
        Loads an image safely with Pillow, enforcing MAX_IMAGE_PIXELS and auto-scaling
        dimensions exceeding max_dimension to preserve <250MB memory bounds.
        """
        cls._validate_image_file(path)
        try:
            img = Image.open(path)
            img.load()  # Force load image data to catch corruptions / decompression bombs early
        except Image.DecompressionBombError as dbe:
            raise ValueError(f"Image exceeds safe decompression ceiling: {dbe}") from dbe
        except Exception as exc:
            raise ValueError(f"Failed to open image {path}: {exc}") from exc

        # Convert to RGB (normalizes grayscale, RGBA, CMYK, Palette formats)
        img = img.convert("RGB")

        # Auto-scale if any dimension exceeds max_dimension
        w, h = img.size
        if max(w, h) > max_dimension:
            scale = max_dimension / float(max(w, h))
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            img = img.resize((new_w, new_h), Image.Resampling.BILINEAR)

        return img

    @classmethod
    def compare_revisions(
        cls,
        img_a_path: Union[str, Path],
        img_b_path: Union[str, Path],
        sensitivity: int = 30,
        min_pixels: int = 20,
        max_dimension: int = MAX_IMAGE_DIMENSION,
    ) -> List[DiffBoundingBox]:
        """
        Executes Layer 1 revision comparison between Drawing Rev A and Drawing Rev B.

        Args:
            img_a_path: Path to baseline engineering drawing (Rev A).
            img_b_path: Path to updated engineering drawing (Rev B).
            sensitivity: Pixel luminance difference threshold (0-255). Differences > sensitivity are retained.
            min_pixels: Minimum number of changed pixels required to form a valid diff box (noise filter).
            max_dimension: Maximum dimension ceiling for bilinear scaling.

        Returns:
            List of normalized, 1-indexed DiffBoundingBox records sorted in reading order.
        """
        path_a = Path(img_a_path).resolve()
        path_b = Path(img_b_path).resolve()

        im_a = cls._load_and_normalize(path_a, max_dimension=max_dimension)
        im_b = cls._load_and_normalize(path_b, max_dimension=max_dimension)

        # Normalize dimensions: resize Rev B to match Rev A if slight scan variance exists
        if im_a.size != im_b.size:
            im_b = im_b.resize(im_a.size, Image.Resampling.BILINEAR)

        w, h = im_a.size

        # Grayscale conversion for luminance difference
        im_a_l = im_a.convert("L")
        im_b_l = im_b.convert("L")

        # Pixel differencing
        diff_img = ImageChops.difference(im_a_l, im_b_l)

        # Threshold mask (255 where diff >= sensitivity, else 0)
        mask = diff_img.point(lambda p: 255 if p >= sensitivity else 0)

        extrema = mask.getextrema()
        if extrema[1] == 0:
            return []  # Zero differences detected

        # Grid-based connected component clustering
        # Adaptive cell size (typically 12-16 pixels for standard drawings)
        cell_size = max(6, min(16, min(w, h) // 25))
        gw = (w + cell_size - 1) // cell_size
        gh = (h + cell_size - 1) // cell_size

        grid_img = mask.resize((gw, gh), Image.Resampling.BOX)
        grid_data = grid_img.load()

        visited = set()
        components: List[List[Tuple[int, int]]] = []

        for gy in range(gh):
            for gx in range(gw):
                if grid_data[gx, gy] > 0 and (gx, gy) not in visited:
                    comp = []
                    queue = [(gx, gy)]
                    visited.add((gx, gy))
                    while queue:
                        cx, cy = queue.pop(0)
                        comp.append((cx, cy))
                        for dx in (-1, 0, 1):
                            for dy in (-1, 0, 1):
                                nx, ny = cx + dx, cy + dy
                                if 0 <= nx < gw and 0 <= ny < gh:
                                    if grid_data[nx, ny] > 0 and (nx, ny) not in visited:
                                        visited.add((nx, ny))
                                        queue.append((nx, ny))
                    components.append(comp)

        # Determine if drawing is standard light background (paper) or dark background (CAD blueprint)
        # Average extrema across both images
        ext_a = im_a_l.getextrema()
        ext_b = im_b_l.getextrema()
        is_light_bg = (sum(ext_a) + sum(ext_b)) / 4.0 >= 128.0

        # Build candidate bounding boxes
        candidate_boxes = []  # tuples: [xmin, ymin, xmax, ymax, added_count, removed_count, total_count]

        for comp in components:
            c_xmin = min(gx for gx, _ in comp) * cell_size
            c_ymin = min(gy for _, gy in comp) * cell_size
            c_xmax = min(w, (max(gx for gx, _ in comp) + 1) * cell_size)
            c_ymax = min(h, (max(gy for _, gy in comp) + 1) * cell_size)

            mask_crop = mask.crop((c_xmin, c_ymin, c_xmax, c_ymax))
            tight_bbox = mask_crop.getbbox()
            if not tight_bbox:
                continue

            t_xmin = c_xmin + tight_bbox[0]
            t_ymin = c_ymin + tight_bbox[1]
            t_xmax = c_xmin + tight_bbox[2]
            t_ymax = c_ymin + tight_bbox[3]

            crop_a = im_a_l.crop((t_xmin, t_ymin, t_xmax, t_ymax))
            crop_b = im_b_l.crop((t_xmin, t_ymin, t_xmax, t_ymax))
            crop_m = mask.crop((t_xmin, t_ymin, t_xmax, t_ymax))

            if hasattr(crop_a, "get_flattened_data"):
                pixels_a = list(crop_a.get_flattened_data())
                pixels_b = list(crop_b.get_flattened_data())
                pixels_m = list(crop_m.get_flattened_data())
            else:
                pixels_a = list(crop_a.getdata())
                pixels_b = list(crop_b.getdata())
                pixels_m = list(crop_m.getdata())

            added_c = 0
            removed_c = 0
            total_c = 0

            for pa, pb, pm in zip(pixels_a, pixels_b, pixels_m):
                if pm > 0:
                    total_c += 1
                    if is_light_bg:
                        # Paper: Rev B darker means added ink; Rev B lighter means removed ink
                        if pa > pb:
                            added_c += 1
                        elif pb > pa:
                            removed_c += 1
                    else:
                        # Blueprint: Rev B brighter means added element; Rev B darker means removed
                        if pb > pa:
                            added_c += 1
                        elif pa > pb:
                            removed_c += 1

            if total_c >= min_pixels:
                candidate_boxes.append([t_xmin, t_ymin, t_xmax, t_ymax, added_c, removed_c, total_c])

        if not candidate_boxes:
            return []

        # Merge adjacent or overlapping bounding boxes (within merge_margin)
        merge_margin = max(8, cell_size)
        merged = True
        while merged:
            merged = False
            new_candidates = []
            skip_indices = set()

            for i in range(len(candidate_boxes)):
                if i in skip_indices:
                    continue
                cur = candidate_boxes[i]
                for j in range(i + 1, len(candidate_boxes)):
                    if j in skip_indices:
                        continue
                    other = candidate_boxes[j]
                    # Check proximity/overlap with margin
                    if not (cur[2] + merge_margin < other[0] or
                            other[2] + merge_margin < cur[0] or
                            cur[3] + merge_margin < other[1] or
                            other[3] + merge_margin < cur[1]):
                        # Merge boxes
                        cur = [
                            min(cur[0], other[0]),
                            min(cur[1], other[1]),
                            max(cur[2], other[2]),
                            max(cur[3], other[3]),
                            cur[4] + other[4],
                            cur[5] + other[5],
                            cur[6] + other[6],
                        ]
                        skip_indices.add(j)
                        merged = True
                new_candidates.append(cur)

            candidate_boxes = new_candidates

        # Sort in reading order (row by row, then left to right)
        row_height = max(20, h // 20)
        candidate_boxes.sort(key=lambda b: (b[1] // row_height, b[0]))

        # Format into DiffBoundingBox models
        diff_boxes: List[DiffBoundingBox] = []
        for idx, item in enumerate(candidate_boxes, 1):
            xmin, ymin, xmax, ymax, added_c, removed_c, total_c = item

            # Determine change type
            if added_c > 0 and removed_c > 0:
                overlap = min(added_c, removed_c) / float(max(added_c, removed_c))
                if overlap >= 0.20:
                    change_type = DiffChangeType.MODIFIED
                elif added_c > removed_c:
                    change_type = DiffChangeType.ADDED
                else:
                    change_type = DiffChangeType.REMOVED
            elif added_c > 0:
                change_type = DiffChangeType.ADDED
            elif removed_c > 0:
                change_type = DiffChangeType.REMOVED
            else:
                change_type = DiffChangeType.MODIFIED

            # Normalized coordinates [ymin, xmin, ymax, xmax] clamped in [0.0, 1.0]
            norm_box = [
                round(max(0.0, min(1.0, ymin / float(h))), 4),
                round(max(0.0, min(1.0, xmin / float(w))), 4),
                round(max(0.0, min(1.0, ymax / float(h))), 4),
                round(max(0.0, min(1.0, xmax / float(w))), 4),
            ]

            confidence = round(min(1.0, 0.85 + min(0.15, (total_c / 300.0) * 0.15)), 2)

            diff_boxes.append(
                DiffBoundingBox(
                    box_id=idx,
                    box_2d=norm_box,
                    change_type=change_type,
                    pixel_count=total_c,
                    confidence=confidence,
                )
            )

        return diff_boxes

    @classmethod
    def crop_diff_region(
        cls,
        image_path: Union[str, Path],
        box_2d: List[float],
        padding_px: int = 15,
        max_dimension: int = MAX_IMAGE_DIMENSION,
    ) -> Image.Image:
        """
        Crops a specific diff bounding box region from a drawing for visual inspection or VLM reasoning.
        """
        img = cls._load_and_normalize(Path(image_path), max_dimension=max_dimension)
        w, h = img.size
        ymin, xmin, ymax, xmax = box_2d

        px_x0 = max(0, int(xmin * w) - padding_px)
        px_y0 = max(0, int(ymin * h) - padding_px)
        px_x1 = min(w, int(xmax * w) + padding_px)
        px_y1 = min(h, int(ymax * h) + padding_px)

        return img.crop((px_x0, px_y0, px_x1, px_y1))
