"""
src/sovereign/vision/overlay.py
Visual Annotation Overlay Renderer for Engineering Drawings and P&IDs.
Renders industrial standard color-coded bounding contours (Green/Red/Amber),
solid numbered circular badges, drafting title block with legend, and
embeds cryptographic W3C PROV-O lineage via LineageEngine.
Complies with MMOD-03, T-04-04 (Path Fencing), and ASVS V5.1/V10.3.
"""
from pathlib import Path
from typing import List, Optional, Union
import uuid
from PIL import Image, ImageDraw, ImageFont

from sovereign.deliverables.docx import validate_output_path
from sovereign.lineage.engine import LineageEngine
from sovereign.lineage.models import DeliverableInfo, LineageMetadata, ModelInfo
from sovereign.vision.diff import DiffBoundingBox, DiffChangeType


class VisualOverlayRenderer:
    """
    Renders high-contrast visual revision overlays on engineering drawings
    according to industrial drafting conventions.
    """

    COLOR_ADDED = (0, 200, 83)       # Vivid Green (#00C853)
    COLOR_REMOVED = (213, 0, 0)      # Vivid Red (#D50000)
    COLOR_MODIFIED = (255, 214, 0)   # Vivid Amber (#FFD600)

    COLOR_MAP = {
        DiffChangeType.ADDED: COLOR_ADDED,
        DiffChangeType.REMOVED: COLOR_REMOVED,
        DiffChangeType.MODIFIED: COLOR_MODIFIED,
        "ADDED": COLOR_ADDED,
        "REMOVED": COLOR_REMOVED,
        "MODIFIED": COLOR_MODIFIED,
    }

    @classmethod
    def render_diff_overlay(
        cls,
        img_b_path: Union[str, Path],
        diff_boxes: List[DiffBoundingBox],
        output_path: Union[str, Path],
        drawing_title: str = "P&ID Revision Comparison",
        allowed_root: Optional[Union[str, Path]] = None,
        lineage_metadata: Optional[LineageMetadata] = None,
    ) -> Path:
        """
        Renders a high-contrast visual difference overlay on Rev B.

        Args:
            img_b_path: Path to updated drawing revision (Rev B).
            diff_boxes: Detected DiffBoundingBox list from DrawingDiffEngine.
            output_path: Output PNG image path.
            drawing_title: Name/title of drawing to display in title block.
            allowed_root: Optional security boundary directory for path traversal fencing.
            lineage_metadata: Optional W3C PROV-O metadata; generated if omitted.

        Returns:
            Resolved Path to the saved overlay deliverable.
        """
        # Path validation and directory traversal prevention (Threat T-04-04)
        resolved_output = validate_output_path(output_path, allowed_root)
        resolved_output.parent.mkdir(parents=True, exist_ok=True)

        # Load Rev B image
        path_b = Path(img_b_path).resolve()
        if not path_b.exists():
            raise FileNotFoundError(f"Base drawing image not found: {path_b}")

        im_b = Image.open(path_b).convert("RGB")
        w, h = im_b.size

        # 1. Desaturate base image and blend with medium gray (#808080) for high-contrast visibility
        gray = im_b.convert("L").convert("RGB")
        base = Image.blend(gray, Image.new("RGB", gray.size, (128, 128, 128)), alpha=0.35)

        # 2. Prepare RGBA overlay canvas for alpha blending
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay, "RGBA")

        font = ImageFont.load_default()

        # Dynamic badge radius scaled to image size
        badge_radius = max(12, min(24, int(min(w, h) * 0.018)))

        # 3. Render color-coded bounding boxes and callout badges
        for box in diff_boxes:
            ymin, xmin, ymax, xmax = box.box_2d
            x0 = max(0, min(w - 1, int(xmin * w)))
            y0 = max(0, min(h - 1, int(ymin * h)))
            x1 = max(x0 + 1, min(w, int(xmax * w)))
            y1 = max(y0 + 1, min(h, int(ymax * h)))

            color = cls.COLOR_MAP.get(box.change_type, cls.COLOR_MODIFIED)
            fill_color = color + (38,)    # ~15% translucent color wash
            outline_color = color + (255,)  # Solid outline

            # Render 3-pixel bounding box with fill
            draw.rectangle([x0, y0, x1, y1], fill=fill_color, outline=outline_color, width=3)

            # Render numbered circular callout badge at top-left corner
            badge_cx = max(badge_radius, min(w - badge_radius, x0))
            badge_cy = max(badge_radius, min(h - badge_radius, y0))

            # Solid badge circle with white border
            draw.ellipse(
                [
                    badge_cx - badge_radius,
                    badge_cy - badge_radius,
                    badge_cx + badge_radius,
                    badge_cy + badge_radius,
                ],
                fill=outline_color,
                outline=(255, 255, 255, 255),
                width=2,
            )

            # Centered white badge number text
            badge_num = str(box.box_id)
            tb = font.getbbox(badge_num)
            tw = tb[2] - tb[0]
            th = tb[3] - tb[1]
            draw.text(
                (badge_cx - tw / 2.0, badge_cy - th / 2.0 - 1),
                badge_num,
                fill=(255, 255, 255, 255),
                font=font,
            )

        # 4. Render engineering title block with legend in bottom-right corner
        tb_w = min(360, max(240, int(w * 0.45)))
        tb_h = min(120, max(85, int(h * 0.25)))
        margin = max(10, min(20, int(min(w, h) * 0.02)))

        tb_x0 = max(0, w - tb_w - margin)
        tb_y0 = max(0, h - tb_h - margin)
        tb_x1 = w - margin
        tb_y1 = h - margin

        if tb_x1 > tb_x0 and tb_y1 > tb_y0:
            # Semi-opaque light slate background with dark border
            draw.rectangle(
                [tb_x0, tb_y0, tb_x1, tb_y1],
                fill=(245, 247, 250, 240),
                outline=(30, 41, 59, 255),
                width=2,
            )
            # Navy title header bar
            header_h = min(26, max(18, tb_h // 4))
            draw.rectangle([tb_x0, tb_y0, tb_x1, tb_y0 + header_h], fill=(30, 41, 59, 255))

            # Header text
            title_text = drawing_title if len(drawing_title) <= 35 else drawing_title[:32] + "..."
            draw.text((tb_x0 + 8, tb_y0 + 4), title_text, fill=(255, 255, 255, 255), font=font)

            # Subheader & statistics
            text_y1 = tb_y0 + header_h + 6
            draw.text(
                (tb_x0 + 8, text_y1),
                f"Diff Engine: {len(diff_boxes)} identified changes",
                fill=(15, 23, 42, 255),
                font=font,
            )

            # Separator rule
            rule_y = text_y1 + 18
            draw.line([(tb_x0 + 8, rule_y), (tb_x1 - 8, rule_y)], fill=(203, 213, 225, 255), width=1)

            # Legend swatches
            legend_y = rule_y + 8
            swatch_w, swatch_h = 14, 10
            spacing = (tb_x1 - tb_x0 - 16) // 3

            # Swatch 1: Added
            s1_x = tb_x0 + 8
            draw.rectangle(
                [s1_x, legend_y, s1_x + swatch_w, legend_y + swatch_h],
                fill=cls.COLOR_ADDED + (255,),
                outline=(0, 0, 0, 255),
                width=1,
            )
            draw.text((s1_x + swatch_w + 4, legend_y), "Added", fill=(15, 23, 42, 255), font=font)

            # Swatch 2: Removed
            s2_x = tb_x0 + 8 + spacing
            draw.rectangle(
                [s2_x, legend_y, s2_x + swatch_w, legend_y + swatch_h],
                fill=cls.COLOR_REMOVED + (255,),
                outline=(0, 0, 0, 255),
                width=1,
            )
            draw.text((s2_x + swatch_w + 4, legend_y), "Removed", fill=(15, 23, 42, 255), font=font)

            # Swatch 3: Modified
            s3_x = tb_x0 + 8 + spacing * 2
            draw.rectangle(
                [s3_x, legend_y, s3_x + swatch_w, legend_y + swatch_h],
                fill=cls.COLOR_MODIFIED + (255,),
                outline=(0, 0, 0, 255),
                width=1,
            )
            draw.text((s3_x + swatch_w + 4, legend_y), "Modified", fill=(15, 23, 42, 255), font=font)

        # 5. Alpha composite overlay over base image and convert to RGB
        final_img = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
        final_img.save(resolved_output, format="PNG")

        # 6. Inject cryptographic W3C PROV-O lineage metadata into PNG chunks
        meta = lineage_metadata
        if meta is None:
            meta = LineageMetadata(
                deliverable=DeliverableInfo(
                    file_name=resolved_output.name,
                    media_type="image/png",
                ),
                session_id=f"session-{uuid.uuid4().hex[:8]}",
                user_id="engineer",
                user_role="Lead Engineer",
                model=ModelInfo(model_id="sovereign-vision-diff-v1", weights_sha256="0" * 64),
                audit_start_seq=0,
                audit_end_seq=1,
                audit_tip_hash="0" * 64,
                custom_attributes={
                    "drawing_title": drawing_title,
                    "diff_boxes_count": len(diff_boxes),
                    "base_drawing": str(path_b.name),
                },
            )

        LineageEngine.package_deliverable(resolved_output, meta)

        return resolved_output
