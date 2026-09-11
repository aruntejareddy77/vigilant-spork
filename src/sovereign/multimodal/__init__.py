"""
src/sovereign/multimodal/__init__.py
Sovereign offline multimodal ingestion, OCR, and document normalization package.
"""
from sovereign.multimodal.ocr import (
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_FILE_SIZE,
    MAX_PDF_PAGES,
    ALLOWED_IMAGE_EXTENSIONS,
    InvalidDocumentError,
    OCRResultBlock,
    BaseOCRBackend,
    TesseractOCRBackend,
    DeterministicMockOCRBackend,
    get_ocr_backend,
    validate_image_file,
)
from sovereign.multimodal.forms import (
    CONFIDENCE_THRESHOLD,
    CheckboxState,
    FormFieldType,
    RawFormField,
    FormExtractor,
    build_hitl_interrupt_payload,
)
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

__all__ = [
    "MAX_IMAGE_PIXELS",
    "MAX_IMAGE_FILE_SIZE",
    "MAX_PDF_PAGES",
    "ALLOWED_IMAGE_EXTENSIONS",
    "InvalidDocumentError",
    "OCRResultBlock",
    "BaseOCRBackend",
    "TesseractOCRBackend",
    "DeterministicMockOCRBackend",
    "get_ocr_backend",
    "validate_image_file",
    "CONFIDENCE_THRESHOLD",
    "CheckboxState",
    "FormFieldType",
    "RawFormField",
    "FormExtractor",
    "build_hitl_interrupt_payload",
    "ModalityType",
    "DocumentRegion",
    "FormField",
    "ExtractedTable",
    "DocumentPage",
    "NormalizedDocument",
    "OCR_DOCUMENT_TOOL",
    "execute_ocr_document",
    "register_multimodal_tools",
]
