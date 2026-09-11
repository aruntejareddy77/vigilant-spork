"""
src/sovereign/deliverables/tools.py
Tool definitions and execution handlers for generating native Word, Excel, and PowerPoint
deliverables, registered into the Sovereign ToolRegistry with UserRole.ENGINEER clearance.
Complies with DELV-01, DELV-02, DELV-03, and TOOL-01.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from sovereign.deliverables.docx import DocxDeliverableGenerator
from sovereign.deliverables.xlsx import XlsxDeliverableGenerator
from sovereign.deliverables.pptx import PptxDeliverableGenerator
from sovereign.tools.builtin.files import _resolve_fenced_path
from sovereign.tools.registry import ToolRegistry
from sovereign.tools.schemas import ToolDefinition, UserRole


def register_deliverable_tools(
    registry: ToolRegistry,
    workspace_root: Union[str, Path],
) -> ToolRegistry:
    """
    Registers native deliverable generator tools into the sovereign ToolRegistry.
    All outputs are strictly fenced to workspace_root.
    """
    ws_root = Path(workspace_root).resolve()

    # 1. generate_docx (Engineer)
    registry.register_tool(
        ToolDefinition(
            name="generate_docx",
            description=(
                "Generate a professional Microsoft Word (.docx) approval note with corporate "
                "visual typography, zebra-striped findings table, severity badges, and citation appendix."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "Output path for the .docx deliverable within the workspace",
                    },
                    "title": {
                        "type": "string",
                        "description": "Formal document title",
                    },
                    "facility": {
                        "type": "string",
                        "description": "Operating facility or plant unit name",
                    },
                    "equipment_tag": {
                        "type": "string",
                        "description": "Asset or equipment identification tag (e.g. C-101)",
                    },
                    "findings": {
                        "type": "array",
                        "description": "List of findings dictionaries with item_num, component, observation, measured_value, severity, citation",
                        "items": {"type": "object"},
                    },
                    "citations": {
                        "type": "array",
                        "description": "Optional list of citation dictionaries or Citation models",
                        "items": {"type": "object"},
                    },
                    "classification": {
                        "type": "string",
                        "description": "Classification banner (e.g. INTERNAL, RESTRICTED)",
                        "default": "INTERNAL",
                    },
                    "author": {
                        "type": "string",
                        "description": "Author or engineering role title",
                        "default": "Sovereign Engineering AI",
                    },
                },
                "required": ["output_path", "title", "facility", "equipment_tag", "findings"],
            },
            required_role=UserRole.ENGINEER,
        ),
        lambda output_path, title, facility, equipment_tag, findings, citations=None, classification="INTERNAL", author="Sovereign Engineering AI": (
            str(
                DocxDeliverableGenerator.create_approval_note(
                    output_path=_resolve_fenced_path(ws_root, output_path),
                    title=title,
                    facility=facility,
                    equipment_tag=equipment_tag,
                    findings=findings,
                    citations=citations,
                    classification=classification,
                    author=author,
                    allowed_root=ws_root,
                )
            )
        ),
    )

    # 2. generate_xlsx (Engineer)
    registry.register_tool(
        ToolDefinition(
            name="generate_xlsx",
            description=(
                "Generate a native Microsoft Excel (.xlsx) engineering calculation workbook "
                "featuring live recalculable formulas and 3-tier color-coded cells."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "Output path for the .xlsx workbook within the workspace",
                    },
                    "title": {
                        "type": "string",
                        "description": "Calculation workbook title",
                    },
                    "standard_ref": {
                        "type": "string",
                        "description": "Governing engineering code / standard reference",
                    },
                    "inputs": {
                        "type": "array",
                        "description": "List of input dictionaries (name, symbol, value, unit, notes)",
                        "items": {"type": "object"},
                    },
                    "calculations": {
                        "type": "array",
                        "description": "List of calculation dictionaries (name, symbol, formula_excel, unit, clause)",
                        "items": {"type": "object"},
                    },
                    "conclusion_formula": {
                        "type": "string",
                        "description": "Live Excel formula evaluating compliance (e.g. =IF(C15>=C20, 'PASS', 'FAIL'))",
                    },
                    "facility": {
                        "type": "string",
                        "description": "Optional facility name",
                    },
                    "equipment_tag": {
                        "type": "string",
                        "description": "Optional equipment tag",
                    },
                },
                "required": ["output_path", "title", "standard_ref", "inputs", "calculations", "conclusion_formula"],
            },
            required_role=UserRole.ENGINEER,
        ),
        lambda output_path, title, standard_ref, inputs, calculations, conclusion_formula, facility=None, equipment_tag=None: (
            str(
                XlsxDeliverableGenerator.generate_calculation_workbook(
                    output_path=_resolve_fenced_path(ws_root, output_path),
                    title=title,
                    standard_ref=standard_ref,
                    inputs=inputs,
                    calculations=calculations,
                    conclusion_formula=conclusion_formula,
                    facility=facility,
                    equipment_tag=equipment_tag,
                    allowed_root=ws_root,
                )
            )
        ),
    )

    # 3. generate_pptx (Engineer)
    registry.register_tool(
        ToolDefinition(
            name="generate_pptx",
            description=(
                "Generate an executive Microsoft PowerPoint (.pptx) briefing deck with 16:9 widescreen layout, "
                "bulleted summaries, structured data tables, and native editable OOXML charts."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "Output path for the .pptx presentation within the workspace",
                    },
                    "title": {
                        "type": "string",
                        "description": "Presentation deck title",
                    },
                    "facility": {
                        "type": "string",
                        "description": "Operating facility name",
                    },
                    "slides_content": {
                        "type": "array",
                        "description": "List of slide specifications (summary, table, or chart slides)",
                        "items": {"type": "object"},
                    },
                    "chart_data": {
                        "type": "object",
                        "description": "Optional standalone chart specification (heading, chart_type, categories, series)",
                    },
                    "classification": {
                        "type": "string",
                        "description": "Classification level",
                        "default": "INTERNAL",
                    },
                    "author": {
                        "type": "string",
                        "description": "Presenter or author name",
                        "default": "Sovereign Engineering AI",
                    },
                    "equipment_tag": {
                        "type": "string",
                        "description": "Optional asset tag",
                    },
                },
                "required": ["output_path", "title", "facility", "slides_content"],
            },
            required_role=UserRole.ENGINEER,
        ),
        lambda output_path, title, facility, slides_content, chart_data=None, classification="INTERNAL", author="Sovereign Engineering AI", equipment_tag=None: (
            str(
                PptxDeliverableGenerator.generate_briefing_deck(
                    output_path=_resolve_fenced_path(ws_root, output_path),
                    title=title,
                    facility=facility,
                    slides_content=slides_content,
                    chart_data=chart_data,
                    classification=classification,
                    author=author,
                    equipment_tag=equipment_tag,
                    allowed_root=ws_root,
                )
            )
        ),
    )

    return registry
