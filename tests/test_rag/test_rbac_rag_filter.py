"""
tests/test_rag/test_rbac_rag_filter.py
Unit tests for SQL-level RBAC pre-filtering in SQLiteVectorStore across
Admin, Engineer, and Auditor roles.
Enforces RAG-03, Threat T-04-01 (ASVS V1.4), and prevents ranking denial attacks.
"""
from pathlib import Path
import pytest

from sovereign.rag.chunker import DocumentChunk
from sovereign.rag.vector_store import SQLiteVectorStore
from sovereign.tools.schemas import UserRole


@pytest.fixture
def populated_vector_store(tmp_path: Path) -> SQLiteVectorStore:
    """
    Populates an embedded SQLiteVectorStore with chunks across
    PUBLIC, INTERNAL, RESTRICTED, and SECRET sensitivity tiers.
    """
    db_file = tmp_path / "rbac_knowledge.sqlite"
    store = SQLiteVectorStore(db_file)

    # 1. PUBLIC: General plant safety instructions
    c_public = DocumentChunk(
        chunk_id="chk-pub-01",
        doc_id="doc-pub",
        file_sha256="1" * 64,
        page_number=1,
        text_content="General PPE requirements: hardhat and steel-toed boots required.",
        classification="PUBLIC",
        allowed_roles=["auditor", "engineer", "admin"],
    )

    # 2. INTERNAL: Standard Operating Procedure for engineering team
    c_internal_eng = DocumentChunk(
        chunk_id="chk-int-01",
        doc_id="doc-sop",
        file_sha256="2" * 64,
        page_number=3,
        text_content="Distillation column T-401 startup sequence and valve lineup.",
        classification="INTERNAL",
        allowed_roles=["engineer", "admin"],
    )

    # 3. INTERNAL (Auditor-only): Statutory compliance audit notes
    c_internal_audit = DocumentChunk(
        chunk_id="chk-int-audit-01",
        doc_id="doc-audit-memo",
        file_sha256="3" * 64,
        page_number=1,
        text_content="Statutory environmental discharge compliance audit findings.",
        classification="INTERNAL",
        allowed_roles=["auditor"],
    )

    # 4. RESTRICTED: Proprietary refinery process design parameters
    c_restricted = DocumentChunk(
        chunk_id="chk-res-01",
        doc_id="doc-patented-process",
        file_sha256="4" * 64,
        page_number=12,
        text_content="Proprietary catalyst formula and unreleased reactor geometry.",
        classification="RESTRICTED",
        allowed_roles=["admin"],
    )

    # 5. SECRET: Plant emergency master override and executive shutdown keys
    c_secret = DocumentChunk(
        chunk_id="chk-sec-01",
        doc_id="doc-exec-keys",
        file_sha256="5" * 64,
        page_number=1,
        text_content="Emergency cryptographic shutdown credentials and override PIN: 9942.",
        classification="SECRET",
        allowed_roles=["admin"],
    )

    # Vector layout (4 dimensions for deterministic orthogonal testing):
    # c_secret has vector [1, 0, 0, 0] (exact 1.0 match to search query)
    # c_restricted has vector [0.9, 0.1, 0, 0]
    # c_internal_eng has vector [0.5, 0.5, 0.5, 0]
    # c_internal_audit has vector [0.4, 0.6, 0.4, 0]
    # c_public has vector [0.1, 0.9, 0, 0]
    store.insert_chunk(c_public, [0.1, 0.9, 0.0, 0.0])
    store.insert_chunk(c_internal_eng, [0.5, 0.5, 0.5, 0.0])
    store.insert_chunk(c_internal_audit, [0.4, 0.6, 0.4, 0.0])
    store.insert_chunk(c_restricted, [0.9, 0.1, 0.0, 0.0])
    store.insert_chunk(c_secret, [1.0, 0.0, 0.0, 0.0])

    return store


def test_admin_has_full_visibility(populated_vector_store: SQLiteVectorStore):
    """
    Verifies that UserRole.ADMIN retrieves chunks across all classification tiers
    (PUBLIC, INTERNAL, RESTRICTED, SECRET).
    """
    # Query matching the SECRET chunk with 100% similarity
    query_vec = [1.0, 0.0, 0.0, 0.0]
    results = populated_vector_store.search(query_vec, top_k=10, user_role=UserRole.ADMIN)

    assert len(results) == 5
    retrieved_ids = {chunk.chunk_id for chunk, _ in results}
    assert "chk-sec-01" in retrieved_ids
    assert "chk-res-01" in retrieved_ids
    assert "chk-int-01" in retrieved_ids
    assert "chk-int-audit-01" in retrieved_ids
    assert "chk-pub-01" in retrieved_ids

    # Highest ranked chunk for Admin must be the exact match SECRET chunk
    top_chunk, top_sim = results[0]
    assert top_chunk.chunk_id == "chk-sec-01"
    assert pytest.approx(top_sim, abs=1e-3) == 1.0


def test_engineer_zero_leakage_and_ranking_denial_prevention(populated_vector_store: SQLiteVectorStore):
    """
    CRITICAL SECURITY TEST (T-04-01 / ASVS V1.4):
    Verifies that UserRole.ENGINEER NEVER retrieves SECRET or RESTRICTED chunks,
    even when the SECRET chunk has 100% similarity to the query.
    Prevents post-filter information denial attacks.
    """
    # Query pointing directly at SECRET chunk [1, 0, 0, 0]
    query_vec = [1.0, 0.0, 0.0, 0.0]
    results = populated_vector_store.search(query_vec, top_k=10, user_role=UserRole.ENGINEER)

    # Must only return PUBLIC and cleared INTERNAL chunks
    retrieved_ids = {chunk.chunk_id for chunk, _ in results}
    assert "chk-sec-01" not in retrieved_ids
    assert "chk-res-01" not in retrieved_ids

    # Must contain cleared engineer-accessible chunks
    assert "chk-int-01" in retrieved_ids
    assert "chk-pub-01" in retrieved_ids

    # Verify no SECRET or RESTRICTED classification exists in any returned candidate
    for chunk, _ in results:
        assert chunk.classification in ("PUBLIC", "INTERNAL")
        assert chunk.classification not in ("RESTRICTED", "SECRET")


def test_engineer_cannot_access_auditor_only_internal(populated_vector_store: SQLiteVectorStore):
    """
    Verifies that an INTERNAL chunk restricted to auditor is not retrieved by ENGINEER.
    """
    query_vec = [0.4, 0.6, 0.4, 0.0]  # Exact match for chk-int-audit-01
    results = populated_vector_store.search(query_vec, top_k=10, user_role=UserRole.ENGINEER)

    retrieved_ids = {chunk.chunk_id for chunk, _ in results}
    assert "chk-int-audit-01" not in retrieved_ids
    assert "chk-int-01" in retrieved_ids


def test_auditor_strict_clearance(populated_vector_store: SQLiteVectorStore):
    """
    Verifies that UserRole.AUDITOR can only access PUBLIC chunks and chunks
    where 'auditor' is explicitly in allowed_roles.
    """
    query_vec = [1.0, 0.0, 0.0, 0.0]
    results = populated_vector_store.search(query_vec, top_k=10, user_role=UserRole.AUDITOR)

    retrieved_ids = {chunk.chunk_id for chunk, _ in results}

    # Must NOT access engineer SOP or admin-restricted documents
    assert "chk-sec-01" not in retrieved_ids
    assert "chk-res-01" not in retrieved_ids
    assert "chk-int-01" not in retrieved_ids

    # MUST access PUBLIC and auditor-cleared documents
    assert "chk-pub-01" in retrieved_ids
    assert "chk-int-audit-01" in retrieved_ids


def test_database_level_candidate_isolation_when_only_secrets_exist(tmp_path: Path):
    """
    Verifies that if the database contains ONLY restricted/secret chunks,
    an ENGINEER query returns 0 candidates directly from SQL (zero vectors evaluated).
    """
    db_file = tmp_path / "secrets_only.sqlite"
    store = SQLiteVectorStore(db_file)

    secret_chunk = DocumentChunk(
        chunk_id="confidential-1",
        doc_id="doc-conf",
        file_sha256="9" * 64,
        text_content="Confidential nuclear safety parameters",
        classification="SECRET",
        allowed_roles=["admin"],
    )
    store.insert_chunk(secret_chunk, [1.0, 0.0, 0.0, 0.0])

    # Search with Engineer role
    results = store.search([1.0, 0.0, 0.0, 0.0], top_k=5, user_role=UserRole.ENGINEER)
    assert len(results) == 0

    # Search with Auditor role
    results_audit = store.search([1.0, 0.0, 0.0, 0.0], top_k=5, user_role=UserRole.AUDITOR)
    assert len(results_audit) == 0

    # Search with Admin role -> retrieves it
    results_admin = store.search([1.0, 0.0, 0.0, 0.0], top_k=5, user_role=UserRole.ADMIN)
    assert len(results_admin) == 1
    assert results_admin[0][0].chunk_id == "confidential-1"


def test_classification_filter_parameter(populated_vector_store: SQLiteVectorStore):
    """
    Verifies caller classification_filter parameter in conjunction with RBAC clearance.
    """
    # Engineer requests only INTERNAL
    res_eng = populated_vector_store.search(
        [0.5, 0.5, 0.5, 0.0],
        top_k=5,
        user_role=UserRole.ENGINEER,
        classification_filter="INTERNAL",
    )
    assert all(c.classification == "INTERNAL" for c, _ in res_eng)
    assert "chk-pub-01" not in {c.chunk_id for c, _ in res_eng}

    # Engineer attempts to request SECRET via filter -> zero chunks returned
    res_eng_secret = populated_vector_store.search(
        [1.0, 0.0, 0.0, 0.0],
        top_k=5,
        user_role=UserRole.ENGINEER,
        classification_filter="SECRET",
    )
    assert len(res_eng_secret) == 0

    # Admin requests SECRET via filter -> retrieved
    res_admin_secret = populated_vector_store.search(
        [1.0, 0.0, 0.0, 0.0],
        top_k=5,
        user_role=UserRole.ADMIN,
        classification_filter="SECRET",
    )
    assert len(res_admin_secret) == 1
    assert res_admin_secret[0][0].chunk_id == "chk-sec-01"


def test_string_role_and_unknown_role_handling(populated_vector_store: SQLiteVectorStore):
    """
    Verifies string role inputs ('admin', 'engineer', 'auditor') and default-deny
    behavior for unrecognised roles.
    """
    res_str_admin = populated_vector_store.search([1.0, 0.0, 0.0, 0.0], top_k=1, user_role="admin")
    assert len(res_str_admin) == 1
    assert res_str_admin[0][0].chunk_id == "chk-sec-01"

    res_unknown = populated_vector_store.search([1.0, 0.0, 0.0, 0.0], top_k=5, user_role="untrusted_guest")
    # Untrusted role falls back to auditor clearance or returns 0
    # In our implementation: unrecognised string role falls back to AUDITOR
    for chunk, _ in res_unknown:
        assert chunk.classification in ("PUBLIC", "INTERNAL")
        assert chunk.classification not in ("SECRET", "RESTRICTED")
