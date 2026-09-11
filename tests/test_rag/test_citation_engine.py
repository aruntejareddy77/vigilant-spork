"""
tests/test_rag/test_citation_engine.py
Unit tests for inline citation parsing, verification, reference table rendering,
lineage model conversion, and rag_search tool execution.
Complies with RAG-02, ToolRegistry integration, and Phase 1 LineageEngine compatibility.
"""
from pathlib import Path
import pytest

from sovereign.lineage.models import SourceDocumentCitation
from sovereign.models.adapters.mock import MockModelAdapter
from sovereign.models.manifest import EngineConfig, EngineType, ModelCapability, ModelManifest
from sovereign.rag.chunker import DocumentChunk
from sovereign.rag.citations import Citation, CitationEngine
from sovereign.rag.tools import (
    RAG_SEARCH_TOOL,
    execute_rag_search,
    register_rag_tools,
)
from sovereign.rag.vector_store import SQLiteVectorStore
from sovereign.tools.registry import ToolRegistry
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
def sample_retrieved_chunks() -> list[DocumentChunk]:
    return [
        DocumentChunk(
            chunk_id="chk-001",
            doc_id="doc-safety-401",
            file_sha256="a" * 64,
            page_number=2,
            region_id="r004",
            text_content="Ultrasonic wall thickness measurement of nozzle N3 was recorded as 12.4mm.",
            classification="INTERNAL",
            allowed_roles=["engineer", "admin"],
            metadata={"file_name": "Unit4_Inspection_Report.pdf", "box_2d": [0.1, 0.1, 0.3, 0.8], "confidence": 0.98},
        ),
        DocumentChunk(
            chunk_id="chk-002",
            doc_id="doc-std-b31",
            file_sha256="b" * 64,
            page_number=14,
            region_id=None,
            text_content="ASME B31.3 Clause 304.1.2 requires minimum calculated thickness of 9.5mm.",
            classification="INTERNAL",
            allowed_roles=["engineer", "admin"],
            metadata={"file_name": "ASME_B31_3_2022.pdf", "confidence": 1.0},
        ),
    ]


def test_parse_inline_citations_regex():
    """Verifies regex parser extracts bracketed citations with and without region IDs."""
    text = (
        "Inspection report shows measured wall thickness of 12.4mm [Doc: doc-safety-401, p.2#r004]. "
        "The governing ASME standard specifies minimum 9.5mm [Doc: doc-std-b31, p.14]. "
        "Further details are found in [Doc: general-manual, p.1#heading]."
    )

    citations = CitationEngine.parse_inline_citations(text)
    assert len(citations) == 3

    # Token 1
    raw1, doc1, p1, r1 = citations[0]
    assert raw1 == "[Doc: doc-safety-401, p.2#r004]"
    assert doc1 == "doc-safety-401"
    assert p1 == 2
    assert r1 == "r004"

    # Token 2
    raw2, doc2, p2, r2 = citations[1]
    assert raw2 == "[Doc: doc-std-b31, p.14]"
    assert doc2 == "doc-std-b31"
    assert p2 == 14
    assert r2 is None

    # Token 3
    raw3, doc3, p3, r3 = citations[2]
    assert raw3 == "[Doc: general-manual, p.1#heading]"
    assert doc3 == "general-manual"
    assert p3 == 1
    assert r3 == "heading"


def test_parse_inline_citations_no_matches():
    """Verifies parsing returns empty list when text contains no inline citations."""
    assert CitationEngine.parse_inline_citations("Standard plain text without citations.") == []


def test_validate_citations_all_valid(sample_retrieved_chunks: list[DocumentChunk]):
    """Verifies validation passes when all citations match retrieved context chunks."""
    text = (
        "Nozzle N3 wall thickness is 12.4mm [Doc: doc-safety-401, p.2#r004], "
        "conforming to ASME code requirements [Doc: doc-std-b31, p.14]."
    )

    report = CitationEngine.validate_citations(text, sample_retrieved_chunks)
    assert report["valid"] is True
    assert report["total_citations"] == 2
    assert len(report["valid_citations"]) == 2
    assert len(report["hallucinated_citations"]) == 0
    assert report["citation_coverage"] == 1.0

    c1 = report["valid_citations"][0]
    assert c1.document_id == "doc-safety-401"
    assert c1.page_number == 2
    assert c1.region_id == "r004"
    assert c1.file_name == "Unit4_Inspection_Report.pdf"


def test_validate_citations_hallucination_detection(sample_retrieved_chunks: list[DocumentChunk]):
    """Verifies detection and flagging of hallucinated or ungrounded citations."""
    text = (
        "Nozzle thickness is 12.4mm [Doc: doc-safety-401, p.2#r004]. "
        "Fabricator test certificate was signed off [Doc: doc-fake-123, p.99#fake]."
    )

    report = CitationEngine.validate_citations(text, sample_retrieved_chunks)
    assert report["valid"] is False
    assert report["total_citations"] == 2
    assert len(report["valid_citations"]) == 1
    assert len(report["hallucinated_citations"]) == 1
    assert report["citation_coverage"] == 0.5

    hallucinated = report["hallucinated_citations"][0]
    assert hallucinated["document_id"] == "doc-fake-123"
    assert hallucinated["page_number"] == 99
    assert hallucinated["region_id"] == "fake"
    assert "not present in retrieved context" in hallucinated["reason"]


def test_format_reference_table():
    """Verifies rendering of reference appendix tables in markdown and text formats."""
    citations = [
        Citation(
            document_id="doc-safety-401",
            file_name="Unit4_Inspection.pdf",
            file_sha256="abcdef1234567890abcdef1234567890",
            page_number=2,
            region_id="r004",
            excerpt="Measured wall thickness of nozzle N3 was recorded as 12.4mm.",
        ),
        Citation(
            document_id="doc-std-b31",
            file_name="ASME_B31_3.pdf",
            file_sha256="fedcba0987654321fedcba0987654321",
            page_number=14,
            excerpt="Clause 304.1.2 requires minimum calculated thickness of 9.5mm.",
        ),
    ]

    # Markdown format
    md_table = CitationEngine.format_reference_table(citations, format_type="markdown")
    assert "| Citation Tag | Document Name | SHA-256 | Page | Excerpt |" in md_table
    assert "[Doc: doc-safety-401, p.2#r004]" in md_table
    assert "Unit4_Inspection.pdf" in md_table
    assert "[Doc: doc-std-b31, p.14]" in md_table

    # Plain text format
    txt_table = CitationEngine.format_reference_table(citations, format_type="text")
    assert "SOURCE REFERENCES:" in txt_table
    assert "[Doc: doc-safety-401, p.2#r004]" in txt_table


def test_to_lineage_citations():
    """Verifies export to Phase 1 SourceDocumentCitation models for cryptographic sidecars."""
    citations = [
        Citation(
            document_id="doc-insp-001",
            file_name="insp_report.pdf",
            file_sha256="12345" * 12,
            page_number=3,
            region_id="r001",
            excerpt="Piping vibration within tolerance.",
            bounding_box=[0.1, 0.2, 0.3, 0.4],
        )
    ]

    lineage_citations = CitationEngine.to_lineage_citations(citations)
    assert len(lineage_citations) == 1
    lc = lineage_citations[0]
    assert isinstance(lc, SourceDocumentCitation)
    assert lc.document_id == "doc-insp-001"
    assert lc.file_name == "insp_report.pdf"
    assert lc.file_sha256 == "12345" * 12
    assert lc.page_number == 3
    assert lc.bounding_box == [0.1, 0.2, 0.3, 0.4]
    assert lc.snippet == "Piping vibration within tolerance."


def test_rag_search_tool_execution_and_registry_integration(tmp_path: Path, mock_manifest: ModelManifest):
    """Verifies rag_search tool registration, RBAC clearance enforcement, and execution."""
    adapter = MockModelAdapter(mock_manifest)
    adapter.load()

    db_path = tmp_path / "tool_test_knowledge.sqlite"
    store = SQLiteVectorStore(db_path)

    # Insert test chunks
    c1 = DocumentChunk(
        chunk_id="chunk-valve-01",
        doc_id="doc-valve-manual",
        file_sha256="7" * 64,
        page_number=5,
        region_id="r012",
        text_content="Control valve CV-102 pneumatic actuator requires 4.2 bar supply pressure.",
        classification="INTERNAL",
        allowed_roles=["engineer", "admin"],
        metadata={"file_name": "Valve_Operating_Manual.pdf"},
    )
    c2 = DocumentChunk(
        chunk_id="chunk-pump-01",
        doc_id="doc-pump-manual",
        file_sha256="8" * 64,
        page_number=1,
        text_content="Feed pump P-101 motor rating: 75kW at 2950 RPM.",
        classification="INTERNAL",
        allowed_roles=["engineer", "admin"],
        metadata={"file_name": "Pump_Technical_Specs.pdf"},
    )

    vec1 = adapter.embed([c1.text_content])[0]
    vec2 = adapter.embed([c2.text_content])[0]
    store.insert_chunk(c1, vec1)
    store.insert_chunk(c2, vec2)

    # Register tool
    registry = ToolRegistry()
    register_rag_tools(registry, store, adapter, default_role=UserRole.ENGINEER)

    # Check tool is listed in registry
    tools = registry.list_tools(user_role=UserRole.ENGINEER)
    assert any(t.name == "rag_search" for t in tools)

    # Execute search via ToolRegistry dispatch as Engineer
    output = registry.execute_tool(
        "rag_search",
        {"query": "pneumatic actuator supply pressure", "top_k": 2},
        user_role=UserRole.ENGINEER,
    )

    assert output["total_retrieved"] == 2
    assert output["user_role"] == "engineer"
    top_hit = output["results"][0]
    assert top_hit["chunk_id"] == "chunk-valve-01"
    assert top_hit["doc_id"] == "doc-valve-manual"
    assert top_hit["citation_token"] == "[Doc: doc-valve-manual, p.5#r012]"

    # Verify RBAC clearance check: Auditor role should be denied tool execution
    # (since rag_search requires UserRole.ENGINEER)
    with pytest.raises(PermissionError):
        registry.execute_tool(
            "rag_search",
            {"query": "test query"},
            user_role=UserRole.AUDITOR,
        )
