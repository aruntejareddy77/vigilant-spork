"""
tests/test_rag/test_local_vector_store.py
Unit tests for DocumentChunker and SQLiteVectorStore with binary IEEE-754 blob storage,
WAL mode, and cosine similarity ranking. Complies with RAG-01 and ASVS V1.4.
"""
import math
import sqlite3
import time
from pathlib import Path
import pytest
from pydantic import ValidationError

from sovereign.models.manifest import EngineConfig, EngineType, ModelCapability, ModelManifest
from sovereign.models.adapters.mock import MockModelAdapter
from sovereign.multimodal.models import (
    DocumentPage,
    DocumentRegion,
    ModalityType,
    NormalizedDocument,
)
from sovereign.rag.chunker import DocumentChunk, DocumentChunker
from sovereign.rag.vector_store import SQLiteVectorStore
from sovereign.tools.schemas import UserRole

@pytest.fixture
def mock_manifest() -> ModelManifest:
    return ModelManifest(
        model_id="mock-embed-v1",
        name="Mock Embedding Model",
        family="test",
        capabilities=[ModelCapability.EMBEDDING],
        context_window=8192,
        vram_estimate_mb=512,
        engine=EngineConfig(type=EngineType.MOCK, parameters={"simulated_latency_ms": 0.0}),
    )


@pytest.fixture
def sample_normalized_doc() -> NormalizedDocument:
    """Creates a 2-page NormalizedDocument with spatial regions."""
    page1 = DocumentPage(
        page_number=1,
        width=1000,
        height=1000,
        regions=[
            DocumentRegion(
                region_id="p1-r001",
                box_2d=[0.05, 0.10, 0.15, 0.90],
                text="FACILITY SAFETY MANUAL - SECTION 4: PRESSURE SYSTEMS",
                confidence=0.99,
                modality=ModalityType.PRINTED,
            ),
            DocumentRegion(
                region_id="p1-r002",
                box_2d=[0.20, 0.10, 0.45, 0.90],
                text="All pressure vessels in Unit 4 must undergo ultrasonic thickness testing every 12 months.",
                confidence=0.96,
                modality=ModalityType.PRINTED,
            ),
        ],
    )
    page2 = DocumentPage(
        page_number=2,
        width=1000,
        height=1000,
        regions=[
            DocumentRegion(
                region_id="p2-r001",
                box_2d=[0.10, 0.10, 0.35, 0.90],
                text="Inspection log entry for nozzle N3 indicates measured wall thickness of 12.4mm.",
                confidence=0.94,
                modality=ModalityType.HANDWRITTEN,
            ),
        ],
    )
    return NormalizedDocument(
        doc_id="doc-safety001",
        file_name="safety_manual_rev2.pdf",
        file_sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        total_pages=2,
        pages=[page1, page2],
    )


def test_document_chunk_model_validation():
    """Verifies DocumentChunk instantiation and classification validation."""
    chunk = DocumentChunk(
        chunk_id="chk-001",
        doc_id="doc-001",
        file_sha256="a" * 64,
        page_number=1,
        region_id="p1-r001",
        text_content="Sample text",
        classification="INTERNAL",
        allowed_roles=["Admin", "Engineer"],
        metadata={"custom": "val"},
    )
    assert chunk.classification == "INTERNAL"
    assert chunk.allowed_roles == ["admin", "engineer"]
    assert chunk.metadata["custom"] == "val"

    # Invalid classification rejected
    with pytest.raises(ValidationError):
        DocumentChunk(
            chunk_id="chk-bad",
            doc_id="doc-001",
            file_sha256="a" * 64,
            text_content="Sample text",
            classification="TOP_SECRET_INVALID",
        )


def test_document_chunker_text_splitting():
    """Verifies recursive text splitting with configurable chunk size and overlap."""
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
    text = (
        "Paragraph 1 contains general plant information.\n\n"
        "Paragraph 2 details high pressure relief valve protocols and maintenance schedules.\n\n"
        "Paragraph 3 covers emergency shutdown procedures in the event of thermal runaways."
    )
    chunks = chunker.chunk_text(text, doc_id="doc-test-split")
    assert len(chunks) >= 3
    for c in chunks:
        assert len(c.text_content) <= 100
        assert c.doc_id == "doc-test-split"
        assert c.chunk_id.startswith("doc-test-split-c")


def test_document_chunker_normalized_document(sample_normalized_doc: NormalizedDocument):
    """Verifies chunking of NormalizedDocument preserves page and region IDs."""
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
    chunks = chunker.chunk_normalized_document(
        sample_normalized_doc,
        classification="INTERNAL",
        allowed_roles=["engineer", "admin"],
    )

    assert len(chunks) == 3

    # Check page and region coordinates preserved
    c0 = chunks[0]
    assert c0.doc_id == "doc-safety001"
    assert c0.page_number == 1
    assert c0.region_id == "p1-r001"
    assert "PRESSURE SYSTEMS" in c0.text_content
    assert c0.metadata["box_2d"] == [0.05, 0.10, 0.15, 0.90]
    assert c0.metadata["modality"] == "printed"

    c2 = chunks[2]
    assert c2.page_number == 2
    assert c2.region_id == "p2-r001"
    assert "12.4mm" in c2.text_content
    assert c2.metadata["modality"] == "handwritten"


def test_sqlite_vector_store_wal_initialization(tmp_path: Path):
    """Verifies that SQLiteVectorStore initializes with WAL journal mode and schema."""
    db_file = tmp_path / "sovereign_knowledge.sqlite"
    store = SQLiteVectorStore(db_file)

    with sqlite3.connect(db_file) as conn:
        cursor = conn.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        # In WAL mode, SQLite returns 'wal'
        assert mode.lower() == "wal"

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks';")
        assert cursor.fetchone() is not None

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_chunks_doc';")
        assert cursor.fetchone() is not None


def test_vector_store_insert_and_get(tmp_path: Path):
    """Verifies inserting single chunk and retrieving it."""
    db_file = tmp_path / "test_store.sqlite"
    store = SQLiteVectorStore(db_file)

    chunk = DocumentChunk(
        chunk_id="chunk-alpha",
        doc_id="doc-alpha",
        file_sha256="f" * 64,
        page_number=1,
        region_id="p1-r001",
        text_content="Unit 4 distillation tower specs",
        classification="INTERNAL",
        allowed_roles=["engineer"],
        metadata={"priority": "high"},
    )
    embedding = [0.1] * 768

    store.insert_chunk(chunk, embedding)
    assert store.count_chunks() == 1

    retrieved = store.get_chunk("chunk-alpha")
    assert retrieved is not None
    assert retrieved.chunk_id == "chunk-alpha"
    assert retrieved.text_content == "Unit 4 distillation tower specs"
    assert retrieved.classification == "INTERNAL"
    assert retrieved.allowed_roles == ["engineer"]
    assert retrieved.metadata["priority"] == "high"


def test_vector_store_batch_insert(tmp_path: Path):
    """Verifies batch insertion of multiple chunks."""
    db_file = tmp_path / "test_batch.sqlite"
    store = SQLiteVectorStore(db_file)

    items = []
    for i in range(10):
        c = DocumentChunk(
            chunk_id=f"batch-{i:03d}",
            doc_id="doc-batch",
            file_sha256="e" * 64,
            page_number=1,
            text_content=f"Batch chunk content {i}",
            classification="INTERNAL",
            allowed_roles=["admin", "engineer"],
        )
        vec = [0.0] * 768
        vec[i] = 1.0
        items.append((c, vec))

    store.batch_insert(items)
    assert store.count_chunks() == 10


def test_vector_store_cosine_search_ranking(tmp_path: Path):
    """Verifies cosine similarity calculation and top_k descending rank order."""
    db_file = tmp_path / "test_ranking.sqlite"
    store = SQLiteVectorStore(db_file)

    # Insert 3 chunks with known directional unit vectors (dim=4 for simplicity)
    # v1: identical to query [1, 0, 0, 0] -> similarity 1.0
    # v2: 45 degrees [0.7071, 0.7071, 0, 0] -> similarity ~0.7071
    # v3: orthogonal [0, 1, 0, 0] -> similarity 0.0
    c1 = DocumentChunk(
        chunk_id="c-match", doc_id="d1", file_sha256="1"*64,
        text_content="Exact match content", classification="PUBLIC", allowed_roles=["engineer", "admin"]
    )
    c2 = DocumentChunk(
        chunk_id="c-partial", doc_id="d1", file_sha256="1"*64,
        text_content="Partial match content", classification="PUBLIC", allowed_roles=["engineer", "admin"]
    )
    c3 = DocumentChunk(
        chunk_id="c-ortho", doc_id="d1", file_sha256="1"*64,
        text_content="Orthogonal content", classification="PUBLIC", allowed_roles=["engineer", "admin"]
    )

    store.insert_chunk(c1, [1.0, 0.0, 0.0, 0.0])
    store.insert_chunk(c2, [0.7071, 0.7071, 0.0, 0.0])
    store.insert_chunk(c3, [0.0, 1.0, 0.0, 0.0])

    query = [1.0, 0.0, 0.0, 0.0]
    results = store.search(query, top_k=3, user_role=UserRole.ENGINEER)

    assert len(results) == 3
    assert results[0][0].chunk_id == "c-match"
    assert pytest.approx(results[0][1], abs=1e-3) == 1.0

    assert results[1][0].chunk_id == "c-partial"
    assert pytest.approx(results[1][1], abs=1e-3) == 0.7071

    assert results[2][0].chunk_id == "c-ortho"
    assert pytest.approx(results[2][1], abs=1e-3) == 0.0


def test_vector_store_pure_python_fallback(tmp_path: Path):
    """Verifies that pure Python fallback matches NumPy similarity results."""
    db_file = tmp_path / "test_fallback.sqlite"
    store = SQLiteVectorStore(db_file)

    c1 = DocumentChunk(
        chunk_id="c-1", doc_id="d1", file_sha256="1"*64,
        text_content="Chunk 1", classification="PUBLIC", allowed_roles=["engineer"]
    )
    c2 = DocumentChunk(
        chunk_id="c-2", doc_id="d1", file_sha256="1"*64,
        text_content="Chunk 2", classification="PUBLIC", allowed_roles=["engineer"]
    )

    store.insert_chunk(c1, [0.6, 0.8])
    store.insert_chunk(c2, [0.8, 0.6])

    query = [0.6, 0.8]

    # NumPy result
    store._force_pure_python = False
    numpy_res = store.search(query, top_k=2, user_role=UserRole.ENGINEER)

    # Pure Python result
    store._force_pure_python = True
    python_res = store.search(query, top_k=2, user_role=UserRole.ENGINEER)

    assert len(numpy_res) == len(python_res)
    for (c_np, s_np), (c_py, s_py) in zip(numpy_res, python_res):
        assert c_np.chunk_id == c_py.chunk_id
        assert pytest.approx(s_np, abs=1e-4) == s_py


def test_vector_store_performance_with_mock_embeddings(tmp_path: Path, mock_manifest: ModelManifest):
    """Verifies insertion and search of 768-dim embeddings completes in < 15ms."""
    adapter = MockModelAdapter(mock_manifest)
    adapter.load()

    texts = [
        "Boiler feedwater pump P-101 vibration analysis report",
        "Ultrasonic testing on high pressure line L-302 showed 8.2mm wall thickness",
        "Emergency isolation valve XV-201 failed quarterly stroke test",
        "Flare stack ignition system preventative maintenance guidelines",
        "Atmospheric distillation column overhead reflux accumulator level control",
    ]

    embeddings = adapter.embed(texts)
    assert len(embeddings) == len(texts)
    assert len(embeddings[0]) == 768

    db_file = tmp_path / "perf_test.sqlite"
    store = SQLiteVectorStore(db_file)

    items = []
    for idx, (txt, emb) in enumerate(zip(texts, embeddings)):
        chunk = DocumentChunk(
            chunk_id=f"perf-{idx:03d}",
            doc_id="doc-perf",
            file_sha256="c" * 64,
            page_number=1,
            text_content=txt,
            classification="INTERNAL",
            allowed_roles=["engineer", "admin"],
        )
        items.append((chunk, emb))

    store.batch_insert(items)

    # Measure search latency
    query_vec = adapter.embed(["pump vibration ultrasonic"])[0]
    t0 = time.perf_counter()
    results = store.search(query_vec, top_k=3, user_role=UserRole.ENGINEER)
    latency_ms = (time.perf_counter() - t0) * 1000

    assert len(results) == 3
    assert latency_ms < 15.0  # Must be sub-15ms
