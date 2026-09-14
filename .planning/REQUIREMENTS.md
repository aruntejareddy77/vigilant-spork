# Requirements: Sovereign AI Workbench

**Defined:** 2026-09-09  
**Core Value:** Verifiable sovereign agentic productivity — autonomous multimodal task execution and auditable deliverable generation running 100% offline with observable zero-network egress.

## v1 Requirements

### Model Management & Routing (MODL)

- [x] **MODL-01**: System provides a pluggable adapter interface supporting local open-weight model registration via YAML/JSON manifest without modifying orchestrator code (FR-MM-1)
- [x] **MODL-02**: System automatically routes incoming user tasks to appropriate model class (reasoning/drafting, code execution, vision/multimodal) based on task classification (FR-MM-2)
- [x] **MODL-03**: Model manager tracks GPU VRAM usage and orchestrates model loading/unloading or graceful quantization to prevent out-of-memory crashes on single 24GB-class GPU (FR-MM-3)
- [x] **MODL-04**: System supports a deterministic test/mock model adapter allowing full end-to-end verification in environments without discrete GPU hardware

### Agent Orchestration & State Machine (ORCH)

- [x] **ORCH-01**: Agent runtime implements a multi-step planner and executor state machine (LangGraph-style) decomposing requests into sequential tool and model invocations (FR-AO-1)
- [x] **ORCH-02**: Agent maintains and persists session state across multi-turn task iterations so intermediate findings and drafts are retained without re-executing completed steps (FR-AO-4)
- [x] **ORCH-03**: System provides a bounded self-correction loop (configurable, default 3 attempts) when tools or code executions produce runtime errors (FR-AO-5)
- [x] **ORCH-04**: System enforces a Human-in-the-Loop (HITL) approval gate pausing graph execution before final deliverable generation and saving state until resumed (FR-AO-6)

### Tool Registry & Sandboxed Execution (TOOL)

- [x] **TOOL-01**: System provides a typed tool registry with declared input/output schemas enabling dynamic tool discovery and validation (FR-AO-2)
- [x] **TOOL-02**: Isolated code sandbox executes generated Python scripts with no network namespace access, bounded CPU/memory, and execution timeouts (FR-AO-3)
- [x] **TOOL-03**: Sandbox returns structured execution traces, stdout, stderr, and test assertion logs back to the agent runtime

### Multimodal Ingestion & Document Understanding (MMOD)

- [x] **MMOD-01**: Offline OCR pipeline extracts text, layout, and bounding boxes from scanned/photographed documents (FR-MI-1)
- [x] **MMOD-02**: Handwriting recognition extracts entries from structured inspection checklists and forms with confidence scoring and flagging for low confidence (FR-MI-2)
- [x] **MMOD-03**: Vision model analyzes engineering drawings, P&IDs, and equipment photographs to extract structural descriptions and visual elements (FR-MI-3)
- [x] **MMOD-04**: System normalizes ingested content into a unified representation preserving page numbers and region coordinates for citation (FR-MI-4)

### Native Deliverable Generation (DELV)

- [x] **DELV-01**: System generates native Microsoft Word (.docx) documents with structured headings, formatted findings tables, and corporate styling (FR-DG-1)
- [x] **DELV-02**: System generates native Microsoft Excel (.xlsx) workbooks with live mathematical formulas, cell references, and recalculable sheets (FR-DG-2)
- [x] **DELV-03**: System generates native Microsoft PowerPoint (.pptx) decks with styled slide layouts and editable native charts (FR-DG-3)
- [x] **DELV-04**: System exports reproducible code artifacts accompanied by verified execution logs and sample data inputs in `/local/output` (FR-DG-4)
- [x] **DELV-05**: System exports verifiable engineering calculation traces detailing applied standard clauses, input variables, and intermediate math steps (FR-DG-5)

### Local Knowledge Base & RAG (RAG)

- [x] **RAG-01**: System indexes designated local document folders into an on-premises vector database with offline chunking and local embeddings (FR-KB-1)
- [x] **RAG-02**: Agent generates answers with inline citations referencing specific document IDs and section/page locations (FR-KB-2)
- [x] **RAG-03**: Retrieval results are filtered dynamically by user RBAC permissions preventing unauthorized access to restricted documentation (FR-KB-4)

### Sovereignty Verification & Auditability (SOVG)

- [x] **SOVG-01**: Append-only structured local audit log records every agent step, tool call, model invocation, user action, and output file (FR-AS-1)
- [x] **SOVG-02**: Audit log entries are cryptographically hash-chained (SHA-256) such that tampering or deletion is immediately detectable (FR-AS-2)
- [x] **SOVG-03**: Real-time visible network monitor dashboard tracks socket connections and kernel-level network attempts with explicit allow/deny outcomes (FR-AS-3)
- [x] **SOVG-04**: Host and container network configurations enforce default-deny egress policies blocking all non-intranet/non-localhost routes (FR-AS-4)
- [x] **SOVG-05**: Startup verification enforces checksum/attestation matching for model files and core binaries, failing closed on discrepancy (FR-AS-5)
- [x] **SOVG-06**: Every deliverable carries metadata linking its content to specific models, tools, and source documents used (FR-AS-6)

### User Interfaces & Access Control (UI)

- [ ] **UI-01**: Web UI provides a guided step-by-step mode for executing the core SIH demonstration workflows (FR-UI-1)
- [ ] **UI-02**: Web application and backend APIs bind exclusively to localhost and designated intranet interfaces (FR-UI-2)
- [ ] **UI-03**: Full-featured CLI supports model registration, task execution, audit log export, and network status checks (FR-UI-3)
- [ ] **UI-04**: Minimal Python SDK supports programmatic task submission, status polling, and artifact retrieval (FR-UI-4)
- [ ] **UI-05**: Role-Based Access Control enforces least-privilege view and action filtering across Admin, Standard User, and Auditor roles (FR-UI-5)

### Core Demonstration Workflows (DEMO)

- [ ] **DEMO-01**: **Demo Workflow A (Approval Note)**: End-to-end ingestion of scanned/handwritten inspection report → findings extraction → human review/approval → styled Word (.docx) export with scan citations
- [ ] **DEMO-02**: **Demo Workflow B (Industrial Code & Sandbox)**: Generation of data parsing/engineering script → sandboxed execution against sample data → bounded self-correction loop on error → verified code & execution log output
- [ ] **DEMO-03**: **Demo Workflow C (Engineering Drawing Comparison)**: Multimodal comparison of two drawing/P&ID revisions → structural diff detection → annotated visual overlay & change summary export

---

## v2 Requirements

Deferred to post-SIH MVP release:

- **CONN-01**: Connectors for enterprise file shares (SMB/NFS), on-prem SharePoint, and Document Management Systems (DMS)
- **AUTH-01**: Active Directory / LDAP enterprise identity provider integration
- **DIST-01**: Multi-GPU distributed inference and tensor sharding across multi-node clusters
- **CERT-01**: Formal STQC / CERT-In compliance certification package and formal empanelment documentation
- **CAD-01**: Native CAD vector file parsing and direct drawing redlining
- **BATCH-01**: High-throughput asynchronous batch processing pipeline for bulk enterprise document archives

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Public Cloud APIs & Telemetry | Violates absolute air-gap sovereignty requirement |
| Multi-tenant SaaS Management | MVP targets single-organization, single-enclave deployment |
| Real-time Collaborative Editing | High architectural complexity with minimal value for initial demonstration |
| Mobile Native Apps | Industrial target users operate from ruggedized laptops or fixed desktop workstations |
| Voice Interface | High noise floor in plant/refinery environments; unneeded for MVP |
| Model Training / Fine-tuning | Focus is on efficient local inference, agentic orchestration, and RAG |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MODL-01 | Phase 2 | Complete |
| MODL-02 | Phase 2 | Complete |
| MODL-03 | Phase 2 | Complete |
| MODL-04 | Phase 2 | Complete |
| ORCH-01 | Phase 3 | Pending |
| ORCH-02 | Phase 3 | Pending |
| ORCH-03 | Phase 3 | Pending |
| ORCH-04 | Phase 3 | Pending |
| TOOL-01 | Phase 3 | Pending |
| TOOL-02 | Phase 3 | Pending |
| TOOL-03 | Phase 3 | Pending |
| MMOD-01 | Phase 4 | Complete |
| MMOD-02 | Phase 4 | Complete |
| MMOD-03 | Phase 4 | Complete |
| MMOD-04 | Phase 4 | Complete |
| DELV-01 | Phase 4 | Complete |
| DELV-02 | Phase 4 | Complete |
| DELV-03 | Phase 4 | Complete |
| DELV-04 | Phase 4 | Complete |
| DELV-05 | Phase 4 | Complete |
| RAG-01 | Phase 4 | Complete |
| RAG-02 | Phase 4 | Complete |
| RAG-03 | Phase 4 | Complete |
| SOVG-01 | Phase 1 | Complete |
| SOVG-02 | Phase 1 | Complete |
| SOVG-03 | Phase 1 | Complete |
| SOVG-04 | Phase 1 | Complete |
| SOVG-05 | Phase 1 | Complete |
| SOVG-06 | Phase 1 | Complete |
| UI-01 | Phase 5 | Pending |
| UI-02 | Phase 5 | Pending |
| UI-03 | Phase 5 | Pending |
| UI-04 | Phase 5 | Pending |
| UI-05 | Phase 5 | Pending |
| DEMO-01 | Phase 6 | Pending |
| DEMO-02 | Phase 6 | Pending |
| DEMO-03 | Phase 6 | Pending |

**Coverage:**

- v1 requirements: 37 total
- Mapped to phases: 37
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-09*  
*Last updated: 2026-09-10 after Phase 1 completion (SOVG-01 through SOVG-06 complete)*
