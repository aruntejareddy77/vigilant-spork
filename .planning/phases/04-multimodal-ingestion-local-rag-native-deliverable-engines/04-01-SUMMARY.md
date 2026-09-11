---
phase: "04-multimodal-ingestion-local-rag-native-deliverable-engines"
plan: "04-01"
subsystem: "multimodal"
tags:
  - "ocr"
  - "tesseract"
  - "deterministic-mock"
  - "handwriting"
  - "form-extraction"
  - "confidence-scoring"
  - "hitl-gate"
  - "normalized-document"
  - "rfc8785"
requires:
  - "01-01"
  - "03-01"
  - "03-02"
provides:
  - "src/sovereign/multimodal/__init__.py"
  - "src/sovereign/multimodal/ocr.py"
  - "src/sovereign/multimodal/forms.py"
  - "src/sovereign/multimodal/models.py"
  - "src/sovereign/multimodal/tools.py"
affects:
  - "04-02-PLAN.md"
  - "04-03-PLAN.md"
  - "04-04-PLAN.md"
tech-stack:
  added:
    - "pypdf>=4.0.0"
    - "pytesseract>=0.3.10"
    - "python-docx>=1.1.0"
    - "openpyxl>=3.1.2"
    - "python-pptx>=0.6.23"
  patterns:
    - "Pluggable offline OCR architecture with pure-Python DeterministicMockOCRBackend fallback"
    - "Strict Pillow image bounds (MAX_IMAGE_PIXELS = 50_000_000, 50MB size limit) preventing decompression bombs (Threat T-04-03)"
    - "Mandatory confidence threshold (0.85) flagging low-confidence handwriting for Human-in-the-Loop review (Threat T-04-05)"
    - "Canonical RFC 8785 JSON representation preserving 1-indexed pages and normalized 2D coordinates [ymin, xmin, ymax, xmax]"
    - "Rigid ToolRegistry integration with UserRole.ENGINEER clearance for agentic document ingestion"
key-files:
  created:
    - "src/sovereign/multimodal/__init__.py"
    - "src/sovereign/multimodal/ocr.py"
    - "src/sovereign/multimodal/forms.py"
    - "src/sovereign/multimodal/models.py"
    - "src/sovereign/multimodal/tools.py"
    - "tests/test_multimodal/__init__.py"
    - "tests/test_multimodal/test_ocr_engine.py"
    - "tests/test_multimodal/test_handwriting_forms.py"
    - "tests/test_multimodal/test_normalized_document.py"
  modified:
    - "pyproject.toml"
key-decisions:
  - "Enforced 50M pixel and 50MB ceiling across all ingested image and PDF formats to mitigate T-04-03 decompression bomb DoS."
  - "Implemented pure-Python DeterministicMockOCRBackend producing realistic inspection checklist layout blocks and reproducible hashes for 100% offline test coverage in headless CI."
  - "Strictly gated sub-0.85 confidence form and handwriting readings to trigger needs_review=True and build_hitl_interrupt_payload for Phase 3 StateGraph interruption."
  - "Unified all multimodal extractions into NormalizedDocument with stable spatial region identifiers (p{page}-r{idx:03d}) and canonical RFC 8785 JSON export."
requirements-completed:
  - "MMOD-01"
  - "MMOD-02"
  - "MMOD-04"
duration: "16 min"
completed: "2026-09-11T12:05:00Z"
coverage:
  - deliverable: "Offline OCR Backends & Image Security Boundaries"
    verification: "tests/test_multimodal/test_ocr_engine.py (14 passing)"
  - deliverable: "Form & Handwriting Extraction with HITL Gate"
    verification: "tests/test_multimodal/test_handwriting_forms.py (8 passing)"
  - deliverable: "Unified NormalizedDocument Schema & ocr_document Tool"
    verification: "tests/test_multimodal/test_normalized_document.py (6 passing)"
---

# Plan 04-01: Offline OCR and Structured Form Handwriting Extraction Pipeline Summary

## Overview

Plan 04-01 establishes the sovereign, zero-network multimodal ingestion and form extraction pipeline for the Sovereign AI Workbench. It delivers zero-cloud OCR abstraction, structured checklist and handwriting parsing with confidence gating, and a canonical document representation preserving physical page indices and normalized 2D spatial coordinates for auditability and citations.

## Key Deliverables Implemented

1. **Offline OCR Backend Abstraction (`src/sovereign/multimodal/ocr.py`)**:
   - `BaseOCRBackend`: Abstract base class specifying `extract_text_and_layout` and `is_available`.
   - `TesseractOCRBackend`: Local binary wrapper via `pytesseract`, extracting words/lines and normalizing coordinates to $[0.0, 1.0]$.
   - `DeterministicMockOCRBackend`: Pure-Python, zero-binary mock generating realistic inspection checklist blocks and bounding boxes seeded reproducibly by image SHA-256 hashes.
   - `get_ocr_backend`: Factory auto-selecting `DeterministicMockOCRBackend` when Tesseract binary is absent or when `force_mock=True`.
   - Image Security Bounds: Mitigated threat T-04-03 by enforcing `MAX_IMAGE_PIXELS = 50_000_000`, `MAX_IMAGE_FILE_SIZE = 50MB`, `MAX_PDF_PAGES = 100`, path traversal fencing, and header verification.

2. **Form & Handwriting Extraction Engine (`src/sovereign/multimodal/forms.py`)**:
   - `CheckboxState`: `CHECKED`, `UNCHECKED`, `UNKNOWN`.
   - `FormFieldType`: `TEXT`, `NUMBER`, `CHECKBOX`, `DATE`, `SIGNATURE`.
   - `RawFormField`: Field container tracking key, value, box, confidence, and review flags.
   - `FormExtractor`: Parses structured key-value pairs, checkbox markers (`[x]`, `[ ]`, `(✓)`), numeric measurements, dates, and handwriting annotations.
   - Confidence Gating ($\tau = 0.85$): Any field with confidence $< 0.85$ automatically sets `needs_review=True` and generates a descriptive `review_reason`.
   - `build_hitl_interrupt_payload`: Formats low-confidence flagged fields into an interrupt dictionary compatible with Phase 3 `GraphInterrupt` / `AgentRuntime`.

3. **Unified Document Schema & Tool Registry Integration (`src/sovereign/multimodal/models.py` & `src/sovereign/multimodal/tools.py`)**:
   - `NormalizedDocument`, `DocumentPage`, `DocumentRegion`, `FormField`, `ExtractedTable`, `ModalityType`.
   - Stable spatial region IDs: `p{page_num}-r{idx:03d}` (e.g., `p1-r004`) allowing precise grounded inline citations.
   - `NormalizedDocument.from_ocr_results`: Classmethod assembling multi-page OCR and form outputs into a canonical document hierarchy.
   - `to_canonical_json`: RFC 8785 canonical JSON serialization for cryptographic ledger hashing.
   - `ocr_document` Tool: Registered in `ToolRegistry` with `UserRole.ENGINEER` clearance, executing fenced document ingestion and returning structured extractions and HITL interrupt status.

## Verification Results

- `pytest -v tests/test_multimodal/test_ocr_engine.py`: 14 passed (100%)
- `pytest -v tests/test_multimodal/test_handwriting_forms.py`: 8 passed (100%)
- `pytest -v tests/test_multimodal/test_normalized_document.py`: 6 passed (100%)
- Total Phase 4 Multimodal Suite: 28 passed in 1.24s.
- Entire System Regression Suite: 173 passed in 8.78s across Phase 1, Phase 2, Phase 3, and Phase 4.
