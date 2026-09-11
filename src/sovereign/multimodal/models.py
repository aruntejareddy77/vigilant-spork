"""
src/sovereign/multimodal/models.py
Normalized Multimodal Document representation preserving spatial coordinates and stable region IDs.
Implements MMOD-04 and RFC 8785 canonical JSON serialization.
"""
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image
import rfc8785
from pydantic import BaseModel, ConfigDict, Field

from sovereign.multimodal.ocr import OCRResultBlock
from sovereign.multimodal.forms import FormFieldType, RawFormField, CheckboxState


class ModalityType(str, Enum):
    """Semantic modality classification for a document region."""
    PRINTED = "printed"
    HANDWRITTEN = "handwritten"
    TABLE = "table"
    SCHEMATIC = "schematic"


class DocumentRegion(BaseModel):
    """
    Atomic document region with normalized 2D bounding coordinates and stable ID.
    """
    model_config = ConfigDict(extra="allow")

    region_id: str = Field(description="Stable identifier formatted as p{page}-r{idx:03d}")
    box_2d: List[float] = Field(description="Normalized coordinates [ymin, xmin, ymax, xmax] in [0.0, 1.0]")
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    modality: ModalityType = ModalityType.PRINTED


class FormField(BaseModel):
    """
    Normalized form field embedded within a document page.
    """
    model_config = ConfigDict(extra="allow")

    field_id: str
    key: str
    value: Any
    field_type: Union[FormFieldType, str]
    region_id: Optional[str] = None
    box_2d: Optional[List[float]] = None
    confidence: float = Field(ge=0.0, le=1.0)
    is_handwritten: bool = False
    needs_review: bool = False
    review_reason: Optional[str] = None


class ExtractedTable(BaseModel):
    """
    Tabular structure extracted from a document page.
    """
    model_config = ConfigDict(extra="allow")

    table_id: str
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    box_2d: Optional[List[float]] = None


class DocumentPage(BaseModel):
    """
    Normalized representation of a single document page.
    """
    model_config = ConfigDict(extra="allow")

    page_number: int = Field(ge=1, description="1-indexed page number")
    width: int = Field(ge=1, description="Page width in pixels or points")
    height: int = Field(ge=1, description="Page height in pixels or points")
    regions: List[DocumentRegion] = Field(default_factory=list)
    form_fields: List[FormField] = Field(default_factory=list)
    tables: List[ExtractedTable] = Field(default_factory=list)


class NormalizedDocument(BaseModel):
    """
    Unified canonical representation of ingested multimodal documents.
    Preserves 1-indexed pages, normalized 2D coordinates, and stable region IDs.
    """
    model_config = ConfigDict(extra="allow")

    doc_id: str = Field(description="Unique document identifier, doc-{sha256[:12]}")
    file_name: str
    file_sha256: str
    total_pages: int = Field(ge=1)
    pages: List[DocumentPage] = Field(default_factory=list)

    def get_region(self, page_num: int, region_id: str) -> Optional[DocumentRegion]:
        """
        Lookup a specific document region by page number and region identifier.
        """
        for page in self.pages:
            if page.page_number == page_num:
                for region in page.regions:
                    if region.region_id == region_id:
                        return region

        # Fallback search across all pages if page_num didn't match
        for page in self.pages:
            for region in page.regions:
                if region.region_id == region_id:
                    return region
        return None

    def to_canonical_json(self) -> str:
        """
        Serialize document into canonical RFC 8785 JSON representation
        for zero-tamper cryptographic audit logs.
        """
        raw_dict = json.loads(self.model_dump_json())
        canonical_bytes = rfc8785.dumps(raw_dict)
        return canonical_bytes.decode("utf-8")

    @classmethod
    def from_ocr_results(
        cls,
        file_path: Union[str, Path],
        pages_blocks: List[List[OCRResultBlock]],
        pages_dims: Optional[List[Tuple[int, int]]] = None,
        form_fields_per_page: Optional[List[List[Union[RawFormField, FormField]]]] = None,
        tables_per_page: Optional[List[List[ExtractedTable]]] = None,
    ) -> "NormalizedDocument":
        """
        Assemble OCR result blocks, form fields, and tables into a canonical NormalizedDocument.
        Generates stable region IDs formatted as p{page_num}-r{idx:03d}.
        """
        path = Path(file_path).resolve()
        with open(path, "rb") as f:
            content_bytes = f.read()

        file_sha256 = hashlib.sha256(content_bytes).hexdigest()
        doc_id = f"doc-{file_sha256[:12]}"
        total_pages = len(pages_blocks)

        pages: List[DocumentPage] = []

        for p_idx, blocks in enumerate(pages_blocks):
            page_num = p_idx + 1

            if pages_dims and p_idx < len(pages_dims):
                width, height = pages_dims[p_idx]
            else:
                width, height = 1000, 1000

            # Generate stable DocumentRegion items
            regions: List[DocumentRegion] = []
            for r_idx, block in enumerate(blocks):
                reg_id = f"p{page_num}-r{r_idx + 1:03d}"
                modality = ModalityType.PRINTED
                if block.block_type == "handwritten":
                    modality = ModalityType.HANDWRITTEN
                elif block.block_type == "table":
                    modality = ModalityType.TABLE
                elif block.block_type == "schematic":
                    modality = ModalityType.SCHEMATIC

                regions.append(
                    DocumentRegion(
                        region_id=reg_id,
                        box_2d=block.box_2d,
                        text=block.text,
                        confidence=block.confidence,
                        modality=modality,
                    )
                )

            # Map form fields
            page_form_fields: List[FormField] = []
            if form_fields_per_page and p_idx < len(form_fields_per_page):
                for f_item in form_fields_per_page[p_idx]:
                    if isinstance(f_item, FormField):
                        page_form_fields.append(f_item)
                    elif isinstance(f_item, RawFormField):
                        # Find closest region if box_2d matches
                        matching_reg_id = None
                        for reg in regions:
                            if reg.box_2d == f_item.box_2d:
                                matching_reg_id = reg.region_id
                                break

                        val = f_item.value.value if isinstance(f_item.value, Enum) else f_item.value
                        page_form_fields.append(
                            FormField(
                                field_id=f_item.field_id,
                                key=f_item.key,
                                value=val,
                                field_type=f_item.field_type,
                                region_id=matching_reg_id,
                                box_2d=f_item.box_2d,
                                confidence=f_item.confidence,
                                is_handwritten=f_item.is_handwritten,
                                needs_review=f_item.needs_review,
                                review_reason=f_item.review_reason,
                            )
                        )

            # Map tables
            page_tables: List[ExtractedTable] = []
            if tables_per_page and p_idx < len(tables_per_page):
                page_tables.extend(tables_per_page[p_idx])

            pages.append(
                DocumentPage(
                    page_number=page_num,
                    width=width,
                    height=height,
                    regions=regions,
                    form_fields=page_form_fields,
                    tables=page_tables,
                )
            )

        return cls(
            doc_id=doc_id,
            file_name=path.name,
            file_sha256=file_sha256,
            total_pages=total_pages,
            pages=pages,
        )
