# Roadmap: Sovereign AI Workbench

## Overview

The Sovereign AI Workbench roadmap delivers an end-to-end demonstrable, air-gapped agentic AI platform tailored for the Smart India Hackathon (SIH). Executing as a Vertical MVP slice across 6 focused phases, it moves from foundational zero-egress enforcement and cryptographic auditability, through local model abstraction and isolated sandboxing, into multimodal processing and native Office deliverable generation, culminating in a unified multi-pane UI and 3 unassisted end-to-end industrial demonstration workflows.

## Phases

- [x] **Phase 1: Sovereign Foundation, Cryptographic Audit & Network Egress Monitoring** - Default-deny network guardrails, observable egress monitor, SHA-256 hash-chained audit logging, and binary attestation.
- [ ] **Phase 2: Local Model Management, Adapters & VRAM Scheduler** - Pluggable model adapter interface, task-based auto-routing, memory-aware model scheduling/swapping, and deterministic mock adapters.
- [ ] **Phase 3: Agentic State Machine, Tool Registry & Isolated Sandbox** - LangGraph state machine, typed tool registry, isolated zero-egress code sandbox with resource bounding, session persistence, self-correction, and HITL approval gates.
- [ ] **Phase 4: Multimodal Ingestion, Local RAG & Native Deliverable Engines** - Offline OCR and handwriting extraction, local vector database with RBAC-filtered retrieval, vision drawing comparison, and native Office (.docx, .xlsx, .pptx) deliverable generators.
- [ ] **Phase 5: Workbench Web Interface, CLI & Role-Based Access Control** - Localhost/intranet multi-pane web UI (trace, preview, approval queue, egress dashboard), administrative CLI, Python SDK, and 3-role RBAC enforcement.
- [ ] **Phase 6: SIH End-to-End Demonstration Workflows & Verification** - Packaging, sample datasets, guided execution, and full compliance validation of the 3 SIH demo workflows (Approval Note, Sandboxed Coding, Drawing Diff).

---

## Phase Details

### Phase 1: Sovereign Foundation, Cryptographic Audit & Network Egress Monitoring

**Goal:** Establish verifiable host/container zero-egress isolation, real-time connection telemetry, tamper-evident hash-chained audit logging, and startup binary attestation.
**Mode:** mvp
**Depends on:** Nothing (first phase)
**Requirements:** SOVG-01, SOVG-02, SOVG-03, SOVG-04, SOVG-05, SOVG-06
**Success Criteria:**

1. Host/container network monitor logs all active socket connections and outbound attempts with immediate allow/deny telemetry.
2. Audit logger records all system and agent events in an append-only, SHA-256 hash-chained JSON ledger where retroactive tampering is detected.
3. Model weight and binary checksum verification runs at startup and fails closed on corrupted or tampered files.
4. Output-to-source traceability generator attaches full model, tool, and document lineage metadata to generated deliverables.

**Plans:** 3/3 plans executed

Plans:

- [x] 01-01-PLAN.md
- [x] 01-02-PLAN.md
- [x] 01-03-PLAN.md

**Wave 1**

- [x] 01-01: Implement tamper-evident SHA-256 hash-chained audit logging engine and verification CLI

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02: Build host/process network monitoring service and default-deny egress test harness

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03: Implement binary/model checksum attestation verifier and deliverable lineage generator

### Phase 2: Local Model Management, Adapters & VRAM Scheduler

**Goal:** Construct a pluggable, model-agnostic inference layer supporting open-weight models (SGLang/vLLM/Ollama) alongside deterministic mock adapters, task auto-routing, and VRAM-aware scheduling.
**Mode:** mvp
**Depends on:** Phase 1
**Requirements:** MODL-01, MODL-02, MODL-03, MODL-04
**Success Criteria:**

1. A new model can be registered via a manifest file without modifying orchestrator code.
2. Incoming requests are classified and automatically routed to the proper model capability (reasoning, code, vision).
3. VRAM scheduler tracks memory budgets and prevents OOM crashes on a 24GB reference GPU.
4. A deterministic mock adapter allows running and verifying all pipelines on machines without discrete GPUs.

**Plans:** 3 plans

Plans:

- [ ] 02-01: Build uniform Model Manager interface and manifest registration schema
- [ ] 02-02: Implement local inference adapters (SGLang / vLLM / Ollama / llama.cpp) and deterministic mock test adapter
- [ ] 02-03: Implement task classification router and VRAM-aware model scheduler

### Phase 3: Agentic State Machine, Tool Registry & Isolated Sandbox

**Goal:** Deliver a cyclical agentic state machine with session persistence, typed tool schemas, isolated zero-egress code execution sandbox with resource bounds, bounded self-correction, and HITL approval checkpoints.
**Mode:** mvp
**Depends on:** Phase 2
**Requirements:** ORCH-01, ORCH-02, ORCH-03, ORCH-04, TOOL-01, TOOL-02, TOOL-03
**Success Criteria:**

1. Multi-step planner decomposes incoming user tasks into sequential tool and model calls.
2. Code sandbox executes generated Python scripts inside an isolated network namespace with CPU/memory/time bounds.
3. Code execution or tool errors trigger up to 3 automatic self-correction attempts.
4. Human approval gate pauses execution graph and persists state until explicit resume command.

**Plans:** 3 plans

Plans:

- [ ] 03-01: Build typed Tool Registry with schema validation and core system tools
- [ ] 03-02: Implement zero-network sandboxed code execution environment with cgroup/timeout limits
- [ ] 03-03: Implement LangGraph planner/executor cyclical state machine with HITL interrupt and bounded self-correction

### Phase 4: Multimodal Ingestion, Local RAG & Native Deliverable Engines

**Goal:** Implement offline OCR, handwriting extraction, local vector database indexing with RBAC-scoped retrieval, vision-based drawing comparison, and native Office (.docx, .xlsx, .pptx) file generators.
**Mode:** mvp
**Depends on:** Phase 3
**Requirements:** MMOD-01, MMOD-02, MMOD-03, MMOD-04, DELV-01, DELV-02, DELV-03, DELV-04, DELV-05, RAG-01, RAG-02, RAG-03
**Success Criteria:**

1. Scanned documents and handwriting are ingested into normalized text and bounding boxes with confidence scores.
2. Local vector database provides permission-scoped semantic search and returns inline source document citations.
3. Native Word (.docx) approval notes, Excel (.xlsx) sheets with live recalculable formulas, and PowerPoint (.pptx) decks are generated.
4. Vision pipeline detects visual and schematic differences between two drawing revisions and produces an annotated overlay.

**Plans:** 4 plans

Plans:

- [ ] 04-01: Implement offline OCR and structured form handwriting extraction pipeline
- [ ] 04-02: Build local vector database RAG pipeline with RBAC metadata filtering and inline citations
- [ ] 04-03: Implement native Office deliverable generators (.docx, .xlsx with formulas, .pptx) and calculation trace export
- [ ] 04-04: Implement engineering drawing / P&ID revision comparison and visual annotation overlay generator

### Phase 5: Workbench Web Interface, CLI & Role-Based Access Control

**Goal:** Deliver a localhost/intranet-only multi-pane web UI, command-line tool, minimal Python SDK, and consistent 3-role RBAC enforcement across all access surfaces.
**Mode:** mvp
**Depends on:** Phase 4
**Requirements:** UI-01, UI-02, UI-03, UI-04, UI-05
**Success Criteria:**

1. Multi-pane web UI displays live agent reasoning trace, document preview with bounding boxes, approval workflow, and real-time egress monitor.
2. Auditor role can inspect audit logs and network telemetry but is blocked from submitting tasks.
3. Power users can execute tasks, list models, and export audit trails via CLI and Python SDK.
4. Web and API servers bind exclusively to localhost/intranet addresses.

**Plans:** 3 plans

Plans:

- [ ] 05-01: Implement FastAPI backend endpoints, WebSocket event streaming, and RBAC middleware
- [ ] 05-02: Build multi-pane Web UI with guided demo modes and live network monitor dashboard
- [ ] 05-03: Implement Workbench CLI and lightweight Python SDK for task submission and audit export

### Phase 6: SIH End-to-End Demonstration Workflows & Verification

**Goal:** Package sample datasets, configure guided execution paths, and execute full cross-cutting verification for the 3 core SIH demo workflows under strict air-gapped conditions.
**Mode:** mvp
**Depends on:** Phase 5
**Requirements:** DEMO-01, DEMO-02, DEMO-03
**Success Criteria:**

1. Demo A executes unassisted: scanned inspection report → OCR → findings extraction → human approval → `.docx` approval note with source scan citations in `/local/output`.
2. Demo B executes unassisted: CSV parsing task → code generation → sandbox execution → auto-fix iteration → verified runnable script and execution log.
3. Demo C executes unassisted: two drawing revisions uploaded → visual difference detection → annotated overlay image and change summary.
4. Session verification confirms zero outbound network connections, 100% hash-chained audit log coverage, and Auditor role enforcement.

**Plans:** 2 plans

Plans:

- [ ] 06-01: Assemble sample datasets (inspection reports, historian CSVs, P&ID revisions) and automated demo test suite
- [ ] 06-02: Execute and document full verification session across all 3 demo workflows, audit trail, and zero-egress monitor

---

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Sovereign Foundation, Cryptographic Audit & Network Egress Monitoring | 3/3 | Complete | 2026-09-10 |
| 2. Local Model Management, Adapters & VRAM Scheduler | 0/3 | Not started | - |
| 3. Agentic State Machine, Tool Registry & Isolated Sandbox | 0/3 | Not started | - |
| 4. Multimodal Ingestion, Local RAG & Native Deliverable Engines | 0/4 | Not started | - |
| 5. Workbench Web Interface, CLI & Role-Based Access Control | 0/3 | Not started | - |
| 6. SIH End-to-End Demonstration Workflows & Verification | 0/2 | Not started | - |
