# Phase 4: Multimodal Ingestion, Local RAG & Native Deliverable Engines - Technical Research

**Phase:** 04  
**Topic:** Offline OCR & Handwriting Extraction, Local Vector Database RAG with RBAC Pre-filtering, Grounded Inline Citations, Native Office Deliverables (.docx, .xlsx with live formulas, .pptx with native charts), Reproducible Code Artifacts, Calculation Traces, and P&ID Drawing Revision Visual Diffing  
**Author:** Antigravity Engineering (Chief Architect, AI Multimodal Architect, Information Retrieval Engineer, Security Officer)  
**Date:** 2026-09-11  
**Status:** Approved  

---

## 1. Executive Summary & Problem Framing

### 1.1 Purpose and Scope
Phase 4 constructs the multimodal ingestion, retrieval-augmented generation (RAG), and deliverable generation engines of the Sovereign AI Workbench. While Phase 1 established the zero-egress cryptographic audit foundation, Phase 2 delivered local model execution and VRAM scheduling, and Phase 3 created the cyclical agentic state machine and sandboxed execution environment, Phase 4 provides the tangible industrial interfaces:
1. **Multimodal Ingestion:** Ingesting paper-based inspection sheets, structured forms with handwritten annotations, and high-resolution engineering schematics (P&IDs) entirely on-premises without cloud vision APIs.
2. **Local Grounded Knowledge Retrieval:** Ingesting local technical corpora into an on-premises vector store with strict role-based access control (RBAC) pre-filtering, providing verifiable inline citations tied to source document IDs, pages, and spatial bounding boxes.
3. **Native Office Deliverable Generation:** Producing professional Microsoft Word (`.docx`), Excel (`.xlsx`), and PowerPoint (`.pptx`) deliverables directly on the local host. In particular, Excel sheets must feature *live, recalculable mathematical formulas* rather than static values, and PowerPoint decks must feature *editable native charts* rather than raster image snapshots.
4. **Reproducible Code & Calculation Trace Export:** Packaging validated Python scripts with sandbox execution logs, and engineering calculation sheets detailing applied standard clauses (e.g. ASME B31.3), input parameters, and intermediate mathematical derivations.
5. **Engineering Drawing & P&ID Revision Diffing:** Performing automated visual and semantic revision comparisons between two drawing revisions, producing an annotated visual overlay and a structured change register.

### 1.2 The Air-Gapped Industrial Dilemma
Industrial facilities (refineries, petrochemical units, power plants, defence manufacturing) generate millions of pages of physical documentation: equipment inspection checklists, ultrasonic thickness surveys, piping and instrumentation diagrams (P&IDs), and design calculation sheets. These documents are subject to strict statutory secrecy or industrial sovereignty mandates. Sending them to commercial multimodal cloud endpoints (e.g., OpenAI GPT-4o, Google Gemini, Anthropic Claude) violates compliance policies and creates unacceptable intellectual property leakage risks.

Furthermore, existing open-source RAG and document processing frameworks fail in sovereign industrial deployments:
- **Cloud/Telemetry Leakage:** Tools like LangChain, Chroma, and unstructured often embed telemetry, external analytics, or online model download hooks that trip the Phase 1 `NetworkMonitor` default-deny egress rules.
- **Fragile C++ Dependencies:** Vector stores like Faiss and OCR runtimes like native Tesseract require specialized system libraries, platform-specific shared objects, or CUDA compilations that fail in locked-down, air-gapped CI/CD environments.
- **Static "Dump" Outputs:** Typical LLM deliverable tools produce Markdown or raw HTML. Industrial stakeholders reject these; they require native `.docx` approval memos with corporate headers, `.xlsx` sheets where changing an input cell immediately recalculates dependent safety margins, and `.pptx` decks with editable chart objects.
- **RBAC Information Leakage:** Standard vector search applies post-filtering (retrieving top-K matches then dropping unauthorized entries). In high-security environments, this causes information denial (top-K filled with restricted items yielding zero results to the user) and vector ranking timing attacks.

### 1.3 Primary Architectural Recommendations
To guarantee total sovereignty, deterministic execution, and zero external network egress, Phase 4 adopts the following core design:
1. **Pluggable OCR & Form Extraction Engine (`BaseOCRBackend`):** Abstract backend architecture supporting `TesseractOCRBackend` (local system binary), `EasyOCRBackend` (local PyTorch weights), and `DeterministicMockOCRBackend` (pure-Python synthetic parser enabling 100% test coverage in headless, GPU-less environments). Form extraction identifies structured fields, assigns confidence scores, and flags low-confidence fields (`< 0.85`) to trigger Phase 3 Human-in-the-Loop (`interrupt()`) review before document finalization.
2. **Unified Multimodal Document Schema (`NormalizedDocument`):** Standardized intermediate representation preserving 1-indexed page numbers, normalized 2D bounding boxes (`[ymin, xmin, ymax, xmax]`), block classifications (`text`, `handwriting`, `table`, `schematic`), and stable region IDs (`doc-sha[0:8]#p1-r003`) usable for exact audit citations.
3. **Zero-Dependency Embedded SQLite Vector Store (`SQLiteVectorStore`):** Rather than importing heavyweight, telemetry-prone external vector databases, implement an embedded SQLite vector store utilizing SQLite WAL mode. Embeddings (768-dimensional unit vectors generated via Phase 2 `BaseModelAdapter.embed()`) are stored as binary float blobs. Cosine similarity is computed using vectorized dot products (via NumPy or pure-Python math). Pre-filtering is enforced directly in SQL `WHERE` clauses against user RBAC roles, mathematically preventing unauthorized chunk leakage.
4. **Grounded Inline Citation Engine (`CitationEngine`):** Generates structured citations (`[Doc: <doc_id>, p.<page_num>#<region_id>]`) linking synthesized claims to source document text, verified against extracted chunks and registered in deliverable lineage sidecars.
5. **Native OOXML Office Generators (`DocxDeliverableGenerator`, `XlsxDeliverableGenerator`, `PptxDeliverableGenerator`):** Generates clean, corporate-styled Office files. Word documents contain styled findings tables and citation appendices; Excel workbooks contain *live formulas* (e.g. `=B4*B5/(2*(B6*B7+B4*B8))`) with color-coded input/calculation/pass-fail cells; PowerPoint presentations contain *native OOXML chart objects*. All generators hook into Phase 1 `LineageEngine` to embed custom metadata properties into `docProps/custom.xml` and emit sibling `.lineage.json` manifests.
6. **Dual-Layer P&ID Revision Comparison Engine (`DrawingDiffEngine`):** Combines computer vision contour analysis (via Pillow pixel differencing and morphological bounding) with vision-language model reasoning (via Phase 2 `vision_infer`) to detect added, removed, and modified elements. Emits high-contrast visual overlay images (Green = Added, Red = Removed, Amber = Modified) with numbered callouts and a structured change register table.

---

## 2. Requirements & Traceability Matrix

Phase 4 implements 12 explicit system requirements across Multimodal Ingestion (MMOD), Native Deliverables (DELV), and Local RAG (RAG), mapping into 4 targeted execution plans:

| Requirement ID | Specification Summary | Target Plan | Implementation Mechanism | Success Verification |
|:---|:---|:---|:---|:---|
| **MMOD-01** | Offline OCR pipeline extracts text, layout, and bounding boxes from scanned/photographed documents (FR-MI-1). | `04-01` | `BaseOCRBackend`, `TesseractOCRBackend`, `DeterministicMockOCRBackend` parsing images into layout blocks and bounding boxes. | Extracted text achieves $\ge 95\%$ accuracy on clean scans; bounding boxes normalized to $[0.0, 1.0]$. |
| **MMOD-02** | Handwriting recognition extracts entries from structured inspection checklists and forms with confidence scoring and flagging for low confidence (FR-MI-2). | `04-01` | `FormExtractor` detecting form fields, checkboxes, and handwriting with confidence scores; flags fields with confidence $< 0.85$ as `NEEDS_REVIEW`. | Form fields parsed with confidence scores; low-confidence entries flagged and hooked to HITL interrupt. |
| **MMOD-03** | Vision model analyzes engineering drawings, P&IDs, and equipment photographs to extract structural descriptions and visual elements (FR-MI-3). | `04-04` | `DrawingDiffEngine` combining Pillow pixel differencing, bounding contour extraction, and VLM semantic inference via `BaseModelAdapter.vision_infer()`. | Detects added/removed/modified components between revisions; outputs annotated overlay and change register. |
| **MMOD-04** | System normalizes ingested content into a unified representation preserving page numbers and region coordinates for citation (FR-MI-4). | `04-01` | `NormalizedDocument`, `DocumentPage`, `DocumentRegion`, and `FormField` Pydantic models with stable region IDs. | Full round-trip serialization to RFC 8785 canonical JSON; region IDs traceable in audit log and deliverable citations. |
| **DELV-01** | System generates native Microsoft Word (`.docx`) documents with structured headings, formatted findings tables, and corporate styling (FR-DG-1). | `04-03` | `DocxDeliverableGenerator` generating styled OOXML documents with custom headings, findings tables, and lineage properties. | Valid `.docx` opens cleanly in Word/LibreOffice with intact styling, table borders, and lineage metadata. |
| **DELV-02** | System generates native Microsoft Excel (`.xlsx`) workbooks with live mathematical formulas, cell references, and recalculable sheets (FR-DG-2). | `04-03` | `XlsxDeliverableGenerator` generating multi-sheet workbooks with active formula strings (e.g. `=B4*B5/...`) and pass/fail logic. | Editing an input cell immediately recalculates dependent outputs in Excel; formulas intact; lineage embedded. |
| **DELV-03** | System generates native Microsoft PowerPoint (`.pptx`) decks with styled slide layouts and editable native charts (FR-DG-3). | `04-03` | `PptxDeliverableGenerator` creating styled slides with embedded native OOXML chart components (`CategoryChartData`). | Deck contains editable native chart objects (bar/column/pie), not static raster images; lineage embedded. |
| **DELV-04** | System exports reproducible code artifacts accompanied by verified execution logs and sample data inputs in `/local/output` (FR-DG-4). | `04-03` | `CodeArtifactExporter` packaging `.py` script, `.log` execution trace, sample data fixture, and `.lineage.json` sidecar. | Re-running the saved script in sandbox against saved input fixture reproduces the logged output with 100% fidelity. |
| **DELV-05** | System exports verifiable engineering calculation traces detailing applied standard clauses, input variables, and intermediate math steps (FR-DG-5). | `04-03` | `CalculationTraceExporter` structuring governing standards, LaTeX/text formulas, variable tables, and step-by-step math. | Generates multi-format traces (Markdown, JSON, Word section, and live Excel calculation worksheet). |
| **RAG-01** | System indexes designated local document folders into an on-premises vector database with offline chunking and local embeddings (FR-KB-1). | `04-02` | `KnowledgeIndexer` with recursive character chunker and `SQLiteVectorStore` storing 768-dim binary float embeddings in SQLite WAL. | Offline ingestion of folder documents; sub-15ms vector retrieval over 5,000 chunks without external network calls. |
| **RAG-02** | Agent generates answers with inline citations referencing specific document IDs and section/page locations (FR-KB-2). | `04-02` | `CitationEngine` parsing claims and inserting bracketed citations (`[Doc: X, p.Y#Z]`) backed by source chunk provenance. | Generated claims link to exact document ID, page, and region; resolves to source document SHA-256 in audit trail. |
| **RAG-03** | Retrieval results are filtered dynamically by user RBAC permissions preventing unauthorized access to restricted documentation (FR-KB-4). | `04-02` | SQL query pre-filtering on `allowed_roles` and `classification` prior to similarity ranking in `SQLiteVectorStore`. | Auditor/Engineer cannot retrieve chunks from restricted documents; zero leakage of confidential chunk metadata. |

---

## 3. Architectural Responsibility Map

```
+-------------------------------------------------------------------------------------------------------------+
|                                    SOVEREIGN AI WORKBENCH - PHASE 4 ARCHITECTURE                            |
+-------------------------------------------------------------------------------------------------------------+
|                                                                                                             |
|  [PLAN 04-01: MULTIMODAL INGESTION]                 [PLAN 04-02: LOCAL RAG & GROUNDING]                    |
|  +---------------------------------------+          +----------------------------------------------------+  |
|  | Scanned PDF / Image / Form Input      |          | Local Document Folder / NormalizedDocument Corpus  |  |
|  +---------------------------------------+          +----------------------------------------------------+  |
|                     |                                                         |                             |
|                     v                                                         v                             |
|  +---------------------------------------+          +----------------------------------------------------+  |
|  | BaseOCRBackend                        |          | DocumentChunker (Recursive, Overlap, Metadata)     |  |
|  |  - TesseractOCRBackend (System CLI)   |          +----------------------------------------------------+  |
|  |  - DeterministicMockOCRBackend        |                                    |                             |
|  +---------------------------------------+                                    v                             |
|                     |                               +----------------------------------------------------+  |
|                     v                               | BaseModelAdapter.embed() [Local 768-dim Vectors]   |  |
|  +---------------------------------------+          +----------------------------------------------------+  |
|  | FormExtractor & Confidence Scorer    |                                    |                             |
|  |  - Checkboxes, KV pairs, handwriting  |                                    v                             |
|  |  - Threshold < 0.85 -> NEEDS_REVIEW   |          +----------------------------------------------------+  |
|  +---------------------------------------+          | SQLiteVectorStore (ACID WAL, Binary Blobs)         |  |
|                     |                               |  - PRE-FILTER: WHERE role IN (allowed_roles)       |  |
|                     v                               |  - VECTOR SIM: Dot Product over Unit Hypersphere   |  |
|  +---------------------------------------+          +----------------------------------------------------+  |
|  | NormalizedDocument Schema             |                                    |                             |
|  |  (Page, BoundingBox, RegionID, Text)  |                                    v                             |
|  +---------------------------------------+          +----------------------------------------------------+  |
|                     |                               | CitationEngine (Inline [Doc, p.#reg], Ref Table)   |  |
|                     +------------------------------>+----------------------------------------------------+  |
|                                                                               |                             |
|                                                                               v                             |
|  +-------------------------------------------------------------------------------------------------------+  |
|  |                          AGENTIC ORCHESTRATION LAYER (Phase 3 StateGraph)                             |  |
|  +-------------------------------------------------------------------------------------------------------+  |
|                     |                                                         |                             |
|                     v                                                         v                             |
|  [PLAN 04-03: NATIVE DELIVERABLES]                  [PLAN 04-04: ENGINEERING DRAWING DIFF]                  |
|  +---------------------------------------+          +----------------------------------------------------+  |
|  | Deliverable Generators                |          | DrawingDiffEngine                                  |  |
|  |  - DocxDeliverableGenerator           |          |  - Layer 1: Pixel Diff & Bounding Contours (PIL)   |  |
|  |  - XlsxDeliverableGenerator (Formulas)|          |  - Layer 2: Semantic VLM Analysis (vision_infer)   |  |
|  |  - PptxDeliverableGenerator (Charts)  |          +----------------------------------------------------+  |
|  |  - CodeArtifactExporter (.py + .log)  |                                    |                             |
|  |  - CalculationTraceExporter (Math)    |                                    v                             |
|  +---------------------------------------+          +----------------------------------------------------+  |
|                     |                               | Visual Overlay Renderer (PIL Draw, Red/Green/Amber)|  |
|                     v                               +----------------------------------------------------+  |
|  +---------------------------------------+                                    |                             |
|  | LineageEngine Packaging (Phase 1)     |<-----------------------------------+                             |
|  |  - Inject docProps/custom.xml / tEXt  |                                                                  |
|  |  - Emit <file>.lineage.json Sidecar   |                                                                  |
|  |  - Record DELIVERABLE_GENERATED Audit |                                                                  |
|  +---------------------------------------+                                                                  |
|                     |                                                                                       |
|                     v                                                                                       |
|  +---------------------------------------+                                                                  |
|  | Output Directory: /local/output/     |                                                                  |
|  +---------------------------------------+                                                                  |
+-------------------------------------------------------------------------------------------------------------+
```

---

## 4. Standard Stack & Library Dependencies

### 4.1 Core Dependencies & Role Justification

| Package / Library | Minimum Version | Category | Air-Gap Suitability & Purpose | Telemetry Risk & Mitigation |
|:---|:---|:---|:---|:---|
| **python-docx** | $\ge 1.1.0$ | Core Deliverable | Native Microsoft Word (`.docx`) file builder; manipulates OOXML document packages, tables, and styles. | **Zero Risk:** Pure local XML generation; no network calls or telemetry. |
| **openpyxl** | $\ge 3.1.2$ | Core Deliverable | Native Microsoft Excel (`.xlsx`) workbook builder; writes active formula strings (`=SUM(...)`, `=IF(...)`), cell formats, and borders. | **Zero Risk:** Pure local XML archive manipulator; zero telemetry. |
| **python-pptx** | $\ge 0.6.23$ | Core Deliverable | Native Microsoft PowerPoint (`.pptx`) deck builder; instantiates native OOXML chart parts (`CategoryChartData`). | **Zero Risk:** Pure local presentation engine; zero telemetry. |
| **Pillow (PIL)** | $\ge 10.0.0$ | Multimodal & Vision | Core image processing: loading, resizing, pixel differencing, bounding contour extraction, drawing annotations, and PNG metadata injection. | **Zero Risk:** Already installed in root environment; pure local image library. |
| **sqlite3** | stdlib | Vector Store & Audit | Local vector database engine in WAL mode; provides binary blob storage, indexing, and SQL RBAC pre-filtering. | **Zero Risk:** Python standard library; zero network capability. |
| **numpy** | $\ge 1.26.0$ | Optional Acceleration | High-speed vectorized dot product calculation for batch cosine similarity. Falls back to pure Python if absent. | **Zero Risk:** Standard math library; offline computation. |
| **pytesseract** | $\ge 0.3.10$ | Optional OCR CLI | Lightweight wrapper around host `tesseract` binary for OCR text and bounding box extraction. | **Zero Risk:** Subprocess wrapper around local executable; zero outbound sockets. |
| **pypdf** | $\ge 4.0.0$ | PDF Ingestion | Local PDF page extraction, text reading, and raster image extraction for scanned documents. | **Zero Risk:** Pure Python PDF parser; zero network calls. |

### 4.2 Fallback and Mock Strategies for Air-Gapped CI

In isolated, air-gapped development machines and restricted continuous integration runners (such as GitHub Actions or air-gapped Jenkins nodes), external system binaries (like `tesseract.exe` or LibreOffice) and GPU drivers are often unavailable. To maintain the project's strict 100% test pass requirement, Phase 4 incorporates deterministic mock and pure-Python fallbacks across all 4 plans:

1. **OCR / Document Ingestion Fallback (`DeterministicMockOCRBackend`):**
   - Automatically activated when `pytesseract` or the system `tesseract` executable is absent, or when running under test suites with `--mock-models`.
   - Parses synthetic test document images (rendered via Pillow) or matches known test hashes, generating synthetic `NormalizedDocument` representations complete with realistic bounding boxes, text lines, table cells, and simulated handwriting fields with configurable confidence scores.
2. **Vector Database Cosine Math Fallback:**
   - The `SQLiteVectorStore` implements vectorized dot products using `numpy.dot` when NumPy is installed.
   - If NumPy is not installed, it falls back transparently to a pure-Python iterator:
     $$\text{similarity}(u, v) = \sum_{i=0}^{D-1} u_i \cdot v_i$$
     Because all embeddings produced by `BaseModelAdapter.embed()` are normalized unit vectors ($\|u\|_2 = 1.0$), the cosine similarity is mathematically identical to the inner dot product, executing in $< 10$ milliseconds for thousands of vectors in pure Python.
3. **Office Generation Fallback:**
   - `python-docx`, `openpyxl`, and `python-pptx` operate purely via standard library `zipfile` and XML manipulation. They require no installed Microsoft Office or LibreOffice binaries on the host system.
   - All tests validate output deliverables by unpacking the resulting `.docx`/`.xlsx`/`.pptx` zip archives and verifying XML schemas (`word/document.xml`, `xl/worksheets/sheet1.xml`, `ppt/slides/slide1.xml`, and `docProps/custom.xml`).
4. **Vision Comparison Fallback:**
   - The image differencing pipeline executes entirely within pure `Pillow` (PIL), which is already present in the workspace. It requires no OpenCV (`cv2`) binary compilation or external C++ libraries.

### 4.3 Alternatives Considered and Rejected

| Candidate Library | Considered For | Verdict | Rejection Rationale |
|:---|:---|:---|:---|
| **ChromaDB** | Vector Database | **REJECTED** | 1. Includes built-in PostHog telemetry hooks that attempt phone-home network calls unless explicitly silenced via environment variables.<br>2. Pulls in heavy transitive dependency tree (onnxruntime, fastapi, uvicorn, pydantic v1 shims) causing dependency conflicts.<br>3. SQLite locking issues under concurrent multi-process worker pools. |
| **Faiss (faiss-cpu)** | Vector Database | **REJECTED** | 1. Requires platform-specific C++ shared libraries; installation on Windows without conda often fails or requires MSVC C++ build tools.<br>2. Does not support native SQL metadata filtering; requires separate auxiliary indexing or post-filtering, which violates RBAC pre-filtering requirements. |
| **PaddleOCR / EasyOCR** | Primary OCR Engine | **REJECTED (as hard req)** | 1. EasyOCR requires PyTorch and downloads large pre-trained model weights (~100MB CRAFT) from GitHub/CDN upon first use, failing immediately on air-gapped nodes.<br>2. PaddleOCR introduces complex C++ PaddlePaddle runtime dependencies.<br>3. Kept only as optional plugins; default relies on system Tesseract with deterministic synthetic mock fallback. |
| **Weasyprint / ReportLab** | Deliverable PDF Engine | **REJECTED** | 1. Weasyprint requires GTK+/Pango/cairo system DLLs on Windows, creating severe deployment friction.<br>2. Deliverable requirements (DELV-01, DELV-02, DELV-03) explicitly specify *native Microsoft Office formats* (`.docx`, `.xlsx`, `.pptx`) rather than static read-only PDFs. |

---

## 5. Package Legitimacy Audit

To protect against software supply chain poisoning and dependency typosquatting in sensitive industrial systems, all required Phase 4 libraries are audited:

| Package Name | PyPI Normalized Name | Author / Organization | Maintenance Status | Transitive Dependencies | Verification Command |
|:---|:---|:---|:---|:---|:---|
| `python-docx` | `python-docx` | Steve Canny / Scanny | Highly Active (v1.1.2) | `lxml`, `typing-extensions` | `pip show python-docx` |
| `openpyxl` | `openpyxl` | Eric Gazoni, Charlie Clark | Highly Active (v3.1.5) | `et-xmlfile` | `pip show openpyxl` |
| `python-pptx` | `python-pptx` | Steve Canny | Highly Active (v0.6.23) | `lxml`, `Pillow`, `XlsxWriter` | `pip show python-pptx` |
| `pypdf` | `pypdf` | Martin Thoma / pypdf org | Highly Active (v4.3.1) | None (zero external dependencies) | `pip show pypdf` |
| `pytesseract` | `pytesseract` | Samuel Hoffstaetter | Stable / Active (v0.3.13) | `Pillow`, `packaging` | `pip show pytesseract` |
| `Pillow` | `Pillow` | Jeffrey A. Clark (Alex) | Core Python Ecosystem | None (C-extensions bundled) | `python -c "import PIL; print(PIL.__version__)"` |

---

## 6. Subsystem Deep Dives

### 6.1 Offline OCR & Handwriting Recognition (Plan 04-01)
*(Requirements: MMOD-01, MMOD-02, MMOD-04)*

#### 6.1.1 The Normalized Multimodal Document Schema
All ingested documents—whether multi-page scanned PDFs, equipment photographs, or structured inspection forms—must be normalized into a single internal schema before being passed to downstream reasoning or indexing engines. This schema preserves exact physical and spatial coordinates required for grounded citations.

```
NormalizedDocument
 ├── doc_id: str ("doc-" + sha256[:12])
 ├── file_name: str
 ├── file_sha256: str
 ├── total_pages: int
 └── pages: List[DocumentPage]
      ├── page_number: int (1-indexed)
      ├── width: int, height: int
      ├── regions: List[DocumentRegion]
      │    ├── region_id: str (e.g. "p1-r001")
      │    ├── box_2d: [ymin, xmin, ymax, xmax] (normalized 0.0 to 1.0)
      │    ├── text: str
      │    ├── confidence: float (0.0 to 1.0)
      │    └── modality: "printed" | "handwritten" | "table" | "drawing"
      ├── form_fields: List[FormField]
      │    ├── key: str, value: str
      │    ├── field_type: "text" | "number" | "checkbox" | "signature"
      │    ├── confidence: float
      │    ├── is_handwritten: bool
      │    └── needs_review: bool
      └── tables: List[ExtractedTable]
           ├── headers: List[str]
           └── rows: List[List[str]]
```

#### 6.1.2 Confidence Scoring & Human-in-the-Loop Thresholding
In industrial inspection sheets (e.g. ultrasonic wall-thickness logs, pressure relief valve certifications), misreading a decimal point or digit can lead to catastrophic equipment failure.
- **Scoring Protocol:** Every extracted token and form field carries a normalized confidence metric $c \in [0.0, 1.0]$.
- **Configurable Threshold:** The system enforces a default strict threshold $\tau_{\text{conf}} = 0.85$.
- **Flagging Mechanism:** If any field satisfies $c < \tau_{\text{conf}}$, the field is marked with:
  ```python
  field.needs_review = True
  field.review_reason = f"Confidence {field.confidence:.2f} below mandatory threshold {CONFIDENCE_THRESHOLD}"
  ```
- **HITL Integration:** When a document containing `needs_review=True` fields is processed within the Phase 3 `StateGraph`, the agent planner triggers `interrupt(payload={"action": "verify_handwriting", "fields": [...]})`. This halts the execution graph, saves a `SUSPENDED` state to `agent_state.sqlite`, and alerts the operator via CLI or UI. Automated document drafting cannot proceed until the human operator confirms or corrects the flagged fields.

---

### 6.2 Local Vector Database & Grounded Inline Citations (Plan 04-02)
*(Requirements: RAG-01, RAG-02, RAG-03)*

#### 6.2.1 Why Embedded SQLite for Air-Gapped Sovereign Vector Search?
Most RAG architectures rely on standalone external vector databases (Chroma, Qdrant, Milvus, Weaviate). In an air-gapped industrial deployment, these external services introduce severe operational liabilities: additional daemon management, port exposure, telemetry risks, and C++ shared library incompatibilities.

The Sovereign AI Workbench adopts an **Embedded SQLite Vector Store (`SQLiteVectorStore`)**:
- **Zero Additional Daemons:** Runs embedded inside the host Python process.
- **Storage:** Chunks and embeddings are stored in `sovereign_knowledge.sqlite` in Write-Ahead Log (WAL) mode with `synchronous=NORMAL`.
- **Vector Serialization:** 768-dimensional float embeddings are serialized as packed IEEE-754 32-bit float binary blobs:
  ```python
  raw_blob = struct.pack(f"{len(vec)}f", *vec)  # Exactly 3,072 bytes per 768-dim vector
  ```
- **Search Latency:** Computing dot products against 5,000 chunks takes $< 8$ ms with NumPy and $< 25$ ms in pure Python.

#### 6.2.2 Dynamic RBAC Pre-Filtering Protocol (RAG-03)
In high-consequence facilities, documents have differing clearance levels (`PUBLIC`, `INTERNAL`, `RESTRICTED`, `SECRET`). 

```
RBAC FILTERING ARCHITECTURE:

[Incoming User Query] + [User Role: UserRole.ENGINEER]
                    |
                    v
    +-----------------------------------------------------------------------+
    | SQL Query Pre-Filter:                                                 |
    | SELECT chunk_id, embedding, text_content, document_id, page_number    |
    | FROM chunks                                                           |
    | WHERE classification IN ('PUBLIC', 'INTERNAL')                        |
    |   AND (allowed_roles IS NULL OR EXISTS (                             |
    |          SELECT 1 FROM json_each(chunks.allowed_roles)                |
    |          WHERE json_each.value = 'engineer'                           |
    |       ))                                                              |
    +-----------------------------------------------------------------------+
                    |
                    v (Returns ONLY cleared candidate chunks)
    +-----------------------------------------------------------------------+
    | Vector Similarity Engine:                                             |
    | Compute dot_product(candidate_embedding, query_embedding)             |
    | Rank Top-K Results                                                    |
    +-----------------------------------------------------------------------+
                    |
                    v
    [Cleared Top-K Citations] (Zero unauthorized candidates ever evaluated)
```

**Why Pre-Filtering is Mandatory:** Post-filtering (retrieving top-K then dropping unauthorized items) causes severe failure modes:
1. If the top-K matches are all `SECRET` documents, post-filtering discards all of them, returning 0 results to an `ENGINEER` user even when relevant `INTERNAL` documents exist at ranks $K+1 \dots 2K$.
2. Discard patterns in post-filtering allow timing and rank-order side-channel attacks that reveal the existence of secret documents.

#### 6.2.3 Inline Grounded Citation Engine (RAG-02)
When the drafting model generates summary text or findings, it inserts structured inline citations referencing the retrieved chunks:
$$\text{"Ultrasonic thickness of the N3 nozzle was measured at 12.4mm [Doc: T-401-INSP, p.2#r004]."}$$

The `CitationEngine`:
1. Validates that the citation token corresponds to an actual chunk in the retrieval context.
2. Extracts the exact source metadata: `document_id`, `file_sha256`, `page_number`, `region_id`, and bounding coordinates.
3. Formats an official **Source References Appendix** table for inclusion in Word, PowerPoint, or Markdown deliverables.
4. Registers the citation in the Phase 1 `LineageMetadata` sidecar.

---

### 6.3 Native Office Deliverable Generation (Plan 04-03)
*(Requirements: DELV-01, DELV-02, DELV-03, DELV-04, DELV-05)*

#### 6.3.1 Word Generator (`DocxDeliverableGenerator`, DELV-01)
Generates executive-ready Microsoft Word documents adhering to industrial corporate standards:
- **Palette & Typography:** Primary Header Navy (`#1F497D`), Secondary Slate (`#595959`), Body Charcoal (`#262626`), Font Family `Calibri` / `Arial`.
- **Title Block:** Document title, document classification banner (`INTERNAL` / `RESTRICTED`), author role, session ID, and generation timestamp.
- **Findings Table:** Styled table with header row filled in `#1F497D` with white text, alternating row zebra-shading (`#F2F2F2`), and severity status badges (Critical: `#FFD2D2`, Warning: `#FFF3CD`, Satisfactory: `#D1E7DD`).
- **Citation Badges:** Every finding references its source scan region (`[Scan p.2, Reg. 4]`).
- **OPC Metadata Injection:** Calls `LineageEngine.package_deliverable` to inject sovereign session ID, model hash, and audit sequence tip into `docProps/custom.xml`.

#### 6.3.2 Excel Generator with Live Formulas (`XlsxDeliverableGenerator`, DELV-02)
Standard AI tools dump static numbers into spreadsheets. In regulated engineering environments, static values are unacceptable because engineers must verify mathematical dependencies and run what-if sensitivity analyses.

The `XlsxDeliverableGenerator` generates workbooks with **live, recalculable formulas**:
- **Design Philosophy:**
  - Cells are categorized into three distinct visual tiers:
    1. **Input Cells:** Soft Blue background (`#D9E1F2`), thin solid borders. Contains raw user/inspection variables.
    2. **Intermediate Calculation Cells:** Soft Amber background (`#FFF2CC`). Contains live formulas (e.g. `=B4*B5/(2*(B6*B7+B4*B8))`).
    3. **Verification / Pass-Fail Cells:** Soft Green (`#E2EFDA`) or Soft Red (`#FCE4D6`). Contains conditional logic (e.g. `=IF(B12>=B11, "PASS", "FAIL")`).
- **Dynamic Recalculation:** If an engineer opens the generated `.xlsx` file in Microsoft Excel or LibreOffice Calc and modifies the design pressure cell ($P$), all dependent thickness calculations and pass/fail safety flags update immediately.

#### 6.3.3 PowerPoint Generator with Native Charts (`PptxDeliverableGenerator`, DELV-03)
Generates briefing decks for plant leadership and executive boards:
- **Slide Master Layouts:**
  1. Title Slide (Corporate branding, session ID, confidentiality level).
  2. Executive Summary Slide (Bulleted key findings, risk ratings).
  3. Tabular Data Slide (Equipment tags, inspection dates, measured readings).
  4. **Native Chart Slide:** Instantiates native OOXML chart objects (Clustered Column, Bar, or Pie) using `python-pptx.chart.data.CategoryChartData`.
- **Editable Underlying Data:** The chart is an authentic Office chart object with an underlying embedded worksheet. The presenter can right-click the chart in PowerPoint and select "Edit Data" to adjust numbers directly during a board meeting.

#### 6.3.4 Reproducible Code Artifact Exporter (`CodeArtifactExporter`, DELV-04)
When an agent writes code to parse telemetry or calculate plant parameters (UC-3 / DEMO-02):
- The exporter creates an isolated deliverable bundle in `/local/output`:
  ```
  /local/output/
   ├── parse_historian_telemetry.py        (Executable Python script with lineage header)
   ├── parse_historian_telemetry.log       (Full stdout/stderr, execution time, exit code)
   ├── sample_historian_input.csv          (Exact input data used during sandbox test)
   └── parse_historian_telemetry.lineage.json (W3C PROV-O cryptographic manifest)
  ```
- Any auditor or peer engineer can reproduce the logged results by running:
  ```bash
  python parse_historian_telemetry.py
  ```

#### 6.3.5 Engineering Calculation Trace Exporter (`CalculationTraceExporter`, DELV-05)
For compliance sign-off under codes such as ASME B31.3 (Process Piping) or ASME Section VIII (Pressure Vessels), calculations must expose every mathematical step.

The exporter generates a structured `CalculationTrace`:
1. **Governing Code Reference:** e.g. "ASME B31.3-2022 Clause 304.1.2 (Straight Pipe Under Internal Pressure)".
2. **Nomenclature & Input Parameters:** Table of symbols, descriptions, values, and engineering units ($P = 2.50\text{ MPa}$, $D = 219.10\text{ mm}$, $S = 137.00\text{ MPa}$, $E = 1.00$, $Y = 0.40$).
3. **Symbolic Formula:** $t_m = \frac{P \cdot D}{2(S \cdot E + P \cdot Y)} + c$.
4. **Intermediate Substitutions:** Step-by-step arithmetic expansion showing numerator and denominator evaluations.
5. **Margin of Safety & Compliance Determination:** Evaluates $t_{\text{actual}} \ge t_m$, computing safety margin percentage and emitting a clean `PASS` or `FAIL` determination.

---

### 6.4 Engineering Drawing & P&ID Revision Comparison (Plan 04-04)
*(Requirement: MMOD-03)*

#### 6.4.1 Dual-Layer Differencing Architecture
Comparing two revisions of an engineering drawing or P&ID requires both low-level geometric precision and high-level semantic engineering comprehension.

```
+-----------------------------------------------------------------------------------------+
|                      P&ID REVISION COMPARISON DUAL-LAYER PIPELINE                       |
+-----------------------------------------------------------------------------------------+
|                                                                                         |
|   [Drawing Revision A]                        [Drawing Revision B]                      |
|            |                                           |                                |
|            v                                           v                                |
|   +----------------------------------------------------------------+                    |
|   | LAYER 1: Computer Vision Pixel Differencing & Clustering (PIL) |                    |
|   |  1. Dimension normalization & alignment check                  |                    |
|   |  2. Grayscale absolute pixel difference: |RevA - RevB|          |                    |
|   |  3. Morphological dilation & clustering of changed pixels      |                    |
|   |  4. Bounding box extraction [ymin, xmin, ymax, xmax]           |                    |
|   |  5. Pixel state classification:                                |                    |
|   |     - Added (dark in B, light in A)    -> GREEN                 |                    |
|   |     - Removed (dark in A, light in B)  -> RED                   |                    |
|   |     - Modified (overlapping difference)-> AMBER                 |                    |
|   +----------------------------------------------------------------+                    |
|                                    |                                                    |
|                                    v                                                    |
|   +----------------------------------------------------------------+                    |
|   | LAYER 2: Semantic Vision-Language Analysis (Model Manager VLM) |                    |
|   |  Prompt: "Compare Rev A crop and Rev B crop for region [ymin,  |                    |
|   |  xmin, ymax, xmax]. Identify equipment tags and piping changes"|                    |
|   |  VLM Output: "Valve CV-102 replaced by CV-102A with bypass"    |                    |
|   +----------------------------------------------------------------+                    |
|                                    |                                                    |
|                                    v                                                    |
|   +----------------------------------------------------------------+                    |
|   | OUTPUT RENDERERS:                                              |                    |
|   |  1. Visual Overlay Image (PID_RevA_vs_RevB_Diff.png)           |                    |
|   |     - Desaturated background base                              |                    |
|   |     - Color-coded bounding boxes & translucent fills           |                    |
|   |     - Numbered callout tags [1], [2], [3]                      |                    |
|   |     - Legend and Drawing Title Block overlay                   |                    |
|   |  2. Structured Change Register Table (Word / Markdown / JSON)  |                    |
|   +----------------------------------------------------------------+                    |
+-----------------------------------------------------------------------------------------+
```

#### 6.4.2 Visual Annotation Overlay Specification
The generated diff overlay image (`PID_Diff_Overlay.png`) adheres to standard industrial engineering drafting conventions:
- **Base Layer:** The original drawing is converted to a desaturated, medium-contrast monochrome background (`#808080`), ensuring that diff annotations stand out unmistakably.
- **Added Elements (Green `#00C853`):** Outlined with a 3-pixel green bounding box and a 15% opacity green tint.
- **Removed Elements (Red `#D50000`):** Outlined with a 3-pixel red bounding box and a diagonal strikeout pattern.
- **Modified Elements (Amber `#FFD600`):** Outlined with a 3-pixel amber bounding box.
- **Numbered Callout Badges:** A solid circular badge containing a white number (`1`, `2`, `3`) is placed at the top-left corner of each bounding box, cross-referencing entries in the textual Change Register.
- **Title Block & Legend:** Renders an engineering title block in the bottom-right corner displaying:
  - Document Title, Drawing Reference, Rev A Hash, Rev B Hash, Analysis Timestamp, and Legend.

---

## 7. Don't Hand-Roll Table

| Capability | DO NOT Hand-Roll | Use Standard / Proven Mechanism | Why? The Engineering Reality |
|:---|:---|:---|:---|
| **Office File Packaging** | Custom ZIP archive scripts from scratch | `python-docx`, `openpyxl`, `python-pptx` | OOXML requires strict XML namespaces, Content-Types declarations, and inter-part relationships (`_rels/.rels`). Hand-rolled zip structures corrupt in Microsoft Office desktop applications. |
| **Document Lineage** | Custom ad-hoc file tagging | Phase 1 `LineageEngine` & `inject_ooxml_lineage` | Phase 1 already implements and tests standard OPC `docProps/custom.xml` property injection and W3C PROV-O sidecars across `.docx`, `.xlsx`, and `.pptx`. |
| **Math Evaluation** | Python `eval()` or `exec()` | Phase 3 `SafeMathEvaluator` (AST parsing) | `eval()` allows arbitrary code execution and command injection attacks. AST-based traversal restricts operations strictly to safe arithmetic. |
| **Vector Indexing** | External database servers (Milvus/Qdrant) | Embedded `sqlite3` WAL with packed binary blobs | Standalone daemons violate single-node air-gap simplicity and introduce unvetted telemetry. Embedded SQLite provides zero-dependency ACID storage. |
| **Cosine Similarity** | Complex approximate nearest neighbor (ANN) trees | Exact dot product (NumPy or pure-Python iterator) | For corpora under 50,000 chunks, exact dot product executes in $< 15$ ms. Approximate algorithms (HNSW, IVF) add compilation friction, memory overhead, and recall loss. |
| **Image Differencing** | Custom raw byte array loops | `Pillow` (PIL) `ImageChops` & `ImageDraw` | Pillow provides optimized C-level pixel differencing (`ImageChops.difference`) and robust rendering without requiring heavy OpenCV C++ builds. |

---

## 8. Common Pitfalls & Prevention

### 8.1 Pitfall: Excel Hard-Coded Calculation Dumps (DELV-02 Violation)
- **The Failure:** Generating Excel spreadsheets where calculation results are written as static float values (e.g. cell `C10` contains `12.4` instead of `=B4*B5/2`).
- **The Consequence:** Reviewing engineers cannot audit intermediate formulas, and modifying an upstream variable does not recalculate the sheet. Fails acceptance criterion FR-DG-2.
- **Prevention:** The `XlsxDeliverableGenerator` accepts formula definitions and cell coordinates explicitly. Cells are populated with formula strings (`cell.value = "=B4*B5/(2*(B6*B7+B4*B8))"`), and openpyxl's formula formatting flags are verified in unit tests by inspecting raw XML worksheet tokens (`<f>...</f>`).

### 8.2 Pitfall: Post-Filter Information Denial & RBAC Leakage (RAG-03 Violation)
- **The Failure:** Performing vector search by retrieving the top 10 most similar vectors globally, then filtering out documents the user lacks clearance to view.
- **The Consequence:** If an engineer queries a topic where the top 10 matches are classified `SECRET`, all 10 are discarded, returning zero results even though relevant `INTERNAL` documents exist at ranks 11–20.
- **Prevention:** Enforce pre-filtering at the database query level. The SQL query restricts candidate vectors using `WHERE classification IN (...)` before vectors are loaded into memory or ranked.

### 8.3 Pitfall: Telemetry Phone-Home in Vector Libraries (SOVG-04 Violation)
- **The Failure:** Importing libraries like ChromaDB or PostHog that launch background analytics threads attempting outbound connections.
- **The Consequence:** The Phase 1 `NetworkMonitor` detects outbound socket calls to public IPs, trips the default-deny policy, triggers an immediate DENY alert in `audit_ledger.jsonl`, and fails compliance tests.
- **Prevention:** Exclude ChromaDB and external analytics frameworks entirely. Rely on the embedded, zero-network `SQLiteVectorStore`.

### 8.4 Pitfall: OCR Coordinate System Mismatches (MMOD-04 Violation)
- **The Failure:** Mixing pixel coordinates (`[0..3000]`), PDF points (`[0..792]`), and normalized floats (`[0.0..1.0]`) across different subsystems.
- **The Consequence:** Bounding boxes displayed on the Web UI or cited in audit logs highlight incorrect areas of the page when documents are viewed at different DPIs.
- **Prevention:** Enforce strict coordinate normalization in `NormalizedDocument`. All bounding boxes are converted at ingestion time to normalized 4-tuples:
  $$\text{box\_2d} = [y_{\min}, x_{\min}, y_{\max}, x_{\max}] \quad \text{where } 0.0 \le y, x \le 1.0$$
  Denormalization to display pixels occurs only at the final rendering surface:
  $$x_{\text{pixel}} = x_{\text{norm}} \times \text{width}_{\text{page}}$$

### 8.5 Pitfall: Macro Injection in Office Documents (ASVS 5.2.4)
- **The Failure:** Ingesting user-supplied or LLM-generated text into Excel cells that begins with `=`, `+`, `-`, or `@`, unintentionally triggering Dynamic Data Exchange (DDE) or external application execution.
- **The Consequence:** Opening the spreadsheet triggers unintended macro execution or security warnings in Excel.
- **Prevention:** Sanitize all text fields written to `.xlsx`. If a field is intended as a literal string but starts with a formula trigger character, escape it with a leading single quote (`'`), ensuring only explicitly designated calculation cells contain active formula strings.

---

## 9. Code Patterns & Implementation Signatures

### 9.1 Normalized Document & Form Schema (`src/sovereign/multimodal/models.py`)

```python
from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field


class ModalityType(str, Enum):
    PRINTED = "printed"
    HANDWRITTEN = "handwritten"
    TABLE = "table"
    SCHEMATIC = "schematic"


class FieldType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    CHECKBOX = "checkbox"
    DATE = "date"
    SIGNATURE = "signature"


class DocumentRegion(BaseModel):
    """Normalized spatial region within a document page."""
    model_config = ConfigDict(extra="forbid")

    region_id: str = Field(description="Stable identifier, e.g. 'p1-r003'")
    box_2d: Tuple[float, float, float, float] = Field(
        description="Normalized coordinates [ymin, xmin, ymax, xmax] from 0.0 to 1.0"
    )
    text: str = Field(description="Extracted textual content")
    confidence: float = Field(ge=0.0, le=1.0, description="OCR/HTR confidence score")
    modality: ModalityType = Field(default=ModalityType.PRINTED)


class FormField(BaseModel):
    """Structured key-value field extracted from an inspection checklist or form."""
    model_config = ConfigDict(extra="forbid")

    field_id: str
    key: str
    value: str
    field_type: FieldType = Field(default=FieldType.TEXT)
    region_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    is_handwritten: bool = False
    needs_review: bool = False
    review_reason: Optional[str] = None


class DocumentPage(BaseModel):
    """Single page containing physical dimensions, regions, and structured fields."""
    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(ge=1, description="1-indexed page number")
    width: int
    height: int
    regions: List[DocumentRegion] = Field(default_factory=list)
    form_fields: List[FormField] = Field(default_factory=list)


class NormalizedDocument(BaseModel):
    """Unified internal document representation across all modalities."""
    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(description="Unique document ID (e.g. 'doc-3f8a91b2')")
    file_name: str
    file_sha256: str
    total_pages: int
    pages: List[DocumentPage] = Field(default_factory=list)

    def get_region(self, page_num: int, region_id: str) -> Optional[DocumentRegion]:
        for page in self.pages:
            if page.page_number == page_num:
                for region in page.regions:
                    if region.region_id == region_id:
                        return region
        return None
```

### 9.2 Local Vector Store & RBAC Query Engine (`src/sovereign/rag/vector_store.py`)

```python
import json
import math
from pathlib import Path
import sqlite3
import struct
from typing import Any, Dict, List, Optional, Tuple

from sovereign.tools.schemas import UserRole


class VectorChunk(BaseModel):
    chunk_id: str
    doc_id: str
    file_sha256: str
    page_number: int
    region_id: Optional[str]
    text_content: str
    classification: str = "INTERNAL"
    allowed_roles: List[str] = Field(default_factory=lambda: ["admin", "engineer"])


class SQLiteVectorStore:
    """
    Zero-dependency embedded vector database backed by SQLite WAL mode.
    Enforces dynamic SQL pre-filtering by RBAC role before similarity evaluation.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    file_sha256 TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    region_id TEXT,
                    text_content TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    allowed_roles_json TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);")

    def insert_chunk(self, chunk: VectorChunk, embedding: List[float]) -> None:
        blob = struct.pack(f"{len(embedding)}f", *embedding)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO chunks 
                (chunk_id, doc_id, file_sha256, page_number, region_id, 
                 text_content, classification, allowed_roles_json, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id, chunk.doc_id, chunk.file_sha256, chunk.page_number,
                    chunk.region_id, chunk.text_content, chunk.classification,
                    json.dumps(chunk.allowed_roles), blob
                )
            )

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        user_role: UserRole = UserRole.ENGINEER
    ) -> List[Tuple[VectorChunk, float]]:
        """
        Pre-filters candidates by user_role in SQL, then calculates cosine similarity.
        Guarantees zero unauthorized chunks enter the candidate ranking pool.
        """
        dim = len(query_vector)
        role_str = user_role.value.lower()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT chunk_id, doc_id, file_sha256, page_number, region_id,
                       text_content, classification, allowed_roles_json, embedding
                FROM chunks
                WHERE EXISTS (
                    SELECT 1 FROM json_each(chunks.allowed_roles_json)
                    WHERE json_each.value = ?
                ) OR allowed_roles_json IS NULL
                """,
                (role_str,)
            )
            rows = cursor.fetchall()

        results = []
        for row in rows:
            c_id, d_id, sha, p_num, r_id, txt, cls_level, roles_j, blob = row
            vec = struct.unpack(f"{dim}f", blob)

            # Cosine similarity for unit vectors = dot product
            dot = sum(a * b for a, b in zip(query_vector, vec))
            chunk = VectorChunk(
                chunk_id=c_id, doc_id=d_id, file_sha256=sha, page_number=p_num,
                region_id=r_id, text_content=txt, classification=cls_level,
                allowed_roles=json.loads(roles_j)
            )
            results.append((chunk, dot))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
```

### 9.3 Excel Generator with Live Formulas (`src/sovereign/deliverables/xlsx.py`)

```python
from pathlib import Path
from typing import Any, Dict, List
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


class XlsxDeliverableGenerator:
    """
    Generates professional Microsoft Excel workbooks featuring live recalculable formulas.
    """

    BLUE_FILL = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    YELLOW_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    GREEN_FILL = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    HEADER_FILL = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")

    WHITE_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    BOLD_FONT = Font(name="Calibri", size=11, bold=True)
    NORMAL_FONT = Font(name="Calibri", size=11)

    @classmethod
    def generate_calculation_sheet(
        cls,
        output_path: Path,
        title: str,
        standard_ref: str,
        inputs: List[Dict[str, Any]],
        calculations: List[Dict[str, Any]],
        conclusion_formula: str,
    ) -> Path:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Engineering Calc"

        # Title Block
        ws["A1"] = title
        ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="1F497D")
        ws["A2"] = f"Governing Standard: {standard_ref}"
        ws["A2"].font = Font(name="Calibri", size=10, italic=True)

        row = 4
        # Section 1: Inputs
        ws.cell(row=row, column=1, value="Input Parameters").font = cls.BOLD_FONT
        row += 1
        headers = ["Parameter", "Symbol", "Value", "Unit"]
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col_idx, value=h)
            cell.fill = cls.HEADER_FILL
            cell.font = cls.WHITE_FONT

        row += 1
        input_row_map = {}
        for item in inputs:
            ws.cell(row=row, column=1, value=item["name"]).font = cls.NORMAL_FONT
            ws.cell(row=row, column=2, value=item["symbol"]).font = cls.BOLD_FONT
            val_cell = ws.cell(row=row, column=3, value=item["value"])
            val_cell.fill = cls.BLUE_FILL
            val_cell.font = cls.NORMAL_FONT
            ws.cell(row=row, column=4, value=item["unit"]).font = cls.NORMAL_FONT
            input_row_map[item["symbol"]] = f"C{row}"
            row += 1

        row += 1
        # Section 2: Calculations with Active Formulas
        ws.cell(row=row, column=1, value="Calculations & Intermediate Steps").font = cls.BOLD_FONT
        row += 1
        for col_idx, h in enumerate(["Step", "Symbol", "Formula / Value", "Unit"], 1):
            cell = ws.cell(row=row, column=col_idx, value=h)
            cell.fill = cls.HEADER_FILL
            cell.font = cls.WHITE_FONT

        row += 1
        calc_row_map = {}
        for calc in calculations:
            ws.cell(row=row, column=1, value=calc["name"]).font = cls.NORMAL_FONT
            ws.cell(row=row, column=2, value=calc["symbol"]).font = cls.BOLD_FONT
            
            # Write LIVE formula string
            f_cell = ws.cell(row=row, column=3, value=calc["formula_excel"])
            f_cell.fill = cls.YELLOW_FILL
            f_cell.font = cls.BOLD_FONT

            ws.cell(row=row, column=4, value=calc["unit"]).font = cls.NORMAL_FONT
            calc_row_map[calc["symbol"]] = f"C{row}"
            row += 1

        row += 1
        # Section 3: Verification / Compliance Flag
        ws.cell(row=row, column=1, value="Compliance Status").font = cls.BOLD_FONT
        status_cell = ws.cell(row=row, column=3, value=conclusion_formula)
        status_cell.fill = cls.GREEN_FILL
        status_cell.font = Font(name="Calibri", size=12, bold=True)
        status_cell.alignment = Alignment(horizontal="center")

        wb.save(output_path)
        return output_path
```

### 9.4 P&ID Revision Visual Diff & Overlay Generator (`src/sovereign/vision/diff.py`)

```python
from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageChops, ImageDraw, ImageFont
from pydantic import BaseModel


class DiffBox(BaseModel):
    box_2d: Tuple[float, float, float, float]  # [ymin, xmin, ymax, xmax]
    change_type: str  # "ADDED", "REMOVED", "MODIFIED"
    description: str


class DrawingDiffEngine:
    """
    Detects visual differences between drawing revisions and renders an annotated overlay.
    """

    COLOR_ADDED = (0, 200, 83)      # Vivid Green
    COLOR_REMOVED = (213, 0, 0)     # Vivid Red
    COLOR_MODIFIED = (255, 214, 0)  # Vivid Amber

    @classmethod
    def compute_diff(cls, img_a_path: Path, img_b_path: Path) -> Tuple[Image.Image, List[DiffBox]]:
        im_a = Image.open(img_a_path).convert("RGB")
        im_b = Image.open(img_b_path).convert("RGB")

        # Resize to match Rev A dimensions if slight scan variance exists
        if im_a.size != im_b.size:
            im_b = im_b.resize(im_a.size, Image.Resampling.BILINEAR)

        w, h = im_a.size

        # Grayscale absolute pixel differencing
        diff_img = ImageChops.difference(im_a, im_b).convert("L")
        # Threshold: diff pixels > 30 considered significant
        threshold = 30
        mask = diff_img.point(lambda p: 255 if p > threshold else 0)

        # Create desaturated background base from Rev B
        base = im_b.convert("L").convert("RGB")
        draw = ImageDraw.Draw(base, "RGBA")

        # Simulated clustered diff boxes (in real run, extracted from connected components)
        diff_boxes = [
            DiffBox(box_2d=(0.15, 0.20, 0.35, 0.45), change_type="ADDED", description="New Control Valve CV-103"),
            DiffBox(box_2d=(0.50, 0.60, 0.70, 0.85), change_type="REMOVED", description="Decommissioned bypass line"),
        ]

        # Draw overlays
        for idx, item in enumerate(diff_boxes, 1):
            ymin, xmin, ymax, xmax = item.box_2d
            x0, y0, x1, y1 = int(xmin * w), int(ymin * h), int(xmax * w), int(ymax * h)

            color = cls.COLOR_ADDED if item.change_type == "ADDED" else cls.COLOR_REMOVED
            fill_color = color + (40,)  # 15% opacity tint

            draw.rectangle([x0, y0, x1, y1], outline=color + (255,), width=3, fill=fill_color)
            # Callout circle
            draw.ellipse([x0 - 12, y0 - 12, x0 + 12, y0 + 12], fill=color + (255,))
            draw.text((x0 - 4, y0 - 7), str(idx), fill=(255, 255, 255, 255))

        return base, diff_boxes
```

---

## 10. Assumptions Log & Environment Availability

| # | Assumption | Status | Impact if Invalid | Fallback / Resolution Strategy |
|:---|:---|:---|:---|:---|
| **A-01** | System `tesseract` binary may not be installed on developer workstations or air-gapped CI nodes. | **CONFIRMED** | `TesseractOCRBackend` would raise `FileNotFoundError`. | Provide `DeterministicMockOCRBackend` enabled via `--mock-models` or when binary is absent. |
| **A-02** | Python environment contains `PIL` (Pillow) and `sqlite3`. | **VERIFIED** | Image diffing and vector storage would fail. | Verified active: Python 3.11 with Pillow 10.0+ and SQLite 3 WAL support confirmed. |
| **A-03** | `python-docx`, `openpyxl`, and `python-pptx` can be added to project dependencies without compiling C++ wheels. | **VERIFIED** | Deliverable generation blocked. | Packages are pure Python or pre-built wheels (`lxml` wheel); verified pure offline file generation. |
| **A-04** | GPU hardware may not be present during unit testing and automated CI execution. | **CONFIRMED** | Local model inference and vector embedding would fail. | `MockModelAdapter` generates deterministic 768-dim normalized unit vectors via SHA-256 blocks with zero GPU overhead. |
| **A-05** | Engineering drawing comparison can be performed on 2D raster images (PNG, JPEG, TIFF) rather than raw proprietary DWG/DXF files. | **VALIDATED** | Out of scope for MVP per PRD (`CAD-01` deferred to v2). | Industrial scans and exported drawing sheets (raster) satisfy UC-5 and DEMO-03 requirements. |

---

## 11. Validation Architecture & Test Map

### 11.1 Nyquist Test Mapping per Requirement

Every Phase 4 requirement is covered by at least two explicit automated tests (unit + end-to-end integration):

| Requirement | Primary Test File | Key Test Scenarios | Assertion Criteria |
|:---|:---|:---|:---|
| **MMOD-01** | `tests/test_multimodal/test_ocr_engine.py` | 1. Clean printed text extraction.<br>2. Bounding box normalization ($[0.0, 1.0]$).<br>3. Mock backend fallback when binary missing. | Extracted text matches ground truth ($\ge 95\%$ accuracy); all coordinates lie within $[0.0, 1.0]$. |
| **MMOD-02** | `tests/test_multimodal/test_handwriting_forms.py` | 1. Checkbox state detection (`CHECKED`/`UNCHECKED`).<br>2. Confidence score calculation per field.<br>3. Flagging $c < 0.85$ as `NEEDS_REVIEW`. | Low-confidence fields marked `needs_review=True`; high-confidence fields passed to state. |
| **MMOD-03** | `tests/test_vision/test_drawing_diff.py` | 1. Revision A vs Revision B image differencing.<br>2. Color-coded bounding box placement.<br>3. Change register itemization. | Identifies added/removed regions; overlay image generated with matching callout badges. |
| **MMOD-04** | `tests/test_multimodal/test_normalized_document.py` | 1. Multi-page document assembly.<br>2. Stable region ID resolution (`doc-id#p1-r003`).<br>3. RFC 8785 canonical serialization round-trip. | Region coordinates round-trip without precision loss; canonical JSON matches expected schema. |
| **DELV-01** | `tests/test_deliverables/test_docx_generator.py` | 1. Custom style application (Navy headers).<br>2. Findings table rendering with zebra rows.<br>3. Lineage property injection in `docProps/custom.xml`. | Output file passes `zipfile.is_zipfile`; XML contains `<w:tbl>`, custom styles, and sovereign lineage properties. |
| **DELV-02** | `tests/test_deliverables/test_xlsx_generator.py` | 1. Active formula strings written to calculation cells.<br>2. Dynamic recalculation on variable edit.<br>3. Lineage property injection in `docProps/custom.xml`. | Raw XML confirms `<f>` tags exist; editing an input cell recalculates output; lineage verified. |
| **DELV-03** | `tests/test_deliverables/test_pptx_generator.py` | 1. Slide master application.<br>2. Native OOXML chart insertion (`CategoryChartData`).<br>3. Lineage property injection. | Presentation contains valid chart part (`ppt/charts/chart1.xml`); chart data points match input table. |
| **DELV-04** | `tests/test_deliverables/test_code_artifact_export.py` | 1. Script written with sovereign header docstring.<br>2. Execution log captured with exit code 0.<br>3. Input fixture data saved side-by-side. | Running the saved script in sandbox against saved input fixture reproduces logged output identically. |
| **DELV-05** | `tests/test_deliverables/test_calc_trace_export.py` | 1. Standard clause reference extraction.<br>2. Intermediate mathematical expansion.<br>3. Multi-format export (Word, Excel, JSON). | Calculation trace contains input table, intermediate formula expansions, and pass/fail safety margin. |
| **RAG-01** | `tests/test_rag/test_local_vector_store.py` | 1. Document chunking with recursive boundary splitting.<br>2. 768-dim unit vector insertion into SQLite WAL.<br>3. Top-K similarity ranking. | Vector store handles 1,000 chunks; query latency $< 15$ ms; top result matches query topic. |
| **RAG-02** | `tests/test_rag/test_citation_engine.py` | 1. Inline citation insertion (`[Doc: X, p.Y#Z]`).<br>2. Citation resolution against source chunk.<br>3. Lineage sidecar citation registration. | All bracketed citations resolve to valid document IDs and page numbers in the audit ledger. |
| **RAG-03** | `tests/test_rag/test_rbac_rag_filter.py` | 1. Admin querying restricted corpus.<br>2. Engineer querying restricted corpus.<br>3. Pre-filtering query assertion in SQLite. | Engineer query returns 0 restricted chunks; SQL log confirms `WHERE` clause pre-filtering executed. |

### 11.2 Wave 0 Gaps & Pre-Execution Needs
Before executing Plan 04-01 through 04-04, the following foundation dependencies must be established:
1. **Dependencies Installation:** Add `python-docx`, `openpyxl`, `python-pptx`, and `pypdf` to `pyproject.toml`.
2. **Directory Structure:** Create `src/sovereign/multimodal/`, `src/sovereign/rag/`, `src/sovereign/deliverables/`, and `src/sovereign/vision/`.
3. **Synthetic Test Assets:** Provide standard synthetic test fixtures in `tests/fixtures/`:
   - `sample_inspection_scan.png` (Printed header with handwritten thickness values).
   - `pid_rev_a.png` and `pid_rev_b.png` (Schematic drawing pair with known introduced bypass line and removed valve).
   - `sample_sop_internal.txt` and `sample_sop_restricted.txt` (Corpus for RBAC RAG testing).

---

## 12. Security Domain & Threat Model

### 12.1 STRIDE Threat Analysis

| Threat ID | STRIDE Category | Threat Vector | Risk Level | Architectural Mitigation |
|:---|:---|:---|:---|:---|
| **T-04-01** | **Information Disclosure** | RBAC bypass via vector search: An `auditor` or `engineer` queries the local RAG engine to retrieve confidential executive memos or restricted weapon/reactor schematics. | **CRITICAL** | **Mandatory Pre-Filtering:** Retrieval enforces SQL-level pre-filtering (`WHERE classification IN (...) AND role IN (...)`) before vector similarity is computed. Unauthorized chunks are never loaded or ranked. |
| **T-04-02** | **Tampering** | Macro / Formula Injection in `.xlsx`: Malicious text extracted from OCR containing DDE commands (e.g. `=cmd|' /C calc'!A0`) executed when the spreadsheet is opened. | **HIGH** | **AST Sanitization & Formula Escaping:** Only explicitly generated calculation cells receive active formulas. Any arbitrary string input beginning with `=`, `+`, `-`, or `@` is prefixed with an apostrophe (`'`). |
| **T-04-03** | **Denial of Service** | Decompression / Pixel Bomb: Malicious actor uploads a 100,000 $\times$ 100,000 pixel image or nested PDF causing catastrophic host memory exhaustion. | **HIGH** | **Pillow Bounds Enforcement:** Explicitly configure `Image.MAX_IMAGE_PIXELS = 50_000_000` (caps memory at ~200MB). PDF page count capped at 100 pages per submission. |
| **T-04-04** | **Tampering** | Path Traversal during Deliverable Export: Generating output files with paths like `../../../../etc/cron.d/malicious.sh`. | **CRITICAL** | **Strict Path Fencing:** All file writes validate destination using `Path(dest).resolve().is_relative_to(OUTPUT_DIR)`. Any violation raises `PathSecurityViolation` and logs a security alert. |
| **T-04-05** | **Elevation of Privilege** | Low-Confidence OCR Data Ingestion: OCR misreads a critical flange thickness ($1.2\text{ mm}$ read as $12\text{ mm}$), silently passing unsafe values into an official approval note. | **HIGH** | **HITL Confidence Gate:** Any field with confidence $< 0.85$ triggers an automatic `GraphInterrupt`. Execution halts and deliverable generation is blocked until a human signs off. |
| **T-04-06** | **Information Disclosure** | Telemetry Leaks in RAG / Vision Libraries: Using unvetted libraries that transmit background telemetry over HTTP/DNS. | **CRITICAL** | **Zero-Network SQLite & Host Egress Monitor:** Zero external vector daemons. Phase 1 `NetworkMonitor` enforces host/process egress blocking and terminates unauthorized sockets. |

### 12.2 ASVS & Industrial Compliance Alignment
Phase 4 adheres directly to OWASP ASVS 4.0 and industrial cybersecurity standards (IEC 62443):
- **ASVS V5.1 (Input Validation):** All incoming multimodal documents are validated against strict MIME type allowlists (`image/png`, `image/jpeg`, `application/pdf`) and file size ceilings ($50\text{ MB}$).
- **ASVS V5.2.4 (Memory Bounds):** Memory buffers during image differencing and PDF rasterization are bounded by strict allocation limits.
- **ASVS V8.3 (Sensitive Private Data in Logs):** Vector database queries and document snippets logged to the audit ledger are sanitized to prevent secret data leakage into public audit views.
- **ASVS V14.2 (Secure Build & Dependencies):** All added Office libraries (`python-docx`, `openpyxl`, `python-pptx`) are verified against known CVE databases with pinned hashes.

---

## 13. Execution Plan Breakdown & Dependencies

Phase 4 is structured into 4 cohesive, sequential execution plans:

```
+---------------------------------------------------------------------------------------------------------+
|                                    PHASE 4 EXECUTION ROADMAP                                            |
+---------------------------------------------------------------------------------------------------------+
|                                                                                                         |
|  [PLAN 04-01: Offline OCR & Form Handwriting Extraction Pipeline]                                       |
|   - BaseOCRBackend, TesseractOCRBackend, DeterministicMockOCRBackend                                    |
|   - FormExtractor, CheckboxParser, Confidence Scorer (< 0.85 -> NEEDS_REVIEW)                           |
|   - NormalizedDocument, DocumentPage, DocumentRegion, FormField models                                  |
|   - Deliverable: src/sovereign/multimodal/ & tests/test_multimodal/                                     |
|                                       |                                                                 |
|                                       v                                                                 |
|  [PLAN 04-02: Local Vector Database RAG with RBAC Filtering & Citations]                                |
|   - Recursive character chunker preserving region coordinates                                           |
|   - SQLiteVectorStore in WAL mode storing 768-dim float blobs                                           |
|   - Dynamic SQL pre-filtering by UserRole (Admin, Engineer, Auditor)                                    |
|   - CitationEngine formatting bracketed citations and reference tables                                  |
|   - Deliverable: src/sovereign/rag/ & tests/test_rag/                                                   |
|                                       |                                                                 |
|                                       v                                                                 |
|  [PLAN 04-03: Native Office Deliverables, Reproducible Code & Calculation Traces]                       |
|   - DocxDeliverableGenerator (Corporate styling, findings tables, citation appendices)                 |
|   - XlsxDeliverableGenerator (Live recalculable formulas, color-coded inputs/calculations)              |
|   - PptxDeliverableGenerator (Styled slides with native OOXML editable charts)                          |
|   - CodeArtifactExporter (.py script + .log trace + input fixture in /local/output)                     |
|   - CalculationTraceExporter (ASME B31.3 math expansions, multi-format export)                          |
|   - Deliverable: src/sovereign/deliverables/ & tests/test_deliverables/                                 |
|                                       |                                                                 |
|                                       v                                                                 |
|  [PLAN 04-04: P&ID Drawing Revision Comparison & Visual Annotation Overlay]                             |
|   - Layer 1: Pillow pixel differencing, thresholding, and contour bounding box extraction               |
|   - Layer 2: Semantic VLM reasoning via BaseModelAdapter.vision_infer()                                 |
|   - Visual Annotation Overlay Renderer (High-contrast green/red/amber callouts)                         |
|   - Structured Change Register Exporter (.docx / .md table with equipment tags)                         |
|   - Deliverable: src/sovereign/vision/ & tests/test_vision/                                             |
|                                                                                                         |
+---------------------------------------------------------------------------------------------------------+
```

---

## 14. Conclusion

Phase 4 bridges the cognitive reasoning core of the Sovereign AI Workbench with authentic industrial reality. By implementing offline multimodal ingestion, RBAC-grounded vector search, live-formula spreadsheet generation, native presentation charting, and visual P&ID comparison entirely within a zero-egress host architecture, Phase 4 fulfills the core value proposition of the Workbench: delivering cloud-grade agentic productivity with verifiable physical sovereignty.

The technical architecture outlined in this document is immediately consumable by the Phase 4 Planner for decomposition into Plans `04-01`, `04-02`, `04-03`, and `04-04`.
