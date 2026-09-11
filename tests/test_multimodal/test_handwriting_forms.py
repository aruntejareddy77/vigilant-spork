"""
tests/test_multimodal/test_handwriting_forms.py
Unit tests for structured form extraction, checkbox detection, confidence thresholding,
and Human-in-the-Loop review payload generation per MMOD-02 and T-04-05.
"""
from pathlib import Path
import pytest

from sovereign.multimodal.ocr import OCRResultBlock, DeterministicMockOCRBackend
from sovereign.multimodal.forms import (
    CONFIDENCE_THRESHOLD,
    CheckboxState,
    FormFieldType,
    RawFormField,
    FormExtractor,
    build_hitl_interrupt_payload,
    parse_checkbox_state,
    classify_field_type,
)


def test_parse_checkbox_state_checked():
    """Test recognition of checked checkbox markers."""
    for text in ["[x] Passed", "[X] Verified", "[✓] Inspected", "☑ Complete", "(x) Ok"]:
        state, clean = parse_checkbox_state(text)
        assert state == CheckboxState.CHECKED
        assert "[" not in clean and "(" not in clean


def test_parse_checkbox_state_unchecked():
    """Test recognition of unchecked checkbox markers."""
    for text in ["[ ] Pending", "() Incomplete", "[_] Open", "☐ Not Checked"]:
        state, clean = parse_checkbox_state(text)
        assert state == CheckboxState.UNCHECKED
        assert "[" not in clean and "(" not in clean


def test_classify_field_type():
    """Test classification of field types based on keys and values."""
    assert classify_field_type("Inspector Signature", "John Doe") == FormFieldType.SIGNATURE
    assert classify_field_type("Sign-off", "A. Smith") == FormFieldType.SIGNATURE
    assert classify_field_type("Inspection Date", "2026-09-11") == FormFieldType.DATE
    assert classify_field_type("Recorded Date", "11/09/2026") == FormFieldType.DATE
    assert classify_field_type("Shell Thickness", "12.4 mm") == FormFieldType.NUMBER
    assert classify_field_type("Design Pressure", "2.50 MPa") == FormFieldType.NUMBER
    assert classify_field_type("Temperature", "-10 °C") == FormFieldType.NUMBER
    assert classify_field_type("Corrosion Check", CheckboxState.CHECKED) == FormFieldType.CHECKBOX
    assert classify_field_type("General Remarks", "Unit cleaned and ready") == FormFieldType.TEXT


def test_form_extractor_single_block_key_values():
    """Test extraction of key-value pairs formatted within a single text block."""
    blocks = [
        OCRResultBlock(
            text="INSPECTION REPORT",
            confidence=0.99,
            box_2d=[0.05, 0.1, 0.1, 0.9],
            block_type="header",
        ),
        OCRResultBlock(
            text="Shell Thickness: 14.5 mm",
            confidence=0.95,
            box_2d=[0.2, 0.1, 0.25, 0.5],
            block_type="text",
        ),
        OCRResultBlock(
            text="Corrosion Checked: [x]",
            confidence=0.90,
            box_2d=[0.3, 0.1, 0.35, 0.4],
            block_type="text",
        ),
    ]

    extractor = FormExtractor()
    fields = extractor.extract_fields(blocks)

    assert len(fields) == 2
    # Field 1: Shell Thickness
    f1 = fields[0]
    assert f1.key == "Shell Thickness"
    assert f1.value == "14.5 mm"
    assert f1.field_type == FormFieldType.NUMBER
    assert f1.confidence == 0.95
    assert f1.needs_review is False

    # Field 2: Corrosion Checked
    f2 = fields[1]
    assert "Corrosion Checked" in f2.key
    assert f2.value == CheckboxState.CHECKED
    assert f2.field_type == FormFieldType.CHECKBOX
    assert f2.needs_review is False


def test_form_extractor_adjacent_block_key_values():
    """Test extraction of key-value pairs split across adjacent horizontal blocks."""
    blocks = [
        OCRResultBlock(
            text="Equipment Tag:",
            confidence=0.96,
            box_2d=[0.15, 0.10, 0.19, 0.30],
            block_type="text",
        ),
        OCRResultBlock(
            text="TK-901",
            confidence=0.93,
            box_2d=[0.15, 0.32, 0.19, 0.50],
            block_type="text",
        ),
    ]

    extractor = FormExtractor()
    fields = extractor.extract_fields(blocks)

    assert len(fields) == 1
    f = fields[0]
    assert f.key == "Equipment Tag"
    assert f.value == "TK-901"
    assert f.confidence == 0.93
    assert f.box_2d == [0.15, 0.10, 0.19, 0.50]
    assert f.needs_review is False


def test_confidence_thresholding_and_hitl_flag():
    """Test that fields with confidence < 0.85 are automatically flagged for HITL review."""
    blocks = [
        OCRResultBlock(
            text="High Confidence Reading: 10.0 mm",
            confidence=0.88,
            box_2d=[0.1, 0.1, 0.15, 0.5],
            block_type="text",
        ),
        OCRResultBlock(
            text="Low Confidence Handwritten Reading: 3.8 mm",
            confidence=0.74,  # sub-0.85
            box_2d=[0.2, 0.1, 0.25, 0.6],
            block_type="handwritten",
        ),
    ]

    extractor = FormExtractor(confidence_threshold=0.85)
    fields = extractor.extract_fields(blocks)

    assert len(fields) == 2
    assert fields[0].needs_review is False
    assert fields[0].review_reason is None

    assert fields[1].needs_review is True
    assert fields[1].is_handwritten is True
    assert "below mandatory threshold 0.85" in fields[1].review_reason


def test_build_hitl_interrupt_payload():
    """Test that HITL interrupt payload structure conforms to orchestration state machine."""
    flagged = [
        RawFormField(
            field_id="field-007",
            key="Nozzle N3 Thickness",
            value="4.2 mm",
            field_type=FormFieldType.NUMBER,
            box_2d=[0.44, 0.1, 0.48, 0.55],
            confidence=0.72,
            is_handwritten=True,
            needs_review=True,
            review_reason="Confidence 0.72 is below mandatory threshold 0.85",
        )
    ]

    payload = build_hitl_interrupt_payload(flagged, doc_id="doc-abc12345", page_num=1)

    assert payload["action"] == "verify_handwriting"
    assert payload["doc_id"] == "doc-abc12345"
    assert payload["page_number"] == 1
    assert payload["flagged_count"] == 1
    assert len(payload["fields"]) == 1

    field_data = payload["fields"][0]
    assert field_data["field_id"] == "field-007"
    assert field_data["key"] == "Nozzle N3 Thickness"
    assert field_data["value"] == "4.2 mm"
    assert field_data["field_type"] == "number"
    assert field_data["confidence"] == 0.72
    assert field_data["is_handwritten"] is True
    assert "below mandatory threshold" in field_data["review_reason"]


def test_deterministic_mock_blocks_extraction_integration(tmp_path: Path):
    """Integration test verifying FormExtractor on output from DeterministicMockOCRBackend."""
    img_path = tmp_path / "mock_inspection.png"
    img_path.write_bytes(b"dummy image bytes for deterministic hashing")

    # Mock validate_image_file for test dummy file
    import sovereign.multimodal.ocr as ocr_module
    from unittest.mock import patch

    with patch.object(ocr_module, "validate_image_file", return_value=img_path):
        backend = DeterministicMockOCRBackend()
        blocks = backend.extract_text_and_layout(img_path)

    extractor = FormExtractor()
    fields = extractor.extract_fields(blocks)

    # Deterministic mock contains tags, thickness, checkboxes, and a sub-0.85 handwritten entry
    assert len(fields) >= 5

    flagged = [f for f in fields if f.needs_review]
    assert len(flagged) == 1
    assert flagged[0].key == "Nozzle N3 Thickness"
    assert flagged[0].value == "4.2 mm"
    assert flagged[0].confidence == 0.72
    assert flagged[0].is_handwritten is True

    # Test payload construction
    payload = extractor.build_hitl_interrupt_payload(flagged, doc_id="doc-test-123", page_num=1)
    assert payload["flagged_count"] == 1
    assert payload["fields"][0]["key"] == "Nozzle N3 Thickness"
