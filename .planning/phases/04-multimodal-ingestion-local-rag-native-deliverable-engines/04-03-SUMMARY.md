---
phase: "04-multimodal-ingestion-local-rag-native-deliverable-engines"
plan: "04-03"
subsystem: "deliverables"
tags:
  - "office-deliverables"
  - "docx"
  - "xlsx-live-formulas"
  - "pptx-native-charts"
  - "formula-sanitization"
  - "code-export"
  - "calculation-trace"
  - "asme-b313"
  - "lineage"
requires:
  - "04-01"
  - "04-02"
  - "01-02"
  - "03-02"
provides:
  - "src/sovereign/deliverables/__init__.py"
  - "src/sovereign/deliverables/docx.py"
  - "src/sovereign/deliverables/xlsx.py"
  - "src/sovereign/deliverables/pptx.py"
  - "src/sovereign/deliverables/code_export.py"
  - "src/sovereign/deliverables/calc_trace.py"
  - "src/sovereign/deliverables/tools.py"
affects:
  - "04-04-PLAN.md"
tech-stack:
  added: []
  patterns:
    - "Native pure-Python OOXML document compilation (python-docx, openpyxl, python-pptx) requiring zero host Office/LibreOffice binaries"
    - "Corporate typography and layout: Primary Navy (#1F497D), Secondary Slate (#595959), Body Charcoal (#262626)"
    - "Dynamic live Excel formulas (=C7*C8/(2*(...))) enabling real-time engineering recalculation and sensitivity analysis"
    - "Three-tier spreadsheet visual hierarchy: Inputs (#D9E1F2), Calculations (#FFF2CC), Verification (#E2EFDA / #FCE4D6)"
    - "DDE and formula injection mitigation escaping literal strings starting with '=', '+', '-', '@' with a leading apostrophe"
    - "Native editable OOXML chart part generation (CategoryChartData) in 16:9 widescreen presentation slides"
    - "Reproducible Python code bundles pairing scripts, execution logs, and data fixtures in /local/output"
    - "Full mathematical derivation trace export (ASME B31.3 Clause 304.1.2) to Markdown, JSON, Word, and Excel"
    - "Mandatory cryptographic lineage embedding via LineageEngine into docProps/custom.xml and W3C PROV-O sidecars"
key-files:
  created:
    - "src/sovereign/deliverables/__init__.py"
    - "src/sovereign/deliverables/docx.py"
    - "src/sovereign/deliverables/xlsx.py"
    - "src/sovereign/deliverables/pptx.py"
    - "src/sovereign/deliverables/code_export.py"
    - "src/sovereign/deliverables/calc_trace.py"
    - "src/sovereign/deliverables/tools.py"
    - "tests/test_deliverables/__init__.py"
    - "tests/test_deliverables/test_docx_generator.py"
    - "tests/test_deliverables/test_xlsx_generator.py"
    - "tests/test_deliverables/test_pptx_generator.py"
    - "tests/test_deliverables/test_code_artifact_export.py"
    - "tests/test_deliverables/test_calc_trace_export.py"
  modified: []
key-decisions:
  - "Selected pure-Python OOXML libraries (python-docx, openpyxl, python-pptx) to eliminate desktop office suite binaries, rendering pipelines, or headless daemons in air-gapped environments."
  - "Excel workbooks write live formula strings (=B4*B5/...) instead of static float evaluation results, empowering plant engineers to perform what-if recalculations directly in spreadsheet applications (DELV-02)."
  - "Implemented strict formula trigger sanitization via sanitize_cell_text escaping '=', '+', '-', '@' with leading apostrophe, mitigating Dynamic Data Exchange (DDE) and CSV formula injection attacks (Threat T-04-02)."
  - "Constructed presentation charts strictly as native OOXML chart elements (CategoryChartData in ppt/charts/chart1.xml) rather than static bitmap screenshots, allowing interactive data adjustments during executive review (DELV-03)."
  - "Bound all deliverable outputs to workspace boundary with PathSecurityViolation defenses, preventing traversal attacks (Threat T-04-04)."
  - "Integrated all generators with LineageEngine to inject custom metadata properties (sovereign_session_id, sovereign_model_id, etc.) into docProps/custom.xml and emit sibling .lineage.json manifests."
requirements-completed:
  - "DELV-01"
  - "DELV-02"
  - "DELV-03"
  - "DELV-04"
  - "DELV-05"
duration: "25 min"
completed: "2026-09-11T12:28:00Z"
coverage:
  - deliverable: "Native Microsoft Word (.docx) Generator"
    verification: "tests/test_deliverables/test_docx_generator.py (4 passing)"
  - deliverable: "Native Microsoft Excel (.xlsx) Generator with Live Formulas & Sanitization"
    verification: "tests/test_deliverables/test_xlsx_generator.py (6 passing)"
  - deliverable: "Native Microsoft PowerPoint (.pptx) Generator with Editable OOXML Charts"
    verification: "tests/test_deliverables/test_pptx_generator.py (4 passing)"
  - deliverable: "Reproducible Code Artifact Exporter"
    verification: "tests/test_deliverables/test_code_artifact_export.py (2 passing)"
  - deliverable: "ASME B31.3 Calculation Trace & ToolRegistry Integration"
    verification: "tests/test_deliverables/test_calc_trace_export.py (6 passing)"
---

# Plan 04-03: Native Office Deliverable Generators, Reproducible Code & Calculation Trace Export Summary

## Overview

Plan 04-03 establishes the industrial deliverable generation suite for the Sovereign AI Workbench. Operating entirely offline without external desktop binaries (Microsoft Office, LibreOffice, or headless PDF print drivers), this suite compiles professional native Microsoft Office documents (`.docx`, `.xlsx`, `.pptx`), bundles reproducible executable Python scripts with execution traces, and formats step-by-step engineering calculation derivations (ASME B31.3). Every deliverable carries embedded cryptographic lineage metadata in `docProps/custom.xml` and emits sibling `.lineage.json` W3C PROV-O sidecars.

---

## Deliverables & Modules Implemented

### 1. Word Deliverable Generator (`src/sovereign/deliverables/docx.py`)
- **Requirement:** `DELV-01`
- **Component:** `DocxDeliverableGenerator`
- **Features:**
  - Corporate Visual Styling: Primary Navy (`#1F497D`), Secondary Slate (`#595959`), Body Charcoal (`#262626`).
  - Document Title Block: Title, facility name, equipment tag, classification banner (`[ INTERNAL ]`, `[ RESTRICTED ]`), date, and author.
  - Inspection Findings Table: Header row with `#1F497D` background and white bold typography; alternating zebra striping with `#F2F2F2`; severity status badges (Critical in `#FFD2D2` / `#900000`, Warning in `#FFF3CD` / `#856404`, Satisfactory in `#D1E7DD` / `#0F5132`).
  - Source References Appendix: Tabulates inline citation tags (`[Doc: <id>, p.<num>#<reg>]`), document IDs, SHA-256 digests, page numbers, and region coordinates.
  - Path Fencing & Lineage Integration: Rejects path traversal escaping `allowed_root` with `PathSecurityViolation`; calls `LineageEngine.package_deliverable` to inject custom XML properties into `docProps/custom.xml` and write `<file>.lineage.json`.

### 2. Excel Deliverable Generator (`src/sovereign/deliverables/xlsx.py`)
- **Requirement:** `DELV-02`
- **Component:** `XlsxDeliverableGenerator`, `sanitize_cell_text`
- **Features:**
  - Three-Tier Visual Hierarchy:
    - Tier 1: Input Parameters formatted with Soft Blue fill (`#D9E1F2`).
    - Tier 2: Intermediate Calculations formatted with Soft Amber fill (`#FFF2CC`).
    - Tier 3: Verification & Compliance Status formatted with Soft Green fill (`#E2EFDA`) or Soft Red (`#FCE4D6`).
  - Active Recalculable Formulas: Writes native live formula strings (e.g. `=C7*C8/(2*(C9*C10*C11+C7*C12))` and `=IF(C15>=C20, "PASS - SAFE", "FAIL - UNSAFE")`) represented directly as `<f>` elements in `xl/worksheets/sheet1.xml`.
  - Formula Injection Sanitization: `sanitize_cell_text` inspects literal text cells and prefixes any trigger characters (`=`, `+`, `-`, `@`) with a leading apostrophe (`'`), preventing Dynamic Data Exchange (DDE) and CSV formula injection attacks (Threat T-04-02).
  - Column Auto-Fitting & Lineage Embedding.

### 3. PowerPoint Presentation Generator (`src/sovereign/deliverables/pptx.py`)
- **Requirement:** `DELV-03`
- **Component:** `PptxDeliverableGenerator`
- **Features:**
  - Corporate 16:9 Widescreen Layout: Sets presentation dimensions to 13.333" $\times$ 7.5".
  - Modular Slide Builders:
    - Executive Title Slide: Navy title banner, classification pill, facility, tag, author, and timestamp.
    - Bulleted Summary Slide: Styled bullet points with generous line spacing and corporate typography.
    - Data Table Slide: Navy header row, alternating zebra rows (`#FFFFFF` / `#F2F2F2`), and cell padding.
    - Native OOXML Chart Slide: Instantiates editable OOXML chart parts via `python-pptx.chart.data.CategoryChartData` (Column Clustered, Bar, or Pie) stored in `ppt/charts/chart1.xml`. Data remains fully editable by stakeholders in PowerPoint.
  - Cryptographic Lineage Injection into `docProps/custom.xml` and sidecar manifest.

### 4. Reproducible Code Artifact Exporter (`src/sovereign/deliverables/code_export.py`)
- **Requirement:** `DELV-04`
- **Component:** `CodeArtifactExporter`
- **Features:**
  - Bundles verified runnable Python scripts (`<script_name>.py`) with standardized docstring headers containing session ID, timestamp, and model ID.
  - Captures execution logs (`<script_name>.log`) recording stdout, stderr, and sandbox exit metrics.
  - Copies sample input test fixtures (e.g. `sample_telemetry.csv`).
  - Calls `LineageEngine.package_deliverable` to inject code header provenance and emit `.lineage.json`.
  - Confirmed 100% reproducible execution: Re-running the exported script inside the bundle reproduces identical logged stdout.

### 5. Calculation Trace Exporter (`src/sovereign/deliverables/calc_trace.py`)
- **Requirement:** `DELV-05`
- **Component:** `CalculationTrace`, `CalculationParameter`, `CalculationStep`, `CalculationTraceExporter`
- **Features:**
  - Structured Pydantic schemas capturing engineering standards, input parameters, governing formulas, numerical substitutions, and compliance margins.
  - Multi-Format Derivation Exporter:
    - Markdown: GitHub-flavored tables, LaTeX math blocks, step-by-step expansions, and pass/fail indicators.
    - JSON: RFC 8785 canonical serialization for API integration.
    - Word: Appends styled technical derivation sections directly to existing `.docx` documents.
    - Excel: Generates live recalculable workbooks using `XlsxDeliverableGenerator`.
  - Built-in ASME B31.3 Factory: Implements Clause 304.1.2 pressure design formula:
    $$t = \frac{P \cdot D}{2(S \cdot E \cdot W + P \cdot Y)}$$
    $$t_m = t + c, \quad t_{\text{nom,req}} = \frac{t_m}{1 - MT}$$

### 6. Deliverable Tools & Registry Integration (`src/sovereign/deliverables/tools.py`)
- **Registration:** `register_deliverable_tools(registry, workspace_root)`
- **Tools Registered:**
  - `generate_docx`: Word approval note generation tool with `UserRole.ENGINEER` clearance.
  - `generate_xlsx`: Live formula Excel calculation workbook generator tool with `UserRole.ENGINEER` clearance.
  - `generate_pptx`: Presentation generator tool with native charts and `UserRole.ENGINEER` clearance.
- **Security:** Fenced execution enforcing paths strictly within `workspace_root`. Denies unauthorized roles (`UserRole.AUDITOR`) with `PermissionError`.

---

## Verification & Test Results

All 22 unit and integration tests across `tests/test_deliverables/` pass cleanly:
- `tests/test_docx_generator.py`: 4 passed (Document structure, XML styling & shading, lineage packaging, path fencing).
- `tests/test_xlsx_generator.py`: 6 passed (Workbook structure, raw XML `<f>` tags, sanitizer function, in-cell escaping, lineage packaging, path fencing).
- `tests/test_pptx_generator.py`: 4 passed (Presentation structure, native OOXML chart XML part in archive, lineage packaging, path fencing).
- `tests/test_code_artifact_export.py`: 2 passed (Reproducible bundle creation & execution, path fencing).
- `tests/test_calc_trace_export.py`: 6 passed (ASME B31.3 mathematical expansion, Markdown export, JSON round-trip, live Excel export, Word appendix, ToolRegistry execution & RBAC).

**Full project test suite:**
```
============================ 218 passed in 13.59s =============================
```
Zero regressions across Phase 1, Phase 2, Phase 3, and all Phase 4 modules.

---

## Threat Model & Security Compliance

- **T-04-02 (Formula Injection / DDE):** Mitigated via `sanitize_cell_text`. Any untrusted input text starting with `=`, `+`, `-`, `@` is escaped with a leading `'` when written to spreadsheet cells, preventing command execution when opened in Microsoft Excel.
- **T-04-04 (Path Traversal in File Export):** Mitigated via `validate_output_path` and `_resolve_fenced_path`. Any attempt to export deliverables outside the allowed directory or using null bytes (`\x00`) immediately raises `PathSecurityViolation`.
- **RBAC Enforcement:** Deliverable generation tools registered in `ToolRegistry` require `UserRole.ENGINEER` clearance, preventing unauthorized deliverable generation by read-only Auditor accounts.
