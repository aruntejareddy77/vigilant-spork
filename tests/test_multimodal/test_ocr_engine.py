"""
tests/test_multimodal/test_ocr_engine.py
Unit tests for offline OCR backends, image safety limits, coordinate normalization, and path security.
"""
from pathlib import Path
import pytest
from PIL import Image
import pypdf

from sovereign.multimodal.ocr import (
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_FILE_SIZE,
    MAX_PDF_PAGES,
    InvalidDocumentError,
    OCRResultBlock,
    BaseOCRBackend,
    TesseractOCRBackend,
    DeterministicMockOCRBackend,
    get_ocr_backend,
    validate_image_file,
)


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Fixture providing an isolated workspace folder."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def valid_png_image(temp_workspace: Path) -> Path:
    """Fixture generating a valid small test PNG image."""
    img_path = temp_workspace / "inspection_sample.png"
    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    img.save(img_path)
    return img_path


def test_valid_image_passes_validation(valid_png_image: Path, temp_workspace: Path):
    """Test that a standard valid image within bounds passes validation."""
    validated = validate_image_file(valid_png_image, workspace_root=temp_workspace)
    assert validated == valid_png_image.resolve()


def test_missing_file_raises_error(temp_workspace: Path):
    """Test that validating a non-existent file raises FileNotFoundError."""
    missing = temp_workspace / "does_not_exist.png"
    with pytest.raises(FileNotFoundError):
        validate_image_file(missing, workspace_root=temp_workspace)


def test_path_traversal_blocked(temp_workspace: Path, tmp_path: Path):
    """Test that path attempting to escape workspace is blocked."""
    outside_file = tmp_path / "outside.png"
    img = Image.new("RGB", (50, 50), color=(0, 0, 0))
    img.save(outside_file)

    with pytest.raises(InvalidDocumentError, match="Path traversal violation"):
        validate_image_file(outside_file, workspace_root=temp_workspace)


def test_null_byte_path_rejected(temp_workspace: Path):
    """Test that path with null byte is rejected immediately."""
    with pytest.raises(InvalidDocumentError, match="Null byte detected"):
        validate_image_file("sample\x00.png", workspace_root=temp_workspace)


def test_unsupported_file_extension(temp_workspace: Path):
    """Test that files with unsupported extensions are rejected."""
    bad_ext_file = temp_workspace / "script.exe"
    bad_ext_file.write_text("not an image")
    with pytest.raises(InvalidDocumentError, match="Unsupported file format"):
        validate_image_file(bad_ext_file, workspace_root=temp_workspace)


def test_empty_file_rejected(temp_workspace: Path):
    """Test that zero-byte files are rejected."""
    empty_file = temp_workspace / "empty.png"
    empty_file.touch()
    with pytest.raises(InvalidDocumentError, match="File is empty"):
        validate_image_file(empty_file, workspace_root=temp_workspace)


def test_corrupted_image_rejected(temp_workspace: Path):
    """Test that unreadable/corrupted images are rejected."""
    corrupted_file = temp_workspace / "corrupted.png"
    corrupted_file.write_bytes(b"\x89PNG\r\n\x1a\ncorruptedcontentgibberish")
    with pytest.raises(InvalidDocumentError, match="Corrupted or unidentified image format"):
        validate_image_file(corrupted_file, workspace_root=temp_workspace)


def test_file_size_exceeding_limit(temp_workspace: Path, monkeypatch: pytest.MonkeyPatch):
    """Test that files exceeding MAX_IMAGE_FILE_SIZE are rejected."""
    oversized_file = temp_workspace / "huge.png"
    oversized_file.write_bytes(b"dummy" * 20)

    # Monkeypatch MAX_IMAGE_FILE_SIZE to 50 bytes for test
    monkeypatch.setattr("sovereign.multimodal.ocr.MAX_IMAGE_FILE_SIZE", 50)

    with pytest.raises(InvalidDocumentError, match="exceeds maximum allowed"):
        validate_image_file(oversized_file, workspace_root=temp_workspace)


def test_decompression_bomb_pixel_bounds(temp_workspace: Path, monkeypatch: pytest.MonkeyPatch):
    """Test Threat T-04-03: images with dimensions exceeding 50M pixels are blocked."""
    bomb_file = temp_workspace / "pixel_bomb.png"
    img = Image.new("RGB", (10, 10), color=(0, 0, 0))
    img.save(bomb_file)

    # Mock Pillow image dimensions
    class MockImage:
        width = 10000
        height = 6000  # 60,000,000 pixels > 50,000,000 MAX_IMAGE_PIXELS
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def verify(self):
            pass

    monkeypatch.setattr(Image, "open", lambda p: MockImage())

    with pytest.raises(InvalidDocumentError, match="exceed maximum limit"):
        validate_image_file(bomb_file, workspace_root=temp_workspace)


def test_pdf_validation_and_page_limit(temp_workspace: Path):
    """Test that PDF files are validated and reject PDFs over 100 pages."""
    # Create valid 1-page PDF
    pdf_path = temp_workspace / "valid.pdf"
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with open(pdf_path, "wb") as f:
        writer.write(f)

    validated = validate_image_file(pdf_path, workspace_root=temp_workspace)
    assert validated == pdf_path.resolve()

    # Create oversized PDF (> 100 pages)
    large_pdf_path = temp_workspace / "large.pdf"
    large_writer = pypdf.PdfWriter()
    for _ in range(101):
        large_writer.add_blank_page(width=72, height=72)
    with open(large_pdf_path, "wb") as f:
        large_writer.write(f)

    with pytest.raises(InvalidDocumentError, match="exceeds maximum allowed 100 pages"):
        validate_image_file(large_pdf_path, workspace_root=temp_workspace)


def test_deterministic_mock_ocr_backend_extraction(valid_png_image: Path):
    """Test that DeterministicMockOCRBackend produces structured, normalized blocks."""
    backend = DeterministicMockOCRBackend()
    assert backend.is_available() is True

    blocks = backend.extract_text_and_layout(valid_png_image)
    assert len(blocks) >= 5

    # Check normalization and bounds
    for block in blocks:
        assert isinstance(block, OCRResultBlock)
        assert len(block.box_2d) == 4
        ymin, xmin, ymax, xmax = block.box_2d
        assert 0.0 <= ymin <= 1.0
        assert 0.0 <= xmin <= 1.0
        assert 0.0 <= ymax <= 1.0
        assert 0.0 <= xmax <= 1.0
        assert ymin <= ymax
        assert xmin <= xmax
        assert 0.0 <= block.confidence <= 1.0
        assert len(block.text) > 0

    # Verify deterministic reproducibility
    blocks_second_run = backend.extract_text_and_layout(valid_png_image)
    assert [b.model_dump() for b in blocks] == [b.model_dump() for b in blocks_second_run]


def test_deterministic_mock_predefined_blocks(valid_png_image: Path):
    """Test that custom predefined blocks can be injected into mock backend."""
    custom_block = OCRResultBlock(
        text="Custom Valve Reading: 15.2 bar",
        confidence=0.99,
        box_2d=[0.1, 0.2, 0.3, 0.4],
        block_type="text",
    )
    backend = DeterministicMockOCRBackend(predefined_blocks=[custom_block])
    extracted = backend.extract_text_and_layout(valid_png_image)
    assert len(extracted) == 1
    assert extracted[0].text == "Custom Valve Reading: 15.2 bar"
    assert extracted[0].confidence == 0.99


def test_get_ocr_backend_factory():
    """Test get_ocr_backend factory behavior."""
    mock_backend = get_ocr_backend(force_mock=True)
    assert isinstance(mock_backend, DeterministicMockOCRBackend)
    assert mock_backend.is_available() is True

    prefer_mock_backend = get_ocr_backend(prefer_mock=True)
    assert isinstance(prefer_mock_backend, DeterministicMockOCRBackend)

    default_backend = get_ocr_backend()
    assert isinstance(default_backend, BaseOCRBackend)


def test_tesseract_backend_unavailability_handling(valid_png_image: Path, monkeypatch: pytest.MonkeyPatch):
    """Test that TesseractOCRBackend raises descriptive error when binary unavailable."""
    backend = TesseractOCRBackend()
    monkeypatch.setattr(backend, "is_available", lambda: False)

    with pytest.raises(RuntimeError, match="Tesseract binary is not installed"):
        backend.extract_text_and_layout(valid_png_image)
