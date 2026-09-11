"""
tests/test_multimodal/test_normalized_document.py
Unit tests for NormalizedDocument schema, stable spatial region IDs, RFC 8785 canonical JSON,
and ToolRegistry integration per MMOD-04 and TOOL-01.
"""
from pathlib import Path
import json
import pytest
from PIL import Image

from sovereign.tools.schemas import UserRole
from sovereign.tools.registry import ToolRegistry
from sovereign.tools.builtin.files import PathSecurityViolation
from sovereign.multimodal.ocr import (
    OCRResultBlock,
    DeterministicMockOCRBackend,
    InvalidDocumentError,
)
from sovereign.multimodal.forms import FormFieldType, RawFormField, CheckboxState
from sovereign.multimodal.models import (
    ModalityType,
    DocumentRegion,
    FormField,
    ExtractedTable,
    DocumentPage,
    NormalizedDocument,
)
from sovereign.multimodal.tools import (
    OCR_DOCUMENT_TOOL,
    execute_ocr_document,
    register_multimodal_tools,
)


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Fixture providing an isolated workspace folder."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def sample_inspection_image(temp_workspace: Path) -> Path:
    """Fixture creating a sample inspection PNG image."""
    img_path = temp_workspace / "flange_inspection.png"
    img = Image.new("RGB", (400, 300), color=(255, 255, 255))
    img.save(img_path)
    return img_path


def test_normalized_document_instantiation():
    """Test standard instantiation and field validation of NormalizedDocument hierarchy."""
    region = DocumentRegion(
        region_id="p1-r001",
        box_2d=[0.1, 0.1, 0.2, 0.5],
        text="Shell Thickness: 12.4 mm",
        confidence=0.92,
        modality=ModalityType.PRINTED,
    )

    field = FormField(
        field_id="field-001",
        key="Shell Thickness",
        value="12.4 mm",
        field_type=FormFieldType.NUMBER,
        region_id="p1-r001",
        box_2d=[0.1, 0.1, 0.2, 0.5],
        confidence=0.92,
        is_handwritten=False,
        needs_review=False,
    )

    table = ExtractedTable(
        table_id="tbl-001",
        headers=["Nozzle", "Reading (mm)", "Status"],
        rows=[["N1", "12.2", "PASS"], ["N2", "11.9", "PASS"]],
        box_2d=[0.3, 0.1, 0.6, 0.9],
    )

    page = DocumentPage(
        page_number=1,
        width=400,
        height=300,
        regions=[region],
        form_fields=[field],
        tables=[table],
    )

    doc = NormalizedDocument(
        doc_id="doc-1234567890ab",
        file_name="flange_inspection.png",
        file_sha256="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        total_pages=1,
        pages=[page],
    )

    assert doc.doc_id == "doc-1234567890ab"
    assert doc.total_pages == 1
    assert len(doc.pages) == 1
    assert doc.pages[0].page_number == 1
    assert doc.pages[0].regions[0].region_id == "p1-r001"


def test_region_lookup():
    """Test get_region method on NormalizedDocument."""
    reg1 = DocumentRegion(
        region_id="p1-r001",
        box_2d=[0.1, 0.1, 0.2, 0.5],
        text="Header Text",
        confidence=0.98,
    )
    reg2 = DocumentRegion(
        region_id="p1-r002",
        box_2d=[0.3, 0.1, 0.4, 0.5],
        text="Target Value",
        confidence=0.95,
    )

    page = DocumentPage(
        page_number=1,
        width=400,
        height=300,
        regions=[reg1, reg2],
    )

    doc = NormalizedDocument(
        doc_id="doc-abc",
        file_name="test.png",
        file_sha256="abcdef",
        total_pages=1,
        pages=[page],
    )

    found = doc.get_region(1, "p1-r002")
    assert found is not None
    assert found.text == "Target Value"

    not_found = doc.get_region(1, "p1-r999")
    assert not_found is None


def test_to_canonical_json():
    """Test RFC 8785 canonical JSON serialization."""
    doc = NormalizedDocument(
        doc_id="doc-audit-test",
        file_name="test.png",
        file_sha256="0123456789abcdef",
        total_pages=1,
        pages=[
            DocumentPage(
                page_number=1,
                width=100,
                height=100,
                regions=[
                    DocumentRegion(
                        region_id="p1-r001",
                        box_2d=[0.0, 0.0, 0.1, 0.1],
                        text="Line 1",
                        confidence=0.99,
                    )
                ],
            )
        ],
    )

    canon1 = doc.to_canonical_json()
    canon2 = doc.to_canonical_json()

    assert isinstance(canon1, str)
    assert canon1 == canon2
    # Verify valid JSON round-trip
    parsed = json.loads(canon1)
    assert parsed["doc_id"] == "doc-audit-test"


def test_from_ocr_results_assembly(sample_inspection_image: Path):
    """Test classmethod from_ocr_results assembling blocks and assigning stable IDs."""
    backend = DeterministicMockOCRBackend()
    blocks = backend.extract_text_and_layout(sample_inspection_image)

    raw_fields = [
        RawFormField(
            field_id="field-001",
            key="Shell Thickness",
            value="12.4 mm",
            field_type=FormFieldType.NUMBER,
            box_2d=[0.26, 0.10, 0.30, 0.50],
            confidence=0.92,
            is_handwritten=False,
            needs_review=False,
        )
    ]

    doc = NormalizedDocument.from_ocr_results(
        file_path=sample_inspection_image,
        pages_blocks=[blocks],
        pages_dims=[(400, 300)],
        form_fields_per_page=[raw_fields],
    )

    assert doc.total_pages == 1
    page = doc.pages[0]
    assert page.page_number == 1
    assert page.width == 400
    assert page.height == 300
    assert len(page.regions) == len(blocks)

    # Check stable region IDs format
    for idx, reg in enumerate(page.regions):
        expected_id = f"p1-r{idx + 1:03d}"
        assert reg.region_id == expected_id

    # Check form field region association
    assert len(page.form_fields) == 1
    assert page.form_fields[0].key == "Shell Thickness"
    assert page.form_fields[0].region_id == "p1-r004"  # matches [0.26, 0.10, 0.30, 0.50]


def test_tool_registration_and_rbac(temp_workspace: Path, sample_inspection_image: Path):
    """Test tool registration in ToolRegistry and RBAC clearance enforcement."""
    registry = ToolRegistry()
    register_multimodal_tools(registry, temp_workspace)

    tool_def = registry.get_tool("ocr_document")
    assert tool_def is not None
    assert tool_def.required_role == UserRole.ENGINEER

    # Auditor role should be denied execution
    with pytest.raises(PermissionError, match="does not have sufficient clearance"):
        registry.execute_tool(
            name="ocr_document",
            arguments={"path": "flange_inspection.png", "force_mock": True},
            user_role=UserRole.AUDITOR,
        )

    # Engineer role should be allowed execution
    result = registry.execute_tool(
        name="ocr_document",
        arguments={"path": "flange_inspection.png", "force_mock": True},
        user_role=UserRole.ENGINEER,
    )

    assert result["file_name"] == "flange_inspection.png"
    assert "doc_id" in result
    assert "document" in result
    assert "canonical_json" in result
    assert result["total_pages"] == 1
    assert result["flagged_fields_count"] >= 1
    assert result["hitl_required"] is True
    assert result["hitl_payload"] is not None
    assert result["hitl_payload"]["action"] == "verify_handwriting"


def test_tool_execution_path_security(temp_workspace: Path, tmp_path: Path):
    """Test that ocr_document prevents path traversal outside workspace root."""
    registry = ToolRegistry()
    register_multimodal_tools(registry, temp_workspace)

    outside_img = tmp_path / "secret.png"
    outside_img.write_bytes(b"dummy")

    with pytest.raises(Exception):
        registry.execute_tool(
            name="ocr_document",
            arguments={"path": str(outside_img)},
            user_role=UserRole.ENGINEER,
        )
