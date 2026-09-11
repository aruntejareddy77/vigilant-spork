"""
src/sovereign/multimodal/forms.py
Structured form and handwriting extraction with confidence scoring and Human-in-the-Loop gates.
Implements MMOD-02 and threat mitigation T-04-05.
"""
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

from sovereign.multimodal.ocr import OCRResultBlock

# Mandatory Confidence Threshold per MMOD-02 / T-04-05
CONFIDENCE_THRESHOLD = 0.85

CHECKED_PATTERNS = [
    re.compile(r"\[[xX✓vV]\]"),
    re.compile(r"\([xX✓vV]\)"),
    re.compile(r"[☑✓✔]"),
]

UNCHECKED_PATTERNS = [
    re.compile(r"\[\s*\]"),
    re.compile(r"\(\s*\)"),
    re.compile(r"\[_\]"),
    re.compile(r"☐"),
]

DATE_REGEX = re.compile(
    r"^(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})$"
)

NUMBER_REGEX = re.compile(
    r"^[-+]?\d+(?:\.\d+)?(?:\s*(?:mm|psi|bar|kPa|MPa|kg|g|m|cm|°C|°F|%|V|A|rpm))?$",
    re.IGNORECASE,
)


class CheckboxState(str, Enum):
    """Checkbox extraction states."""
    CHECKED = "checked"
    UNCHECKED = "unchecked"
    UNKNOWN = "unknown"


class FormFieldType(str, Enum):
    """Semantic classifications for extracted form fields."""
    TEXT = "text"
    NUMBER = "number"
    CHECKBOX = "checkbox"
    DATE = "date"
    SIGNATURE = "signature"


class RawFormField(BaseModel):
    """
    Extracted form field with confidence metric and mandatory human-in-the-loop review flagging.
    """
    model_config = ConfigDict(extra="allow")

    field_id: str
    key: str
    value: Any
    field_type: FormFieldType
    box_2d: List[float] = Field(description="Normalized coordinates [ymin, xmin, ymax, xmax]")
    confidence: float = Field(ge=0.0, le=1.0)
    is_handwritten: bool = False
    needs_review: bool = False
    review_reason: Optional[str] = None


def parse_checkbox_state(text: str) -> Tuple[CheckboxState, str]:
    """
    Detect whether text contains a checkbox marker.
    Returns (CheckboxState, remaining_text_without_checkbox).
    """
    for pat in CHECKED_PATTERNS:
        match = pat.search(text)
        if match:
            clean = pat.sub("", text).strip(" :-\t")
            return CheckboxState.CHECKED, clean

    for pat in UNCHECKED_PATTERNS:
        match = pat.search(text)
        if match:
            clean = pat.sub("", text).strip(" :-\t")
            return CheckboxState.UNCHECKED, clean

    return CheckboxState.UNKNOWN, text.strip()


def classify_field_type(key: str, value: Any) -> FormFieldType:
    """Classify the semantic field type based on key nomenclature and value format."""
    if isinstance(value, CheckboxState):
        return FormFieldType.CHECKBOX

    val_str = str(value).strip()
    key_lower = key.lower()

    if any(sig_term in key_lower for sig_term in ["signature", "signed", "sign-off", "inspector signature"]):
        return FormFieldType.SIGNATURE

    if any(date_term in key_lower for date_term in ["date", "timestamp"]) or DATE_REGEX.match(val_str):
        return FormFieldType.DATE

    if NUMBER_REGEX.match(val_str):
        return FormFieldType.NUMBER

    return FormFieldType.TEXT


def build_hitl_interrupt_payload(
    flagged_fields: List[RawFormField],
    doc_id: Optional[str] = None,
    page_num: int = 1,
) -> Dict[str, Any]:
    """
    Build structured interruption payload for Phase 3 AgentRuntime / StateGraph HITL review.
    """
    return {
        "action": "verify_handwriting",
        "doc_id": doc_id or "unknown",
        "page_number": page_num,
        "flagged_count": len(flagged_fields),
        "fields": [
            {
                "field_id": f.field_id,
                "key": f.key,
                "value": f.value.value if isinstance(f.value, Enum) else f.value,
                "field_type": f.field_type.value if hasattr(f.field_type, "value") else str(f.field_type),
                "confidence": round(f.confidence, 4),
                "is_handwritten": f.is_handwritten,
                "box_2d": f.box_2d,
                "review_reason": f.review_reason,
            }
            for f in flagged_fields
        ],
        "message": (
            f"{len(flagged_fields)} field(s) require manual operator verification due to low "
            f"confidence (< {CONFIDENCE_THRESHOLD:.2f})."
        ),
    }


class FormExtractor:
    """
    Extracts structured key-value pairs, checkbox states, and handwritten entries
    from document OCR result blocks. Automatically flags entries with confidence < threshold.
    """

    def __init__(self, confidence_threshold: float = CONFIDENCE_THRESHOLD):
        self.confidence_threshold = confidence_threshold

    def extract_fields(
        self,
        blocks: List[OCRResultBlock],
        form_template: Optional[Dict[str, Any]] = None,
    ) -> List[RawFormField]:
        """
        Extract structured fields from OCR blocks.
        Associates labels with values, parses checkboxes, identifies types,
        and enforces confidence thresholding.
        """
        fields: List[RawFormField] = []
        consumed_indices = set()

        for i, block in enumerate(blocks):
            if i in consumed_indices or block.block_type == "header":
                continue

            text = block.text.strip()
            if not text:
                continue

            # Check 1: In-block checkbox (e.g. "Corrosion Checked: [x]")
            cb_state, clean_text = parse_checkbox_state(text)
            if cb_state != CheckboxState.UNKNOWN:
                key = clean_text if clean_text else text
                field = self._create_field(
                    field_id=f"field-{len(fields) + 1:03d}",
                    key=key,
                    value=cb_state,
                    field_type=FormFieldType.CHECKBOX,
                    box_2d=block.box_2d,
                    confidence=block.confidence,
                    is_handwritten=(block.block_type == "handwritten"),
                )
                fields.append(field)
                consumed_indices.add(i)
                continue

            # Check 2: In-block key-value with colon (e.g. "Shell Thickness: 12.4 mm")
            if ":" in text:
                parts = text.split(":", 1)
                k = parts[0].strip()
                v = parts[1].strip()

                if v:
                    # Check if value has checkbox
                    sub_cb, sub_clean = parse_checkbox_state(v)
                    if sub_cb != CheckboxState.UNKNOWN:
                        val_actual = sub_cb
                        f_type = FormFieldType.CHECKBOX
                    else:
                        val_actual = v
                        f_type = classify_field_type(k, val_actual)

                    field = self._create_field(
                        field_id=f"field-{len(fields) + 1:03d}",
                        key=k,
                        value=val_actual,
                        field_type=f_type,
                        box_2d=block.box_2d,
                        confidence=block.confidence,
                        is_handwritten=(block.block_type == "handwritten"),
                    )
                    fields.append(field)
                    consumed_indices.add(i)
                    continue

            # Check 3: Key-value split across adjacent horizontal blocks
            # E.g. block i has "Equipment Tag:" and block i+1 has "TK-901"
            if text.endswith(":") and i + 1 < len(blocks) and (i + 1) not in consumed_indices:
                next_block = blocks[i + 1]
                # Check vertical overlap / alignment
                ymin_diff = abs(block.box_2d[0] - next_block.box_2d[0])
                if ymin_diff < 0.08:
                    k = text.rstrip(":").strip()
                    next_text = next_block.text.strip()
                    sub_cb, _ = parse_checkbox_state(next_text)
                    if sub_cb != CheckboxState.UNKNOWN:
                        val_actual = sub_cb
                        f_type = FormFieldType.CHECKBOX
                    else:
                        val_actual = next_text
                        f_type = classify_field_type(k, val_actual)

                    union_box = [
                        min(block.box_2d[0], next_block.box_2d[0]),
                        min(block.box_2d[1], next_block.box_2d[1]),
                        max(block.box_2d[2], next_block.box_2d[2]),
                        max(block.box_2d[3], next_block.box_2d[3]),
                    ]
                    # Take minimum confidence for strict safety
                    combined_conf = min(block.confidence, next_block.confidence)
                    is_hw = (block.block_type == "handwritten" or next_block.block_type == "handwritten")

                    field = self._create_field(
                        field_id=f"field-{len(fields) + 1:03d}",
                        key=k,
                        value=val_actual,
                        field_type=f_type,
                        box_2d=union_box,
                        confidence=combined_conf,
                        is_handwritten=is_hw,
                    )
                    fields.append(field)
                    consumed_indices.add(i)
                    consumed_indices.add(i + 1)
                    continue

        return fields

    def _create_field(
        self,
        field_id: str,
        key: str,
        value: Any,
        field_type: FormFieldType,
        box_2d: List[float],
        confidence: float,
        is_handwritten: bool,
    ) -> RawFormField:
        """Construct RawFormField and enforce the confidence gate."""
        needs_review = False
        review_reason = None

        if confidence < self.confidence_threshold:
            needs_review = True
            review_reason = (
                f"Confidence {confidence:.2f} is below mandatory threshold {self.confidence_threshold:.2f}"
            )

        return RawFormField(
            field_id=field_id,
            key=key,
            value=value,
            field_type=field_type,
            box_2d=box_2d,
            confidence=round(confidence, 4),
            is_handwritten=is_handwritten,
            needs_review=needs_review,
            review_reason=review_reason,
        )

    def build_hitl_interrupt_payload(
        self,
        flagged_fields: List[RawFormField],
        doc_id: Optional[str] = None,
        page_num: int = 1,
    ) -> Dict[str, Any]:
        """Method proxy to build_hitl_interrupt_payload for convenience."""
        return build_hitl_interrupt_payload(flagged_fields, doc_id=doc_id, page_num=page_num)
