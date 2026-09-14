"""
tests/test_demos/test_demo_a.py
End-to-End Automated Integration Test Suite for Demo Workflow A (Approval Note / DEMO-01).
Tests scanned inspection report ingestion, OCR extraction, confidence thresholding,
Human-in-the-Loop (HITL) review gate, and styled Word (.docx) export with scan citations.
"""
import hashlib
from pathlib import Path
import docx
import pytest
from PIL import Image

from sovereign.audit.ledger import AuditLedger
from sovereign.deliverables.docx import DocxDeliverableGenerator
from sovereign.lineage.models import SourceDocumentCitation
from sovereign.multimodal.forms import CheckboxState, FormExtractor, RawFormField
from sovereign.multimodal.ocr import (
    DeterministicMockOCRBackend,
    InvalidDocumentError,
    OCRResultBlock,
    validate_image_file,
)


def test_demo_a_image_safety(samples_dir: Path, tmp_path: Path):
    """
    Validates samples/refinery_vessel_inspection_v301.png against decompression bomb
    and file boundary ceilings per ASVS V5.1.3 and Threat T-06-03.
    Also validates that an oversized synthetic buffer is rejected.
    """
    scan_path = samples_dir / "refinery_vessel_inspection_v301.png"
    assert scan_path.exists(), f"Sample inspection scan missing at {scan_path}"

    # Valid scan passes validation cleanly
    validated_path = validate_image_file(scan_path)
    assert validated_path.exists()
    assert validated_path.is_file()

    # Rejection of oversized synthetic buffer (>50MB)
    fake_huge_file = tmp_path / "huge_decompression_bomb.png"
    with open(fake_huge_file, "wb") as f:
        f.seek(51 * 1024 * 1024)
        f.write(b"\x00")

    with pytest.raises(InvalidDocumentError, match="exceeds maximum allowed"):
        validate_image_file(fake_huge_file)


def test_demo_a_ocr_and_thresholding(samples_dir: Path):
    """
    Validates OCR extraction and structured form extraction with confidence thresholding:
    - DeterministicMockOCRBackend produces normalized bounding boxes in [0.0, 1.0].
    - FormExtractor(confidence_threshold=0.85) processes fields.
    - Printed findings (e.g. Shell Course 1, Facility) have confidence >= 0.85 and needs_review=False.
    - Handwritten finding (Nozzle N-2 pitting) has confidence < 0.85 (0.78) and needs_review=True.
    """
    scan_path = samples_dir / "refinery_vessel_inspection_v301.png"
    backend = DeterministicMockOCRBackend()
    blocks = backend.extract_text_and_layout(scan_path)

    assert len(blocks) >= 5, f"Expected at least 5 layout blocks, got {len(blocks)}"

    # Check normalized coordinate invariants
    for block in blocks:
        ymin, xmin, ymax, xmax = block.box_2d
        assert 0.0 <= ymin < ymax <= 1.0, f"Invalid vertical bounds: {block.box_2d}"
        assert 0.0 <= xmin < xmax <= 1.0, f"Invalid horizontal bounds: {block.box_2d}"
        assert 0.0 <= block.confidence <= 1.0

    extractor = FormExtractor(confidence_threshold=0.85)
    fields = extractor.extract_fields(blocks)
    assert len(fields) >= 3, f"Expected extracted fields, got {len(fields)}"

    # Separate approved fields from review-flagged fields
    reviewed_fields = [f for f in fields if f.needs_review]
    approved_fields = [f for f in fields if not f.needs_review]

    assert len(reviewed_fields) >= 1, "Expected at least 1 field flagged for review"

    # Verify handwritten finding triggered the gate
    hw_field = next((f for f in reviewed_fields if "nozzle n-2" in f.key.lower() or "pitting" in f.key.lower()), None)
    assert hw_field is not None, f"Handwritten pitting finding not flagged in {reviewed_fields}"
    assert hw_field.confidence < 0.85, f"Expected sub-0.85 confidence, got {hw_field.confidence}"
    assert hw_field.confidence == 0.78
    assert hw_field.needs_review is True
    assert "below mandatory threshold 0.85" in (hw_field.review_reason or "")
    assert hw_field.is_handwritten is True

    # Verify printed fields pass without review
    shell_field = next((f for f in approved_fields if "shell course" in f.key.lower()), None)
    assert shell_field is not None, f"Shell course field missing from approved fields: {approved_fields}"
    assert shell_field.confidence >= 0.85
    assert shell_field.needs_review is False


def test_demo_a_hitl_approval_and_docx_export(samples_dir: Path, tmp_path: Path):
    """
    Validates end-to-end Demo A completion:
    - HITL gate payload construction and state transition (APPROVAL_REQUIRED -> APPROVAL_GRANTED).
    - DocxDeliverableGenerator creates corporate Word approval note in isolated output dir.
    - Document includes corporate header, 6-column table, zebra striping, severity badges, and citation doc-v301#p1-r004.
    - Embedded W3C PROV-O lineage sidecar is verified.
    """
    scan_path = samples_dir / "refinery_vessel_inspection_v301.png"
    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    docx_path = out_dir / "Refinery_Inspection_Approval_Note.docx"

    backend = DeterministicMockOCRBackend()
    blocks = backend.extract_text_and_layout(scan_path)
    extractor = FormExtractor(confidence_threshold=0.85)
    fields = extractor.extract_fields(blocks)

    flagged = [f for f in fields if f.needs_review]
    assert len(flagged) == 1

    # 1. State machine HITL Gate: Build interrupt payload
    interrupt_payload = extractor.build_hitl_interrupt_payload(flagged, doc_id="doc-v301", page_num=1)
    assert interrupt_payload["action"] == "verify_handwriting"
    assert interrupt_payload["flagged_count"] == 1
    assert interrupt_payload["fields"][0]["confidence"] == 0.78

    # 2. Simulate Audit Ledger recording HITL pause and operator approval
    audit_file = tmp_path / "audit_ledger.jsonl"
    ledger = AuditLedger(ledger_path=audit_file)

    # Record APPROVAL_REQUIRED event
    event_req = ledger.append_event(
        session_id="session-demo-a-001",
        event_type="APPROVAL_REQUIRED",
        actor_role="system:state_machine",
        payload={
            "task_id": "task-demo-a-001",
            "reason": "Low confidence handwriting detection",
            "citation": "doc-v301#p1-r004",
            "confidence": 0.78,
        },
    )
    assert event_req.seq_num == 0

    # Simulate operator sign-off (Lead NDT Engineer)
    event_grant = ledger.append_event(
        session_id="session-demo-a-001",
        event_type="APPROVAL_GRANTED",
        actor_role="user:lead_engineer",
        payload={
            "task_id": "task-demo-a-001",
            "decision": "APPROVED",
            "citation": "doc-v301#p1-r004",
            "operator_notes": "Ultrasonic phased array verification scheduled per ASME Sec VIII Div 1",
        },
    )
    assert event_grant.seq_num == 1

    # 3. Assemble findings and citations for deliverable generation
    with open(scan_path, "rb") as f:
        scan_sha256 = hashlib.sha256(f.read()).hexdigest()

    findings = [
        {
            "item_num": "1",
            "component": "Shell Course 1 (Lower)",
            "observation": "Nominal ultrasonic thickness verified across 12-point grid",
            "measured_value": "12.4 mm",
            "severity": "SATISFACTORY",
            "citation": "doc-v301#p1-r001",
        },
        {
            "item_num": "2",
            "component": "Nozzle N-2 Weld Zone",
            "observation": "Localized pitting observed at nozzle N-2 weld zone",
            "measured_value": "4.2 mm",
            "severity": "WARNING",
            "citation": "doc-v301#p1-r004",
        },
    ]

    citations = [
        SourceDocumentCitation(
            document_id="doc-v301",
            file_name="refinery_vessel_inspection_v301.png",
            file_sha256=scan_sha256,
            page_number=1,
            bounding_box=[0.35, 0.08, 0.39, 0.50],
            snippet="Shell Course 1 (Lower): 12.4 mm",
        ),
        SourceDocumentCitation(
            document_id="doc-v301",
            file_name="refinery_vessel_inspection_v301.png",
            file_sha256=scan_sha256,
            page_number=1,
            bounding_box=[0.58, 0.08, 0.65, 0.85],
            snippet="Localized pitting observed at nozzle N-2 weld zone: 4.2 mm",
        ),
    ]

    # 4. Generate native Word deliverable
    generated_path = DocxDeliverableGenerator.create_approval_note(
        output_path=docx_path,
        title="Refinery Vessel V-301 Inspection & Non-Destructive Testing Approval Note",
        facility="Jamnagar Refinery Complex - Unit 04",
        equipment_tag="V-301",
        findings=findings,
        citations=citations,
        classification="INTERNAL",
        author="Sovereign Engineering AI",
        allowed_root=tmp_path,
    )

    assert generated_path.exists()
    assert generated_path.stat().st_size > 5000

    # 5. Inspect generated .docx document
    doc = docx.Document(str(generated_path))

    # Check classification banner and title
    doc_text = "\n".join(p.text for p in doc.paragraphs)
    assert "[ INTERNAL ]" in doc_text
    assert "Jamnagar Refinery Complex - Unit 04" in doc_text
    assert "V-301" in doc_text

    # Check tables: findings table + citations table
    assert len(doc.tables) >= 2

    # Verify findings table structure
    findings_table = doc.tables[0]
    assert len(findings_table.rows) >= 3  # 1 header + 2 data rows
    assert len(findings_table.columns) == 6

    # Verify content in findings table cells
    table_cell_texts = [cell.text for row in findings_table.rows for cell in row.cells]
    assert any("doc-v301#p1-r004" in t for t in table_cell_texts)
    assert any("WARNING" in t for t in table_cell_texts)
    assert any("SATISFACTORY" in t for t in table_cell_texts)
    assert any("4.2 mm" in t for t in table_cell_texts)

    # 6. Verify Lineage sidecar manifest exists
    sidecar_path = out_dir / "Refinery_Inspection_Approval_Note.docx.lineage.json"
    assert sidecar_path.exists(), f"Missing lineage sidecar at {sidecar_path}"

    with open(sidecar_path, "r", encoding="utf-8") as f:
        lineage_content = f.read()

    assert "doc-v301" in lineage_content
    assert "Refinery_Inspection_Approval_Note.docx" in lineage_content
    assert scan_sha256 in lineage_content
