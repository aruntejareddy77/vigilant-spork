# Sovereign AI Workbench

## What This Is

The Sovereign AI Workbench is a self-hosted, air-gapped, model-agnostic agentic AI platform engineered for refineries, public sector undertakings (PSUs), defense-linked manufacturing units, and regulated government enclaves. It delivers cloud-assistant-grade engineering and executive productivity—multi-step task execution, multimodal document understanding, native Office deliverable generation, and sandboxed code execution—while providing continuous, mathematically and empirically verifiable proof that zero data ever leaves the on-premises environment.

## Core Value

Verifiable sovereign agentic productivity: autonomous multimodal task execution and auditable deliverable generation running 100% offline with continuously observable zero-network egress.

## Business Context

- **Customer**: Refineries, Public Sector Undertakings (PSUs), defense-linked manufacturers, critical infrastructure operators, and government offices with absolute data-sovereignty mandates.
- **Revenue model**: On-premises enterprise/enclave deployment licensing, appliance bundles, and high-security compliance support.
- **Success metric**: 3 of 3 core demonstration workflows running end-to-end unassisted on a single reference host with 0 external network packets and 100% audit trail traceability.
- **Strategy notes**: Built for Smart India Hackathon (SIH) with strict adherence to `Sovereign_AI_Workbench_PRD.md` as primary requirements authority and `Air-Gapped Industrial AI Workbench.md` as architectural reference.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] **FR-MM-1**: Pluggable model adapter interface allowing open-weight models to register via manifest without orchestrator code changes
- [ ] **FR-MM-2**: Task-to-model auto-routing based on task classification (drafting, code, multimodal, calculation)
- [ ] **FR-MM-3**: GPU memory-aware model scheduling and swapping on reference single-GPU hardware
- [ ] **FR-AO-1**: Multi-step agent planner/executor state machine with dynamic decomposition and bounded replanning
- [ ] **FR-AO-2**: Declared tool registry with strict input/output schemas (file I/O, search, OCR, sandbox, spreadsheet, office docs)
- [ ] **FR-AO-3**: Sandboxed code execution with zero network namespace, memory/CPU quotas, and bounded execution timeouts
- [ ] **FR-AO-4**: Session state persistence across multi-step execution turns avoiding redundant tool calls
- [ ] **FR-AO-5**: Bounded self-correction loop for code execution and tool failures (configurable default 3 iterations)
- [ ] **FR-AO-6**: Human-in-the-loop (HITL) approval gate before final deliverable generation for sensitive operations
- [ ] **FR-MI-1**: Local OCR pipeline for scanned and photographed printed documents with bounding box layout extraction
- [ ] **FR-MI-2**: Handwriting recognition on structured forms (inspection checklists, approval sheets) with confidence scoring
- [ ] **FR-MI-3**: Local vision model analysis for photographs and engineering drawing / P&ID schematics
- [ ] **FR-MI-4**: Unified multimodal document representation with page and region coordinates for citation
- [ ] **FR-DG-1**: Native Word (.docx) generation with structured headings, tables, and corporate styling
- [ ] **FR-DG-2**: Native Excel (.xlsx) generation with live formulas, intermediate steps, and recalculable sheets
- [ ] **FR-DG-3**: Native PowerPoint (.pptx) deck generation with editable native charts derived from extracted figures
- [ ] **FR-DG-4**: Reproducible code artifacts saved with sandbox execution and test verification logs
- [ ] **FR-DG-5**: Transparent engineering calculation trace exports with formula and standards references
- [ ] **FR-KB-1**: Local document indexing and semantic retrieval using offline vector embeddings
- [ ] **FR-KB-2**: Citation-backed generation linking generated sentences and claims directly to source document IDs
- [ ] **FR-KB-4**: Access-scoped retrieval strictly filtering search results according to user RBAC clearance
- [ ] **FR-AS-1**: Structured, append-only local audit log recording every agent step, tool call, model invocation, and deliverable
- [ ] **FR-AS-2**: Tamper-evident hash-chained audit logging (SHA-256) where modifications break integrity verification
- [ ] **FR-AS-3**: Real-time visible network monitor dashboard showing live connection attempts and allow/deny telemetry
- [ ] **FR-AS-4**: Default-deny network policy enforcement at host/container boundaries blocking external routes
- [ ] **FR-AS-5**: Signed model binary and script checksum/attestation verification at startup (fail-closed)
- [ ] **FR-AS-6**: Output-to-source traceability linking final deliverables to exact model, tool, and input document lineage
- [ ] **FR-UI-1**: Localhost/intranet web UI featuring guided step-by-step demo mode for 3 core SIH workflows
- [ ] **FR-UI-2**: Localhost/intranet-only binding with no external interface exposure
- [ ] **FR-UI-3**: Full-featured CLI for installation, model management, task submission, and audit export
- [ ] **FR-UI-4**: Minimal Python SDK for programmatic task submission and artifact retrieval
- [ ] **FR-UI-5**: Role-based access control (Admin, Standard User, Auditor) enforced consistently across UI, CLI, and API
- [ ] **DEMO-A**: Workflow A: Scanned Inspection Report → Approval Note (.docx) with citations to scan regions
- [ ] **DEMO-B**: Workflow B: Industrial Coding Task with Sandboxed Execution & Self-Correction (.py + execution log)
- [ ] **DEMO-C**: Workflow C: Multimodal Drawing / P&ID Revision Comparison (annotated overlay image + change summary)

### Out of Scope

- **Cloud APIs or external model services** — Absolute prohibition; violates data sovereignty.
- **Multi-tenant SaaS console** — MVP is single-server / single-enclave deployment.
- **Real-time collaborative document editing** — Adds concurrent conflict complexity unnecessary for MVP.
- **Native CAD file editing** — Parsing drawing images/scans is supported; editing native CAD binary formats is not.
- **Model fine-tuning / training pipelines** — Inference and local RAG only for MVP.
- **Distributed multi-node GPU clusters** — Single-server reference architecture for MVP.
- **Voice interface & mobile native applications** — Out of scope for industrial desktop/intranet workbench.
- **Third-party telemetry, crash reports, or phone-home updates** — Strictly excluded for air-gap integrity.

## Context

- **Smart India Hackathon (SIH) MVP**: Focus on high-impact demonstrable capabilities, robust end-to-end reliability, and verifiable air-gap architecture over premature multi-datacenter complexity.
- **Primary Specification**: `Sovereign_AI_Workbench_PRD.md` defines the functional requirements, user personas, acceptance criteria, and demo checklists.
- **Technical Research**: `Air-Gapped Industrial AI Workbench.md` provides architectural depth (eBPF process attribution, SGLang prefix caching, Docling/Marker layout parsing, LangGraph state machine, container isolation).

## Constraints

- **Security & Network**: Must enforce default-deny egress; 0 external outbound network packets during operation.
- **Deployment**: Self-contained on a single Linux host (with Windows/local development and demonstration flexibility), running entirely offline.
- **Hardware Profile**: Must accommodate mid-range GPU (24GB VRAM class) or provide deterministic graceful degradation / mock adapters for lightweight test environments without GPU hardware.
- **Auditability**: 100% of agent actions must be captured in an immutable hash-chained audit log.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Sovereign_AI_Workbench_PRD.md as Primary Spec | Ensures rigorous adherence to functional requirements, acceptance criteria, and demo requirements | — Pending |
| Air-Gapped Industrial AI Workbench.md as Technical Research | Informs architecture (LangGraph state machine, eBPF/iptables network monitor, Docling/Tesseract OCR, Qdrant/vector RAG) without adding rigid constraints | — Pending |
| Vertical MVP Project Structure | Delivers demonstrable end-to-end slices (Demo A, Demo B, Demo C) quickly rather than waiting for horizontal layers | — Pending |
| Interactive GSD Workflow Mode | Ensures user has full visibility and confirmation at each planning and execution milestone | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-09-09 after initialization*
