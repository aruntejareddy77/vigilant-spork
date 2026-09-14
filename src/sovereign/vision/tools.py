"""
src/sovereign/vision/tools.py
Agentic Tool Definition and Handler for Engineering Drawing / P&ID Revision Comparison.
Registers `diff_drawings` tool in the sovereign ToolRegistry with UserRole.ENGINEER clearance.
Complies with MMOD-03, T-04-03, and T-04-04.
"""
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from sovereign.deliverables.docx import validate_output_path
from sovereign.models.adapter import BaseModelAdapter
from sovereign.tools.registry import ToolRegistry
from sovereign.tools.schemas import ToolDefinition, UserRole
from sovereign.vision.diff import DrawingDiffEngine
from sovereign.vision.overlay import VisualOverlayRenderer
from sovereign.vision.register import ChangeRegisterGenerator

DIFF_DRAWINGS_TOOL_DEF = ToolDefinition(
    name="diff_drawings",
    description=(
        "Compare two revisions of an engineering drawing or P&ID schematic. "
        "Executes dual-layer differencing: Layer 1 pixel differencing and bounding contour clustering, "
        "and Layer 2 semantic vision-language reasoning. Renders a color-coded visual overlay deliverable "
        "(Green for Added, Red for Removed, Amber for Modified) with numbered callouts and emits a structured Change Register report."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "rev_a_path": {
                "type": "string",
                "description": "File path to baseline engineering drawing (Revision A)",
            },
            "rev_b_path": {
                "type": "string",
                "description": "File path to updated engineering drawing (Revision B)",
            },
            "output_overlay_path": {
                "type": "string",
                "description": "Output path for the generated visual difference overlay PNG",
            },
            "output_report_path": {
                "type": "string",
                "description": "Optional output path for change register report (.docx, .md, or .json)",
            },
            "drawing_title": {
                "type": "string",
                "description": "Optional engineering drawing title or equipment identifier",
                "default": "P&ID Revision Comparison",
            },
            "sensitivity": {
                "type": "integer",
                "description": "Pixel luminance differencing sensitivity threshold (1-255, default 30)",
                "default": 30,
            },
        },
        "required": ["rev_a_path", "rev_b_path", "output_overlay_path"],
    },
    required_role=UserRole.ENGINEER,
)


def handle_diff_drawings(
    rev_a_path: str,
    rev_b_path: str,
    output_overlay_path: str,
    output_report_path: Optional[str] = None,
    drawing_title: str = "P&ID Revision Comparison",
    sensitivity: int = 30,
    model_adapter: Optional[BaseModelAdapter] = None,
    workspace_root: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Executes drawing revision comparison workflow:
    1. Layer 1: Detects bounding boxes with DrawingDiffEngine.
    2. Renders high-contrast visual overlay via VisualOverlayRenderer.
    3. Layer 2: Analyzes differences semantically via ChangeRegisterGenerator.
    4. Exports optional Change Register (.docx, .md, or .json) report.
    5. Returns structured change register summary.
    """
    ws_root = Path(workspace_root).resolve() if workspace_root else None

    # Resolve input paths
    path_a = Path(rev_a_path)
    if ws_root and not path_a.is_absolute():
        path_a = ws_root / path_a
    path_a = path_a.resolve()

    path_b = Path(rev_b_path)
    if ws_root and not path_b.is_absolute():
        path_b = ws_root / path_b
    path_b = path_b.resolve()

    # Resolve output overlay path
    path_overlay = Path(output_overlay_path)
    if ws_root and not path_overlay.is_absolute():
        path_overlay = ws_root / path_overlay
    resolved_overlay = validate_output_path(path_overlay, ws_root)

    # 1. Layer 1 differencing
    diff_boxes = DrawingDiffEngine.compare_revisions(
        path_a,
        path_b,
        sensitivity=sensitivity,
    )

    # 2. Visual overlay rendering
    VisualOverlayRenderer.render_diff_overlay(
        img_b_path=path_b,
        diff_boxes=diff_boxes,
        output_path=resolved_overlay,
        drawing_title=drawing_title,
        allowed_root=ws_root,
    )

    # 3. Layer 2 semantic change register generation
    register = ChangeRegisterGenerator.generate_register(
        diff_boxes=diff_boxes,
        model_adapter=model_adapter,
        img_a_path=path_a,
        img_b_path=path_b,
        drawing_title=drawing_title,
    )

    # 4. Optional Change Register report export
    resolved_report = None
    if output_report_path:
        path_rep = Path(output_report_path)
        if ws_root and not path_rep.is_absolute():
            path_rep = ws_root / path_rep
        resolved_report = validate_output_path(path_rep, ws_root)
        resolved_report.parent.mkdir(parents=True, exist_ok=True)

        ext = resolved_report.suffix.lower()
        if ext == ".docx":
            ChangeRegisterGenerator.export_word_table(register, resolved_report, allowed_root=ws_root)
        elif ext in [".md", ".txt"]:
            md_content = ChangeRegisterGenerator.export_markdown(register)
            resolved_report.write_text(md_content, encoding="utf-8")
        elif ext == ".json":
            resolved_report.write_text(register.model_dump_json(indent=2), encoding="utf-8")
        else:
            # Default to markdown
            md_content = ChangeRegisterGenerator.export_markdown(register)
            resolved_report.write_text(md_content, encoding="utf-8")

    markdown_summary = ChangeRegisterGenerator.export_markdown(register)

    return {
        "status": "success",
        "drawing_title": drawing_title,
        "total_changes": len(diff_boxes),
        "overlay_path": str(resolved_overlay),
        "report_path": str(resolved_report) if resolved_report else None,
        "items": [item.model_dump() for item in register.items],
        "markdown": markdown_summary,
    }


def register_vision_tools(
    registry: ToolRegistry,
    model_adapter: Optional[BaseModelAdapter] = None,
    workspace_root: Optional[Union[str, Path]] = None,
) -> ToolRegistry:
    """
    Registers sovereign vision and drawing comparison tools into the given ToolRegistry.
    """
    ws_root = Path(workspace_root).resolve() if workspace_root else None

    def handler_wrapper(
        rev_a_path: str,
        rev_b_path: str,
        output_overlay_path: str,
        output_report_path: Optional[str] = None,
        drawing_title: str = "P&ID Revision Comparison",
        sensitivity: int = 30,
    ) -> Dict[str, Any]:
        return handle_diff_drawings(
            rev_a_path=rev_a_path,
            rev_b_path=rev_b_path,
            output_overlay_path=output_overlay_path,
            output_report_path=output_report_path,
            drawing_title=drawing_title,
            sensitivity=sensitivity,
            model_adapter=model_adapter,
            workspace_root=ws_root,
        )

    registry.register_tool(DIFF_DRAWINGS_TOOL_DEF, handler_wrapper)
    return registry
