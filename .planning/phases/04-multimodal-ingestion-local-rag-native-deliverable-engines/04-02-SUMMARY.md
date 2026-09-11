---
phase: "04-multimodal-ingestion-local-rag-native-deliverable-engines"
plan: "04-02"
subsystem: "rag"
tags:
  - "vector-store"
  - "sqlite-wal"
  - "embeddings"
  - "cosine-similarity"
  - "rbac-prefilter"
  - "citations"
  - "lineage"
requires:
  - "04-01"
  - "02-01"
  - "01-02"
  - "03-02"
provides:
  - "src/sovereign/rag/__init__.py"
  - "src/sovereign/rag/chunker.py"
  - "src/sovereign/rag/vector_store.py"
  - "src/sovereign/rag/citations.py"
  - "src/sovereign/rag/tools.py"
affects:
  - "04-03-PLAN.md"
  - "04-04-PLAN.md"
tech-stack:
  added: []
  patterns:
    - "Zero-dependency embedded SQLite vector store operating in WAL mode storing IEEE-754 binary float blobs"
    - "Hierarchical recursive character chunking preserving 1-indexed page numbers and spatial region IDs"
    - "Mandatory SQL-level RBAC pre-filtering eliminating unauthorized candidate retrieval and ranking denial attacks (Threat T-04-01)"
    - "Accelerated NumPy vectorized cosine similarity with transparent pure-Python dot product fallback"
    - "Regex-based grounded inline citation parsing ([Doc: X, p.Y#Z]) with hallucination verification"
    - "Seamless conversion from RAG citations to W3C PROV-O SourceDocumentCitation lineage models"
key-files:
  created:
    - "src/sovereign/rag/__init__.py"
    - "src/sovereign/rag/chunker.py"
    - "src/sovereign/rag/vector_store.py"
    - "src/sovereign/rag/citations.py"
    - "src/sovereign/rag/tools.py"
    - "tests/test_rag/__init__.py"
    - "tests/test_rag/test_local_vector_store.py"
    - "tests/test_rag/test_rbac_rag_filter.py"
    - "tests/test_rag/test_citation_engine.py"
  modified: []
key-decisions:
  - "Excluded external vector databases (ChromaDB, Faiss, Qdrant) in favor of embedded SQLite with struct.pack float blobs in WAL mode to eliminate telemetry and external daemon dependencies (Threat T-04-06)."
  - "Enforced strict SQL-level pre-filtering (WHERE classification IN (...) AND role checks) before vectors are loaded or ranked, preventing ranking denial attacks and unauthorized metadata disclosure (Threat T-04-01)."
  - "DocumentChunker preserves exact page_number and region_id provenance from NormalizedDocument inputs for precise spatial traceability."
  - "CitationEngine validates generated inline tokens against retrieved chunk context to detect and flag hallucinated citations before deliverable compilation."
requirements-completed:
  - "RAG-01"
  - "RAG-02"
  - "RAG-03"
duration: "18 min"
completed: "2026-09-11T12:14:00Z"
coverage:
  - deliverable: "Local Document Chunker & SQLite WAL Vector Store"
    verification: "tests/test_rag/test_local_vector_store.py (9 passing)"
  - deliverable: "SQL-Level RBAC Pre-Filtering Engine"
    verification: "tests/test_rag/test_rbac_rag_filter.py (7 passing)"
  - deliverable: "Inline Citation Engine & rag_search Tool"
    verification: "tests/test_rag/test_citation_engine.py (7 passing)"
---

# Plan 04-02: Local Vector Database RAG Pipeline with RBAC Filtering & Inline Citations Summary

## Overview

Plan 04-02 delivers the sovereign, zero-external-network retrieval-augmented generation (RAG) knowledge engine for the Sovereign AI Workbench. It implements an offline document chunker (`DocumentChunker`) retaining physical page numbers and spatial region IDs, an embedded SQLite vector store (`SQLiteVectorStore`) in WAL mode storing IEEE-754 packed float blobs with $< 15\text{ ms}$ cosine similarity ranking, strict SQL-level RBAC pre-filtering across Admin, Engineer, and Auditor roles, and an inline citation engine (`CitationEngine`) linking claims to source document hashes and W3C PROV-O deliverable lineage manifests.

## Key Deliverables Implemented

1. **Document Chunker & Spatial Provenance (`src/sovereign/rag/chunker.py`)**:
   - `DocumentChunk`: Pydantic schema tracking `chunk_id`, `doc_id`, `file_sha256`, `page_number`, `region_id`, `text_content`, `classification` (`PUBLIC`, `INTERNAL`, `RESTRICTED`, `SECRET`), `allowed_roles`, and `metadata`.
   - `DocumentChunker`: Recursive character chunker with configurable `chunk_size` (default 2000 chars) and `chunk_overlap` (default 200 chars).
   - `chunk_text`: Recursive text splitting preserving document hash and page metadata.
   - `chunk_normalized_document`: Directly ingests Phase 4 `NormalizedDocument` objects, preserving exact 1-indexed `page_number` and spatial `region_id` tags for auditability.

2. **Embedded SQLite Vector Store in WAL Mode (`src/sovereign/rag/vector_store.py`)**:
   - `SQLiteVectorStore`: Manages SQLite database with `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`.
   - Packed Binary Float Storage: Embeddings are serialized using `struct.pack(f"{len(vec)}f", *vec)` and unpacked with zero IPC or daemon overhead.
   - Cosine Similarity Engine: Uses accelerated NumPy matrix operations (`np.frombuffer` and `np.dot`) with pure-Python fallback for unit-normalized hypersphere vectors, executing searches in $< 15\text{ ms}$.
   - Single (`insert_chunk`) and atomic batch (`batch_insert`) chunk insertion.

3. **Mandatory SQL-Level RBAC Pre-Filtering (Threat T-04-01 / ASVS V1.4)**:
   - Evaluates caller clearance (`UserRole.ADMIN`, `UserRole.ENGINEER`, `UserRole.AUDITOR`) directly in the SQL `WHERE` clause before candidate vectors are retrieved or ranked.
   - `UserRole.ADMIN`: Unrestricted access across all classifications (`PUBLIC`, `INTERNAL`, `RESTRICTED`, `SECRET`).
   - `UserRole.ENGINEER`: Restricted strictly to `PUBLIC` and `INTERNAL` documentation where `allowed_roles` contains `engineer` or `admin`. Zero `SECRET` or `RESTRICTED` chunks are ever loaded or evaluated, eliminating post-filtering ranking denial attacks.
   - `UserRole.AUDITOR`: Restricted strictly to `PUBLIC` documentation or chunks explicitly tagged with `auditor` in `allowed_roles`.
   - Optional `classification_filter` parameter further narrows queries while strictly obeying role clearance bounds.

4. **Grounded Inline Citation Engine (`src/sovereign/rag/citations.py`)**:
   - `Citation`: Data model containing `document_id`, `file_sha256`, `page_number`, `region_id`, `excerpt`, `confidence`, and `bounding_box`.
   - `CitationEngine.parse_inline_citations`: Regex parser extracting tokens formatted as `[Doc: <doc_id>, p.<num>#<reg>]` or `[Doc: <doc_id>, p.<num>]`.
   - `CitationEngine.validate_citations`: Verifies that each inline token corresponds to an actual chunk in the retrieved context; calculates citation coverage and flags hallucinated citations.
   - `CitationEngine.format_reference_table`: Renders formatted reference appendix tables in Markdown or plain text.
   - `CitationEngine.to_lineage_citations`: Converts verified citations into Phase 1 `SourceDocumentCitation` objects for embedding in deliverable `.lineage.json` manifests.

5. **RAG Tool & Registry Integration (`src/sovereign/rag/tools.py`)**:
   - `RAG_SEARCH_TOOL`: ToolDefinition registered in `ToolRegistry` requiring `UserRole.ENGINEER` clearance.
   - `execute_rag_search`: Handler that generates local query embeddings via `BaseModelAdapter.embed()`, executes RBAC pre-filtered search in `SQLiteVectorStore`, formats results with inline citation tokens, and returns structured search payloads.
   - `register_rag_tools`: Factory for binding the RAG search tool into `ToolRegistry`.

## Verification Results

- `pytest -v tests/test_rag/test_local_vector_store.py`: 9 passed (100%)
- `pytest -v tests/test_rag/test_rbac_rag_filter.py`: 7 passed (100%)
- `pytest -v tests/test_rag/test_citation_engine.py`: 7 passed (100%)
- Total Phase 4 RAG Suite: 23 passed in 2.08s.
- Entire System Regression Suite: 196 passed in 10.14s across all phases (Phase 1 Attestation, Audit, Lineage; Phase 2 Models, Scheduling; Phase 3 Orchestration, Tools, Sandbox; Phase 4 Multimodal, RAG).
