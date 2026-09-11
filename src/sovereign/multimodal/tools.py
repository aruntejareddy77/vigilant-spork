"""
src/sovereign/multimodal/tools.py
Tool definitions and execution handlers for offline multimodal document OCR and ingestion.
Implements MMOD-01, MMOD-02, MMOD-04 and tool registry integration.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image

from sovereign.tools.schemas import ToolDefinition, UserRole
from sovereign.tools.registry import ToolRegistry
from sovereign.tools.builtin.files import _resolve_fenced_path
from sovereign.multimodal.ocr import (
    validate_image_file,
    get_ocr_backend,
    OCRResultBlock,
)
from sovereign.multimodal.forms import FormExtractor, build_hitl_interrupt_payload
from sovereign.multimodal.models import NormalizedDocument, DocumentPage, DocumentRegion, FormField


OCR_DOCUMENT_TOOL = ToolDefinition(
    name="ocr_document",
    description=(
        "Ingest and extract text, layout, bounding boxes, and form fields from scanned or "
        "photographed documents offline without external cloud calls."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative or absolute path to document/image file within workspace boundary",
            },
            "force_mock": {
                "type": "boolean",
                "description": "Force pure-Python DeterministicMockOCRBackend",
                "default": False,
            },
        },
        "required": ["path"],
    },
    required_role=UserRole.ENGINEER,
)


def execute_ocr_document(
    path: str,
    workspace_root: Union[str, Path],
    force_mock: bool = False,
) -> Dict[str, Any]:
    """
    Execute offline OCR and form extraction on a document inside workspace boundaries.
    """
    resolved_path = _resolve_fenced_path(workspace_root, path)
    validated_path = validate_image_file(resolved_path, workspace_root=workspace_root)

    backend = get_ocr_backend(force_mock=force_mock)
    form_extractor = FormExtractor()

    suffix = validated_path.suffix.lower()

    if suffix == ".pdf":
        import pypdf
        reader = pypdf.PdfReader(str(validated_path))
        total_pages = len(reader.pages)
        pages_blocks: List[List[OCRResultBlock]] = []
        pages_dims: List[Tuple[int, int]] = []
        form_fields_per_page: List[List[Any]] = []

        for p_idx in range(total_pages):
            page = reader.pages[p_idx]
            # Standard PDF dimensions or fallback
            w = int(float(page.mediabox.width)) if page.mediabox else 1000
            h = int(float(page.mediabox.height)) if page.mediabox else 1000
            pages_dims.append((w, h))

            # In mock or tesseract mode, extract blocks
            blocks = backend.extract_text_and_layout(validated_path)
            pages_blocks.append(blocks)

            fields = form_extractor.extract_fields(blocks)
            form_fields_per_page.append(fields)

    else:
        # Standard image (PNG, JPEG, TIFF, etc.)
        with Image.open(validated_path) as img:
            w, h = img.size
        pages_dims = [(w, h)]

        blocks = backend.extract_text_and_layout(validated_path)
        pages_blocks = [blocks]

        fields = form_extractor.extract_fields(blocks)
        form_fields_per_page = [fields]

    norm_doc = NormalizedDocument.from_ocr_results(
        file_path=validated_path,
        pages_blocks=pages_blocks,
        pages_dims=pages_dims,
        form_fields_per_page=form_fields_per_page,
    )

    # Collect flagged fields requiring HITL review
    flagged_fields = []
    for page in norm_doc.pages:
        for f in page.form_fields:
            if f.needs_review:
                flagged_fields.append(f)

    hitl_required = len(flagged_fields) > 0
    hitl_payload = None
    if hitl_required:
        hitl_payload = {
            "action": "verify_handwriting",
            "doc_id": norm_doc.doc_id,
            "flagged_count": len(flagged_fields),
            "fields": [f.model_dump() for f in flagged_fields],
            "message": (
                f"{len(flagged_fields)} field(s) flagged with confidence below mandatory "
                f"threshold ({form_extractor.confidence_threshold:.2f}). Operator sign-off required."
            ),
        }

    return {
        "doc_id": norm_doc.doc_id,
        "file_name": norm_doc.file_name,
        "file_sha256": norm_doc.file_sha256,
        "total_pages": norm_doc.total_pages,
        "document": norm_doc.model_dump(mode="json"),
        "canonical_json": norm_doc.to_canonical_json(),
        "flagged_fields_count": len(flagged_fields),
        "hitl_required": hitl_required,
        "hitl_payload": hitl_payload,
    }


def register_multimodal_tools(registry: ToolRegistry, workspace_root: Union[str, Path]) -> ToolRegistry:
    """
    Register multimodal tools into ToolRegistry bound to the given workspace root.
    """
    ws_root = Path(workspace_root).resolve()

    registry.register_tool(
        OCR_DOCUMENT_TOOL,
        lambda path, force_mock=False: execute_ocr_document(
            path=path,
            workspace_root=ws_root,
            force_mock=force_mock,
        ),
    )
    return registry
