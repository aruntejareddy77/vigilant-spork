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
]
