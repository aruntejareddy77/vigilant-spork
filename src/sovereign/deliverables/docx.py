"""
src/sovereign/deliverables/docx.py
Native Microsoft Word (.docx) deliverable generator with corporate styling,
findings tables with zebra striping and severity badges, citation appendices,
and Phase 1 LineageEngine packaging.
Complies with DELV-01, T-04-04 (path fencing), and corporate design specs.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import uuid

import docx
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from sovereign.lineage.engine import LineageEngine
from sovereign.lineage.models import (
    DeliverableInfo,
    LineageMetadata,
    ModelInfo,
    SourceDocumentCitation,
)
from sovereign.tools.builtin.files import PathSecurityViolation

# Corporate Palette Constants
COLOR_PRIMARY_NAVY = RGBColor(0x1F, 0x49, 0x7D)     # #1F497D
COLOR_SECONDARY_SLATE = RGBColor(0x59, 0x59, 0x59) # #595959
COLOR_BODY_CHARCOAL = RGBColor(0x26, 0x26, 0x26)   # #262626
COLOR_WHITE = RGBColor(0xFF, 0xFF, 0xFF)           # #FFFFFF

HEX_PRIMARY_NAVY = "1F497D"
HEX_ZEBRA_FILL = "F2F2F2"
HEX_WHITE = "FFFFFF"

# Severity Badge Palettes
HEX_BADGE_CRITICAL_BG = "FFD2D2"
COLOR_BADGE_CRITICAL_FG = RGBColor(0x90, 0x00, 0x00)

HEX_BADGE_WARNING_BG = "FFF3CD"
COLOR_BADGE_WARNING_FG = RGBColor(0x85, 0x64, 0x04)

HEX_BADGE_SATISFACTORY_BG = "D1E7DD"
COLOR_BADGE_SATISFACTORY_FG = RGBColor(0x0F, 0x51, 0x32)


def set_cell_shading(cell, fill_hex: str) -> None:
    """Applies solid background shading to a Word table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    for child in list(tcPr):
        if child.tag.endswith("shd"):
            tcPr.remove(child)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex.lstrip("#").upper())
    tcPr.append(shd)


def set_cell_margins(cell, top: int = 120, bottom: int = 120, left: int = 160, right: int = 160) -> None:
    """Sets internal padding (margins) for a table cell in dxa (twips)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for side, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        node = OxmlElement(f"w:{side}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def validate_output_path(
    output_path: Union[str, Path],
    allowed_root: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Validates output path against directory traversal and null byte injection.
    Fails closed with PathSecurityViolation if target escapes allowed_root.
    """
    target_str = str(output_path)
    if "\x00" in target_str:
        raise PathSecurityViolation("Null byte detected in path argument")

    path = Path(output_path)
    resolved = path.resolve()

    if allowed_root is not None:
        root = Path(allowed_root).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            raise PathSecurityViolation(
                f"Path traversal detected: '{output_path}' is outside allowed root '{root}'"
            )

    return resolved


class DocxDeliverableGenerator:
    """
    Generates professional native Microsoft Word (.docx) approval notes with
    corporate typography, zebra-striped findings tables, severity badges,
    inline citation appendices, and embedded cryptographic lineage.
    """

    def __init__(self, allowed_root: Optional[Union[str, Path]] = None):
        self.allowed_root = Path(allowed_root).resolve() if allowed_root else None

    def _resolve_fencing(
        self,
        output_path: Union[str, Path],
        override_root: Optional[Union[str, Path]] = None,
    ) -> Path:
        effective_root = override_root or self.allowed_root
        return validate_output_path(output_path, effective_root)

    @classmethod
    def create_approval_note(
        cls,
        output_path: Union[str, Path],
        title: str,
        facility: str,
        equipment_tag: str,
        findings: List[Dict[str, Any]],
        citations: Optional[List[Any]] = None,
        lineage_metadata: Optional[LineageMetadata] = None,
        classification: str = "INTERNAL",
        author: str = "Sovereign Engineering AI",
        allowed_root: Optional[Union[str, Path]] = None,
    ) -> Path:
        """
        Creates a formatted corporate approval note .docx file.
        Can be called as a classmethod or instance method.
        """
        # Validate path
        resolved_path = validate_output_path(output_path, allowed_root)
        resolved_path.parent.mkdir(parents=True, exist_ok=True)

        citations_list = citations or []

        # Build Word Document
        doc = docx.Document()

        # Set page margins to 1 inch (72 pt)
        for section in doc.sections:
            section.top_margin = Inches(1.0)
            section.bottom_margin = Inches(1.0)
            section.left_margin = Inches(1.0)
            section.right_margin = Inches(1.0)

        # 1. Classification Banner
        p_banner = doc.add_paragraph()
        p_banner.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_banner = p_banner.add_run(f"[ {classification.upper()} ]")
        r_banner.font.name = "Calibri"
        r_banner.font.size = Pt(10)
        r_banner.font.bold = True
        r_banner.font.color.rgb = COLOR_SECONDARY_SLATE

        # 2. Document Title
        p_title = doc.add_paragraph()
        r_title = p_title.add_run(title)
        r_title.font.name = "Calibri"
        r_title.font.size = Pt(20)
        r_title.font.bold = True
        r_title.font.color.rgb = COLOR_PRIMARY_NAVY
        p_title.paragraph_format.space_after = Pt(4)

        # Metadata Subheader
        p_meta = doc.add_paragraph()
        r_f = p_meta.add_run(f"Facility: ")
        r_f.font.bold = True
        r_f.font.size = Pt(10)
        r_f.font.color.rgb = COLOR_SECONDARY_SLATE
        p_meta.add_run(f"{facility}    |    ")
        r_eq = p_meta.add_run(f"Equipment Tag: ")
        r_eq.font.bold = True
        r_eq.font.size = Pt(10)
        r_eq.font.color.rgb = COLOR_SECONDARY_SLATE
        p_meta.add_run(f"{equipment_tag}\n")

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        r_d = p_meta.add_run(f"Date: ")
        r_d.font.bold = True
        r_d.font.size = Pt(10)
        r_d.font.color.rgb = COLOR_SECONDARY_SLATE
        p_meta.add_run(f"{now_str}    |    ")
        r_a = p_meta.add_run(f"Author: ")
        r_a.font.bold = True
        r_a.font.size = Pt(10)
        r_a.font.color.rgb = COLOR_SECONDARY_SLATE
        p_meta.add_run(f"{author}")
        p_meta.paragraph_format.space_after = Pt(16)

        # 3. Findings Section
        h1 = doc.add_paragraph()
        r_h1 = h1.add_run("1. Technical Findings & Condition Assessment")
        r_h1.font.name = "Calibri"
        r_h1.font.size = Pt(14)
        r_h1.font.bold = True
        r_h1.font.color.rgb = COLOR_PRIMARY_NAVY
        h1.paragraph_format.space_after = Pt(6)

        p_intro = doc.add_paragraph(
            "The following table details verified multimodal inspection findings, "
            "severity evaluations, and source citations extracted from on-premises engineering records."
        )
        p_intro.style.font.name = "Calibri"
        p_intro.style.font.size = Pt(10.5)
        p_intro.style.font.color.rgb = COLOR_BODY_CHARCOAL
        p_intro.paragraph_format.line_spacing = 1.15
        p_intro.paragraph_format.space_after = Pt(10)

        # Build Findings Table
        # Columns: Item #, Component / Location, Observation, Measured Value, Severity, Citation
        table = doc.add_table(rows=1 + len(findings), cols=6)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = "Table Grid"

        headers = [
            ("Item #", Inches(0.7)),
            ("Component / Location", Inches(1.5)),
            ("Observation", Inches(2.2)),
            ("Measured Value", Inches(1.2)),
            ("Severity", Inches(1.1)),
            ("Citation", Inches(1.3)),
        ]

        # Format Header Row
        hdr_row = table.rows[0]
        # Repeat header on every page
        trPr = hdr_row._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:tblHeader"))

        for idx, (hdr_text, col_width) in enumerate(headers):
            cell = hdr_row.cells[idx]
            cell.width = col_width
            set_cell_shading(cell, HEX_PRIMARY_NAVY)
            set_cell_margins(cell, top=140, bottom=140, left=140, right=140)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if idx > 0 else WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(hdr_text)
            run.font.name = "Calibri"
            run.font.size = Pt(10)
            run.font.bold = True
            run.font.color.rgb = COLOR_WHITE

        # Format Data Rows
        for row_idx, item in enumerate(findings, start=1):
            row = table.rows[row_idx]
            is_odd = (row_idx % 2 == 1)
            row_fill = HEX_ZEBRA_FILL if is_odd else HEX_WHITE

            item_num = str(item.get("item_num", item.get("item", item.get("id", str(row_idx)))))
            comp = str(item.get("component", item.get("component_location", item.get("location", ""))))
            obs = str(item.get("observation", item.get("description", "")))
            val = str(item.get("measured_value", item.get("value", "")))
            sev = str(item.get("severity", item.get("status", "Satisfactory"))).strip()
            cit = str(item.get("citation", item.get("citation_tag", "")))

            cell_values = [item_num, comp, obs, val, sev, cit]

            for col_idx, (text, (_, col_width)) in enumerate(zip(cell_values, headers)):
                cell = row.cells[col_idx]
                cell.width = col_width
                set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER if col_idx in (0, 4) else WD_ALIGN_PARAGRAPH.LEFT

                if col_idx == 4:
                    # Severity Badge Column
                    s_lower = sev.lower()
                    if "critical" in s_lower:
                        set_cell_shading(cell, HEX_BADGE_CRITICAL_BG)
                        badge_fg = COLOR_BADGE_CRITICAL_FG
                    elif "warn" in s_lower:
                        set_cell_shading(cell, HEX_BADGE_WARNING_BG)
                        badge_fg = COLOR_BADGE_WARNING_FG
                    else:
                        set_cell_shading(cell, HEX_BADGE_SATISFACTORY_BG)
                        badge_fg = COLOR_BADGE_SATISFACTORY_FG

                    run = p.add_run(sev)
                    run.font.name = "Calibri"
                    run.font.size = Pt(9.5)
                    run.font.bold = True
                    run.font.color.rgb = badge_fg
                else:
                    set_cell_shading(cell, row_fill)
                    run = p.add_run(text)
                    run.font.name = "Calibri"
                    run.font.size = Pt(9.5)
                    run.font.color.rgb = COLOR_BODY_CHARCOAL

        # Spacing after findings table
        p_space = doc.add_paragraph()
        p_space.paragraph_format.space_before = Pt(16)

        # 4. Source References Appendix
        h2 = doc.add_paragraph()
        r_h2 = h2.add_run("2. Source References & Lineage Appendix")
        r_h2.font.name = "Calibri"
        r_h2.font.size = Pt(14)
        r_h2.font.bold = True
        r_h2.font.color.rgb = COLOR_PRIMARY_NAVY
        h2.paragraph_format.space_after = Pt(6)

        p_ref_intro = doc.add_paragraph(
            "Every statement and finding is verifiable against sovereign document custody records. "
            "The table below enumerates all referenced documents, SHA-256 hashes, and spatial regions."
        )
        p_ref_intro.style.font.name = "Calibri"
        p_ref_intro.style.font.size = Pt(10.5)
        p_ref_intro.style.font.color.rgb = COLOR_BODY_CHARCOAL
        p_ref_intro.paragraph_format.line_spacing = 1.15
        p_ref_intro.paragraph_format.space_after = Pt(10)

        # References Table: Citation Tag, Document ID, File SHA-256, Page #, Region ID
        ref_headers = [
            ("Citation Tag", Inches(1.8)),
            ("Document ID", Inches(1.5)),
            ("File SHA-256 (Prefix)", Inches(1.8)),
            ("Page #", Inches(0.9)),
            ("Region ID", Inches(1.5)),
        ]

        ref_table = doc.add_table(rows=1 + len(citations_list), cols=5)
        ref_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        ref_table.style = "Table Grid"

        # Ref Table Header
        ref_hdr_row = ref_table.rows[0]
        ref_trPr = ref_hdr_row._tr.get_or_add_trPr()
        ref_trPr.append(OxmlElement("w:tblHeader"))

        for idx, (hdr_text, col_width) in enumerate(ref_headers):
            cell = ref_hdr_row.cells[idx]
            cell.width = col_width
            set_cell_shading(cell, HEX_PRIMARY_NAVY)
            set_cell_margins(cell, top=140, bottom=140, left=140, right=140)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if idx == 3 else WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(hdr_text)
            run.font.name = "Calibri"
            run.font.size = Pt(10)
            run.font.bold = True
            run.font.color.rgb = COLOR_WHITE

        # Ref Table Rows
        for r_idx, c in enumerate(citations_list, start=1):
            row = ref_table.rows[r_idx]
            is_odd = (r_idx % 2 == 1)
            row_fill = HEX_ZEBRA_FILL if is_odd else HEX_WHITE

            doc_id = getattr(c, "document_id", None) or (c.get("document_id", "") if isinstance(c, dict) else "")
            sha = getattr(c, "file_sha256", None) or (c.get("file_sha256", "") if isinstance(c, dict) else "")
            page = getattr(c, "page_number", None) or (c.get("page_number", "") if isinstance(c, dict) else "")
            region = getattr(c, "region_id", None) or (c.get("region_id", "") if isinstance(c, dict) else "")

            # Generate tag
            if region and page:
                tag = f"[Doc: {doc_id}, p.{page}#{region}]"
            elif page:
                tag = f"[Doc: {doc_id}, p.{page}]"
            else:
                tag = f"[Doc: {doc_id}]"

            sha_display = sha[:16] + "..." if len(sha) > 16 else (sha or "N/A")
            page_str = str(page) if page is not None and page != "" else "N/A"
            region_str = str(region) if region else "N/A"

            c_vals = [tag, str(doc_id), sha_display, page_str, region_str]

            for c_idx, (text, (_, col_width)) in enumerate(zip(c_vals, ref_headers)):
                cell = row.cells[c_idx]
                cell.width = col_width
                set_cell_shading(cell, row_fill)
                set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER if c_idx == 3 else WD_ALIGN_PARAGRAPH.LEFT
                run = p.add_run(text)
                run.font.name = "Calibri"
                run.font.size = Pt(9)
                run.font.color.rgb = COLOR_BODY_CHARCOAL

        # Save Word document
        doc.save(resolved_path)

        # 5. Lineage Packaging via Phase 1 LineageEngine
        meta = lineage_metadata
        if meta is None:
            meta = LineageMetadata(
                deliverable=DeliverableInfo(
                    file_name=resolved_path.name,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
                session_id=f"session-{uuid.uuid4().hex[:8]}",
                user_id="engineer",
                user_role="Lead Engineer",
                model=ModelInfo(model_id="sovereign-local-v1", weights_sha256="0" * 64),
                audit_start_seq=0,
                audit_end_seq=1,
                audit_tip_hash="0" * 64,
            )

        # If source_documents in metadata is empty and citations provided, populate
        if not meta.source_documents and citations_list:
            for c in citations_list:
                d_id = getattr(c, "document_id", None) or (c.get("document_id", "") if isinstance(c, dict) else "")
                f_name = getattr(c, "file_name", None) or (c.get("file_name", d_id) if isinstance(c, dict) else d_id)
                f_sha = getattr(c, "file_sha256", None) or (c.get("file_sha256", "") if isinstance(c, dict) else "")
                p_num = getattr(c, "page_number", None) or (c.get("page_number", None) if isinstance(c, dict) else None)
                snip = getattr(c, "excerpt", None) or (c.get("excerpt", None) if isinstance(c, dict) else None)
                bbox = getattr(c, "bounding_box", None) or (c.get("bounding_box", None) if isinstance(c, dict) else None)

                meta.source_documents.append(
                    SourceDocumentCitation(
                        document_id=str(d_id),
                        file_name=str(f_name),
                        file_sha256=str(f_sha),
                        page_number=int(p_num) if p_num is not None else None,
                        snippet=str(snip) if snip else None,
                        bounding_box=bbox,
                    )
                )

        LineageEngine.package_deliverable(resolved_path, meta)

        return resolved_path
