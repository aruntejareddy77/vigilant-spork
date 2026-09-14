---
phase: "06-sih-end-to-end-demonstration-workflows-verification"
plan: "06-01"
subsystem: "demos"
tags:
  - "sample-assets"
  - "demo-a"
  - "demo-b"
  - "demo-c"
  - "hitl-approval"
  - "sandbox-auto-fix"
  - "drawing-diff"
  - "docx-export"
  - "code-export"
  - "change-register"
requires:
  - "04-01"
  - "04-02"
  - "04-03"
  - "04-04"
  - "05-01"
  - "05-02"
provides:
  - "scripts/generate_sample_assets.py"
  - "samples/refinery_vessel_inspection_v301.png"
  - "samples/historian_sensor_telemetry.csv"
  - "samples/pid_drawing_rev_a.png"
  - "samples/pid_drawing_rev_b.png"
  - "tests/test_demos/__init__.py"
  - "tests/test_demos/conftest.py"
  - "tests/test_demos/test_sample_assets.py"
  - "tests/test_demos/test_demo_a.py"
  - "tests/test_demos/test_demo_b.py"
  - "tests/test_demos/test_demo_c.py"
affects:
  - "06-02-PLAN.md"
tech-stack:
  added: []
  patterns:
    - "Programmatic deterministic sample asset generation via Pillow and standard csv"
    - "OCR extraction and confidence thresholding (<0.85) triggering Human-in-the-Loop review"
    - "AST static analysis blocking network socket/http imports before sandbox execution"
    - "Deterministic self-correction reflection loop recovering from KeyError in isolated CodeSandbox"
    - "P&ID morphological clustering isolating ADDED, REMOVED, and MODIFIED revision diff regions"
    - "Formula injection sanitization escaping leading =, +, -, @ characters in exported CSV records"
key-files:
  created:
    - "scripts/generate_sample_assets.py"
    - "samples/refinery_vessel_inspection_v301.png"
    - "samples/historian_sensor_telemetry.csv"
    - "samples/pid_drawing_rev_a.png"
    - "samples/pid_drawing_rev_b.png"
    - "tests/test_demos/__init__.py"
    - "tests/test_demos/conftest.py"
    - "tests/test_demos/test_sample_assets.py"
    - "tests/test_demos/test_demo_a.py"
    - "tests/test_demos/test_demo_b.py"
    - "tests/test_demos/test_demo_c.py"
  modified:
    - "src/sovereign/multimodal/ocr.py"
key-decisions:
  - "Generated deterministic high-resolution test assets (A4 1240x1754 inspection scan, 10,001-row telemetry CSV, 1600x1200 P&ID drawings) entirely via Python scripts with zero external asset downloads."
  - "Enforced 50M pixel safety bounds and 50MB ceiling across all multimodal ingestion pipelines to mitigate T-06-03 decompression bomb DoS."
  - "Implemented simulated HITL review gate in Demo A with confidence thresholding (<0.85) and audit ledger event pairing (APPROVAL_REQUIRED / APPROVAL_GRANTED)."
  - "Configured isolated CodeSandbox in Demo B to catch seeded KeyError ('vibration_rms') and perform single-attempt reflection auto-fix remapping to 'vib_rms_g' before bundle export."
  - "Configured DrawingDiffEngine in Demo C to isolate exactly 3 revision changes (ADDED bypass RV-402, REMOVED drain valve V-102, MODIFIED transmitter PT-201) and sanitize CSV formula injection."
requirements-completed:
  - "DEMO-01"
  - "DEMO-02"
  - "DEMO-03"
---

# Plan 06-01 Summary: Sample Datasets, Test Fixtures & Automated Demo Test Suite

Wave 1 of Phase 6 is complete. All 4 tasks have been implemented, verified, and committed with 12 automated unit and integration tests passing in `tests/test_demos/`.

## Accomplishments

1. **Programmatic Sample Asset Generator (Task 06-01-01 / DEMO-01, DEMO-02, DEMO-03):**
   - Created `scripts/generate_sample_assets.py` synthesizing deterministic industrial test assets in `samples/`:
     - `refinery_vessel_inspection_v301.png` ($1240 \times 1754$ RGB A4 proportions) with title block, checklist rows, discrete findings table, and low-confidence handwritten notes.
     - `historian_sensor_telemetry.csv` ($10,001$ rows) with normal vibration baseline ($0.85-1.35\,g$) and transient anomaly excursion peaking at $5.24\,g$ ($>5.0\,g$) in rows 450–520.
     - `pid_drawing_rev_a.png` & `pid_drawing_rev_b.png` ($1600 \times 1200$ RGB) with identical vessel geometry and 3 discrete revision changes.
   - 3 passing tests in `tests/test_demos/test_sample_assets.py`.

2. **Demo Workflow A Automated Test Suite (Task 06-01-02 / DEMO-01):**
   - Validated image safety validation, OCR layout extraction with normalized $[0.0, 1.0]$ bounding boxes, and confidence scoring.
   - Verified that handwritten pitting finding ($0.78 < 0.85$) triggers `needs_review=True`.
   - Verified HITL approval gate logging `APPROVAL_REQUIRED` and `APPROVAL_GRANTED` to `AuditLedger`.
   - Verified generated Word document (`Refinery_Inspection_Approval_Note.docx`) in `/local/output` with zebra-striped findings table, severity badges, spatial citation `doc-v301#p1-r004`, and W3C PROV-O lineage sidecar.
   - 3 passing tests in `tests/test_demos/test_demo_a.py`.

3. **Demo Workflow B Automated Test Suite (Task 06-01-03 / DEMO-02):**
   - Validated AST static safety check blocking network libraries (`socket`, `requests`, `urllib`, `http`).
   - Verified isolated `CodeSandbox` execution with seeded `KeyError: 'vibration_rms'`.
   - Verified reflection auto-fix remapping column to `'vib_rms_g'` and succeeding on Attempt 1 with exit code 0.
   - Verified `CodeArtifactExporter` bundling runnable `.py`, execution `.log`, input CSV fixture, and `.lineage.json` into `/local/output`.
   - 3 passing tests in `tests/test_demos/test_demo_b.py`.

4. **Demo Workflow C Automated Test Suite (Task 06-01-04 / DEMO-03):**
   - Verified `DrawingDiffEngine.compare_revisions` isolating exactly 3 diff regions (`ADDED`, `REMOVED`, `MODIFIED`).
   - Verified `VisualOverlayRenderer` generating high-contrast overlay `.png` with numbered circular badges and title block.
   - Verified `ChangeRegisterGenerator` exporting styled Word table and formula-sanitized CSV change register.
   - 3 passing tests in `tests/test_demos/test_demo_c.py`.

## Verification Results
- 12 demo tests passing in `tests/test_demos/`.
- All 389 repository tests passing across Phases 1 through 6.
