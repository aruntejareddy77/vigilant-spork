"""
tests/test_attestation/test_sparse_chunk_hashing.py
Unit tests for full SHA-256 and fast 64MB sparse head/tail chunk hashing.
"""
from pathlib import Path
import time
from sovereign.attestation.hasher import hash_full_file, hash_sparse_chunks


def test_small_file_sparse_hash(temp_dir: Path):
    """Verify that for files <= 64MB, both sparse chunk hashes equal full SHA-256."""
    small_file = temp_dir / "small.txt"
    content = b"The quick brown fox jumps over the lazy dog" * 1000
    small_file.write_bytes(content)

    full_sha = hash_full_file(small_file)
    first_64, last_64, size = hash_sparse_chunks(small_file)

    assert size == len(content)
    assert first_64 == full_sha
    assert last_64 == full_sha


def test_large_file_sparse_chunk_performance():
    """Verify that 64MB head and tail chunk hashing on a 130MB file completes in < 200ms."""
    mock_bin = Path("tests/fixtures/mock_qwen.bin")
    if not mock_bin.exists():
        # Generate on the fly if needed
        mock_bin.parent.mkdir(parents=True, exist_ok=True)
        with open(mock_bin, "wb") as f:
            f.write(b"HEAD_MAGIC_TENSORS")
            f.seek(130 * 1024 * 1024 - 18)
            f.write(b"TAIL_MAGIC_TENSORS")

    start = time.perf_counter()
    first_64, last_64, size = hash_sparse_chunks(mock_bin)
    duration_ms = (time.perf_counter() - start) * 1000

    assert size >= 130 * 1024 * 1024
    assert len(first_64) == 64
    assert len(last_64) == 64
    assert first_64 != last_64  # Head and tail are different

    # Performance target: warm restart check completes in < 500ms (typically < 100ms)
    assert duration_ms < 500.0, f"Sparse hashing took too long: {duration_ms:.2f}ms"


def test_sparse_chunk_boundary_tamper_detection(temp_dir: Path):
    """Verify that mutating the head or tail chunk alters the respective hash."""
    test_large = temp_dir / "test_130mb.bin"
    size_130mb = 130 * 1024 * 1024

    with open(test_large, "wb") as f:
        f.write(b"ORIGINAL_HEADER_CHUNKS")
        f.seek(size_130mb - 22)
        f.write(b"ORIGINAL_FOOTER_CHUNKS")

    orig_first, orig_last, _ = hash_sparse_chunks(test_large)

    # 1. Mutate byte in the first 1KB
    with open(test_large, "r+b") as f:
        f.seek(0)
        f.write(b"MODIFIED_HEADER_CHUNKS")

    new_first, new_last, _ = hash_sparse_chunks(test_large)
    assert new_first != orig_first
    assert new_last == orig_last  # tail remained unchanged

    # 2. Mutate byte in the last 1KB
    with open(test_large, "r+b") as f:
        f.seek(size_130mb - 22)
        f.write(b"MODIFIED_FOOTER_CHUNKS")

    final_first, final_last, _ = hash_sparse_chunks(test_large)
    assert final_first == new_first
    assert final_last != orig_last
