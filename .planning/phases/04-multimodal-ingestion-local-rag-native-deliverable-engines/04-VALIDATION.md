---
phase: "04"
slug: "multimodal-ingestion-local-rag-native-deliverable-engines"
status: draft
nyquist_compliant: true
wave_0_complete: false
created: "2026-09-11"
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|:---|:---|
| **Framework** | pytest 9.1.1 (Python 3.11) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest -v tests/test_multimodal/ tests/test_rag/ tests/test_deliverables/ tests/test_vision/` |
| **Full suite command** | `pytest -v` |
| **Estimated runtime** | ~12 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command for affected module (`pytest -v tests/test_multimodal/...`)
- **After every plan wave:** Run `pytest -v tests/test_multimodal/ tests/test_rag/ tests/test_deliverables/ tests/test_vision/`
- **Before Phase 4 completion:** Full suite (`pytest -v`) must be green (Phase 1, 2, 3 tests + all Phase 4 tests)
- **Max feedback latency:** 12 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| `04-01-01` | 01 | 1 | MMOD-01 | T-04-03 | BaseOCRBackend & DeterministicMockOCRBackend extract text and layout offline without external network calls | unit | `pytest -v tests/test_multimodal/test_ocr_engine.py` | ❌ W0 | ⬜ pending |
| `04-01-02` | 01 | 1 | MMOD-02 | T-04-05 | FormExtractor detects checkboxes, handwriting, and flags confidence < 0.85 as NEEDS_REVIEW | unit | `pytest -v tests/test_multimodal/test_handwriting_forms.py` | ❌ W0 | ⬜ pending |
| `04-01-03` | 01 | 1 | MMOD-04 | — | NormalizedDocument preserves page indices, normalized 2D boxes [ymin, xmin, ymax, xmax], and stable region IDs | unit | `pytest -v tests/test_multimodal/test_normalized_document.py` | ❌ W0 | ⬜ pending |
| `04-02-01` | 02 | 2 | RAG-01 | T-04-06 | Local document chunking and SQLiteVectorStore index/retrieve 768-dim float blobs in SQLite WAL | unit | `pytest -v tests/test_rag/test_local_vector_store.py` | ❌ W0 | ⬜ pending |
| `04-02-02` | 02 | 2 | RAG-03 | T-04-01 | SQL-level pre-filtering by UserRole strictly prevents unauthorized chunk leakage | unit | `pytest -v tests/test_rag/test_rbac_rag_filter.py` | ❌ W0 | ⬜ pending |
| `04-02-03` | 02 | 2 | RAG-02 | — | CitationEngine generates bracketed citations linking generated text to source document IDs and regions | unit | `pytest -v tests/test_rag/test_citation_engine.py` | ❌ W0 | ⬜ pending |
| `04-03-01` | 03 | 3 | DELV-01 | T-04-04 | DocxDeliverableGenerator writes corporate-styled Word approval note with findings tables and lineage | unit | `pytest -v tests/test_deliverables/test_docx_generator.py` | ❌ W0 | ⬜ pending |
| `04-03-02` | 03 | 3 | DELV-02 | T-04-02 | XlsxDeliverableGenerator writes Excel sheets with live recalculable formulas and pass/fail cells | unit | `pytest -v tests/test_deliverables/test_xlsx_generator.py` | ❌ W0 | ⬜ pending |
| `04-03-03` | 03 | 3 | DELV-03 | — | PptxDeliverableGenerator creates PowerPoint decks with native editable OOXML chart objects | unit | `pytest -v tests/test_deliverables/test_pptx_generator.py` | ❌ W0 | ⬜ pending |
| `04-03-04` | 03 | 3 | DELV-04, DELV-05 | T-04-04 | CodeArtifactExporter & CalculationTraceExporter save reproducible code logs and ASME B31.3 traces | integration | `pytest -v tests/test_deliverables/test_code_artifact_export.py tests/test_deliverables/test_calc_trace_export.py` | ❌ W0 | ⬜ pending |
| `04-04-01` | 04 | 4 | MMOD-03 | T-04-03 | DrawingDiffEngine compares P&ID drawing revisions, detects changes, and renders color-coded overlay | unit | `pytest -v tests/test_vision/test_drawing_diff.py` | ❌ W0 | ⬜ pending |
| `04-04-02` | 04 | 4 | MMOD-03 | — | ChangeRegisterGenerator extracts semantic P&ID modifications and diff_drawings tool exports report | integration | `pytest -v tests/test_vision/test_drawing_diff.py tests/test_vision/test_change_register.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Add `python-docx`, `openpyxl`, `python-pptx`, `pypdf` to `pyproject.toml`
- [ ] `src/sovereign/multimodal/`: Directory structure for OCR, form extraction, and normalized document schema
- [ ] `src/sovereign/rag/`: Directory structure for chunking, SQLite vector store, and citations
- [ ] `src/sovereign/deliverables/`: Directory structure for Word, Excel, PowerPoint, and trace exporters
- [ ] `src/sovereign/vision/`: Directory structure for drawing differencing and annotation overlay
- [ ] `tests/test_multimodal/`, `tests/test_rag/`, `tests/test_deliverables/`, `tests/test_vision/`: Test directories and fixtures

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all package structures and test suites
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-09-11
