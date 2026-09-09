# Sovereign AI Workbench
## Product Requirements Document (PRD)

**Document status:** Draft v1.0
**Prepared for:** Engineering Leadership, Security/Compliance Officers, Product Design Teams
**Classification:** Internal — treat as pre-decisional

---

### 1. Title and One-Line Summary

**Sovereign AI Workbench** — a self-hosted, air-gapped, model-agnostic agentic AI platform that gives refineries, PSUs, defence-linked manufacturers, and government offices cloud-assistant-grade productivity (multi-step task execution, multimodal document understanding, native Office deliverable generation) while providing continuous, verifiable proof that no data ever leaves the premises.

---

### 2. Purpose and Background

Refineries, public sector undertakings, defence-linked manufacturing units, and government offices generate a high volume of routine but sensitive knowledge work: approval notes, board presentations, engineering calculations, internal code, scanned drawings, and inspection reports. The underlying data — P&IDs, financial data, vendor negotiation records, unreleased designs, internal correspondence, and SOPs — is subject to data-sovereignty, contractual, or statutory restrictions that prohibit transmission to third-party cloud services.

As a result, these organizations cannot use cloud AI assistants (e.g., Claude, Codex, ChatGPT) despite the same categories of staff performing the same categories of repetitive knowledge work that such assistants excel at elsewhere. Today they face two unsatisfactory alternatives: continue doing this work manually, or allow shadow use of public cloud AI tools in violation of policy, creating undocumented data-exfiltration risk.

Open-weight large reasoning models have reached a capability level, and consumer/prosumer GPU hardware has reached a price-performance level, where a genuinely useful, locally deployable agentic assistant is now feasible. No existing product combines (a) model-agnostic local inference, (b) agentic multi-step tool use, (c) multimodal document understanding, and (d) continuously verifiable zero-egress operation into a single deployable system targeted at this market. This PRD defines the requirements for that system (the "Workbench").

**Primary personas:**
- **Plant/Field Engineer** — drafts inspection findings, approval notes, and technical memos from scanned/handwritten source material.
- **Design/Automation Engineer** — performs engineering calculations, reviews or writes internal code, analyzes drawings/P&IDs.
- **PSU/Government Executive Assistant** — synthesizes internal correspondence and reports into board-ready presentations.
- **IT Administrator** — deploys, patches, and operates the Workbench on an isolated network.
- **Security/Compliance Officer (CISO/Auditor)** — must independently verify that the system never contacts external networks and that every output is traceable to its inputs.

---

### 3. Goals and Success Metrics

**Product goals**
1. Match the day-to-day usability of cloud AI assistants for the target task set, without any outbound network dependency.
2. Support multiple open-weight models behind a single interface, selected automatically per task type.
3. Execute genuine multi-step agentic workflows that produce real deliverables (Word/PPT/Excel/code), not just chat responses.
4. Process multimodal, sensitive-format inputs (scanned PDFs, handwriting, engineering drawings, photographs).
5. Make data sovereignty a continuously observable property of the system, not a one-time assertion.
6. Allow new models and tools to be added by configuration, not by re-architecture.

**Measurable success metrics**

| # | Metric | Target |
|---|---|---|
| 1 | Demo workflows completed end-to-end on one mid-range-GPU server | 3 of 3 |
| 2 | External network calls during a full demo session (verified by network monitor) | 0 |
| 3 | Actions represented in the audit log (user, model, source document IDs, timestamps) | 100% of agent/tool actions |
| 4 | RBAC access-control test suite pass rate (least-privilege enforcement) | 100% |
| 5 | Text summarization / approval-note drafting latency, P95, reference hardware | < 30 s |
| 6 | Moderate-length multimodal task latency, P95, reference hardware | < 2 min |
| 7 | Engineering effort to onboard one additional open-weight model (adapter config only, no core-code change) | < 1 engineer-day |
| 8 | Time for a non-expert user to complete a guided demo workflow unassisted | < 10 min |
| 9 | Signed attestation coverage for shipped model binaries and deployment scripts | 100% |

---

### 4. Key Use Cases and Example Workflows

**UC-1: Approval Note from a Scanned Inspection Report**
- **Persona:** Plant/Field Engineer
- **Trigger:** Uploads a scanned or photographed inspection report (may include handwriting) via the web UI.
- **Flow:** OCR/vision pipeline extracts text and layout → agent identifies discrete findings and severities → planner selects the "approval note" template and drafts the note, citing each finding back to a page/region of the source scan → user reviews and edits inline → agent exports a formatted Word document.
- **Expected outputs:** `.docx` approval note; structured findings JSON; audit trail linking each drafted sentence to a source-document region.

**UC-2: Engineering Calculation Check and Calc Sheet**
- **Persona:** Design Engineer
- **Trigger:** "Check this pipe wall-thickness calculation against ASME B31.3 and produce a calc sheet."
- **Flow:** Agent parses input values (from chat, a spreadsheet, or a scanned handwritten sheet) → retrieves the relevant formula/standard reference from the local knowledge base → performs the calculation via a deterministic sandboxed numeric tool (not free-text LLM arithmetic) → cross-checks the result against the code requirement → writes an Excel workbook with visible formulas, intermediate steps, and a pass/fail flag.
- **Expected outputs:** `.xlsx` calculation sheet with live formulas; step-by-step trace; audit log entry recording which standard/formula version was used.

**UC-3: Internal Code Generation, Sandbox Execution, and Debug Iteration**
- **Persona:** Automation/IT Engineer
- **Trigger:** "Write a script to parse our historian's CSV export and flag out-of-range readings; test it on this sample file."
- **Flow:** Planner decomposes the request into subtasks → code-capable model generates the script → sandbox executes it against the supplied sample data with no network access → test results are captured → on failure, the agent inspects the error, revises the code, and re-runs, up to a bounded number of iterations → final code and results are surfaced with the full execution trace.
- **Expected outputs:** Source file(s); test/execution log; pass/fail report; iteration history.

**UC-4: Board Deck Synthesis from Internal Documents**
- **Persona:** PSU/Government Executive Assistant
- **Trigger:** "Summarize this quarter's incident reports and vendor correspondence into a board-ready presentation."
- **Flow:** Agent searches the local, on-premises document index/vector store for relevant material → synthesizes a structured outline → generates slides, including simple charts built from extracted figures → user edits placeholder sections.
- **Expected outputs:** `.pptx` deck; per-slide citation back to internal document IDs; audit trail of retrieved sources.

**UC-5: Engineering Drawing / P&ID Revision Comparison**
- **Persona:** Design/Maintenance Engineer
- **Trigger:** Uploads two revisions of a drawing (scan or photograph) and asks "what changed between these revisions?"
- **Flow:** Vision model performs layout- and symbol-aware comparison → differences (added/removed/relabeled elements) are identified → agent produces an annotated overlay image plus a textual change summary suitable for a change register entry.
- **Expected outputs:** Annotated image file(s); change-summary document; audit log entry.

---

### 5. Product Scope

#### 5.1 MVP Features

**Deployment**
- Single-command installer for a single Ubuntu LTS server with one supported mid-range GPU.
- Pre-flight hardware/driver check (GPU, VRAM, disk, CUDA/ROCm version) before install proceeds.
- Default-deny network policy applied automatically as part of installation, not as a manual post-install step.

**Model layer**
- Model manager hosting at least one mid-size open-weight text/reasoning model and at least one vision/OCR-capable model, both running fully offline.
- Model auto-selection across at least three task classes: document summarization/drafting, code generation with sandbox execution, and multimodal scanned-document understanding.
- Model catalog with manifest metadata (capability tags, size, quantization, VRAM requirement, checksum).

**Agentic runtime**
- Planner/executor loop capable of multi-step task decomposition.
- Tool registry covering: file read/write, local document search, OCR, sandboxed code execution, spreadsheet read/write.
- Session state persisted across iterations of a single task.

**Multimodal**
- OCR pipeline for scanned/printed text.
- Handwriting recognition for common structured forms (inspection checklists, approval sheets).
- Vision-model support for photographs and drawing images.

**Deliverables**
- Native generation of `.docx`, `.pptx`, and `.xlsx` files.
- Code artifacts saved as runnable source files with an accompanying execution/test log.
- Calculation traces showing formulas and intermediate steps, not only final numbers.

**Sovereignty verification**
- Structured, append-only local audit log for every agent/tool action.
- Visible network monitor (e.g., iptables counters or eBPF trace) demonstrating zero outbound connections during a session.
- Signed manifests/checksums for model binaries and deployment scripts, verifiable at install time and at runtime.

**Interfaces**
- Web UI reachable only on localhost/intranet, with guided step-by-step mode for the three demo workflows.
- CLI for power users covering install, model management, and task submission.
- Minimal SDK (Python) for programmatic task submission and result retrieval.

**Access control**
- Baseline RBAC with at least three roles (Admin, Standard User, Auditor/read-only).

#### 5.2 Out of Scope (MVP and near-term)

- Cloud fallback, hybrid cloud/on-prem operation, or any code path capable of outbound calls.
- Mobile native applications.
- Multi-tenant SaaS management console; MVP is single-organization, single-server.
- Real-time multi-user collaborative document editing.
- Native CAD editing (viewing/parsing of drawing images is in scope; editing native CAD files is not).
- Model fine-tuning/training pipelines (inference only in MVP).
- Voice interface.
- Multi-node/distributed GPU clustering (single-node only until Beta/GA).
- Formal third-party security certification (e.g., Common Criteria, CERT-In empanelment) — tracked as a GA-readiness item, not an MVP deliverable.
- Non-English language support beyond what the selected base models natively provide.

---

### 6. Functional Requirements

Each requirement lists a rationale, a testable acceptance criterion, and a priority (**Must** / **Should** / **Could**).

#### 6.1 Model Management and Auto-Selection

**FR-MM-1 — Pluggable model adapter interface**
- *Requirement:* The Model Manager shall expose a uniform adapter interface (load, unload, generate, embed, vision-infer) so any conforming open-weight model can be registered without changes to the orchestrator.
- *Rationale:* Decouples orchestration logic from any single model family, satisfying the model-agnostic architecture requirement.
- *Acceptance criteria:* A second model of a different architecture family is registered and successfully invoked using only a manifest file and adapter config; no orchestrator code is modified.
- *Priority:* Must

**FR-MM-2 — Task-to-model auto-routing**
- *Requirement:* The system shall automatically route a submitted task to an appropriate registered model based on task-type classification (text drafting, code, multimodal, calculation) and declared model capabilities.
- *Rationale:* Users should not need to manually pick a model; correct routing is core to the "usable like a cloud assistant" goal.
- *Acceptance criteria:* Across the three MVP demo workflows, the correct model class (text, code, or vision) is selected automatically in 100% of test runs, logged in the audit trail.
- *Priority:* Must

**FR-MM-3 — GPU memory-aware scheduling**
- *Requirement:* The Model Manager shall track available GPU memory and select/quantize/load models such that concurrent or sequential model use does not exceed available VRAM.
- *Rationale:* Mid-range GPUs have limited VRAM; naive concurrent loading will crash the system.
- *Acceptance criteria:* Running the text model and the vision model in the same session on the reference GPU completes without an out-of-memory failure; scheduler logs show load/unload decisions.
- *Priority:* Must

**FR-MM-4 — Runtime hot-add of new models**
- *Requirement:* An administrator shall be able to add a new model to the catalog and make it selectable without restarting the orchestrator service.
- *Rationale:* Supports the extensibility goal and reduces operational downtime when expanding capability.
- *Acceptance criteria:* A new model is registered via CLI/UI and appears as a selectable option within one polling interval, without a service restart.
- *Priority:* Should

**FR-MM-5 — Quantization and sharding support**
- *Requirement:* The Model Manager shall support loading quantized (e.g., 4-bit/8-bit) model variants and, where a model exceeds single-GPU VRAM, layer/tensor sharding across available devices.
- *Rationale:* Enables use of larger open-weight models on mid-range hardware, and multi-GPU scaling in Beta/GA.
- *Acceptance criteria:* A quantized variant of the primary model runs within the documented VRAM budget for the reference GPU with acceptance-level output quality (human review pass).
- *Priority:* Should

**FR-MM-6 — Manual model override**
- *Requirement:* A power user shall be able to override auto-selection and explicitly pin a task to a chosen model via CLI/SDK.
- *Rationale:* Supports troubleshooting, benchmarking, and cases where auto-routing is suboptimal.
- *Acceptance criteria:* CLI flag `--model <id>` bypasses auto-routing and the audit log reflects a manual-override flag.
- *Priority:* Could

#### 6.2 Agent Orchestration and Tools

**FR-AO-1 — Multi-step planner/executor**
- *Requirement:* The agent runtime shall decompose a user request into an ordered sequence of steps, execute each step (invoking tools/models as needed), and re-plan when a step fails or returns unexpected output.
- *Rationale:* Core capability distinguishing an agentic workbench from a single-turn chatbot.
- *Acceptance criteria:* UC-1 (inspection report → approval note) completes as a traceable sequence of at least four distinct logged steps (ingest → extract → draft → export) without manual intervention between steps.
- *Priority:* Must

**FR-AO-2 — Tool registry with declared schemas**
- *Requirement:* Every tool (file I/O, document search, OCR, code sandbox, spreadsheet engine) shall be registered with a name, description, and input/output schema that the planner uses to select and invoke it.
- *Rationale:* Enables safe, structured tool invocation and supports later addition of new tools without core changes.
- *Acceptance criteria:* A new tool can be registered via a config/schema file and appears as invocable by the planner without orchestrator code changes.
- *Priority:* Must

**FR-AO-3 — Sandboxed code execution**
- *Requirement:* Code generated or requested by the user shall execute only inside an isolated sandbox with no network namespace access, bounded CPU/memory/time, and a restricted filesystem view.
- *Rationale:* Prevents both accidental data exfiltration and unbounded resource consumption from generated code.
- *Acceptance criteria:* A sandboxed script attempting an outbound network call is blocked and logged; a runaway/infinite-loop script is terminated at the configured time limit.
- *Priority:* Must

**FR-AO-4 — Session state persistence**
- *Requirement:* The agent shall persist intermediate state (retrieved documents, partial drafts, tool outputs) for the duration of a task, allowing multi-turn refinement without re-executing completed steps.
- *Rationale:* Avoids redundant computation and supports iterative user review (e.g., editing a drafted approval note before export).
- *Acceptance criteria:* A user edit to a drafted note after step 3 does not trigger re-execution of steps 1–2; session log shows step reuse.
- *Priority:* Must

**FR-AO-5 — Bounded self-correction loop**
- *Requirement:* On tool/code failure, the agent shall attempt a bounded number of automatic correction iterations (configurable, default 3) before surfacing the failure to the user.
- *Rationale:* Matches the required "debug iteration" behavior in the coding demo workflow while preventing runaway retry loops.
- *Acceptance criteria:* UC-3 demonstrates at least one automatic failure → fix → re-run cycle, and the iteration count never exceeds the configured bound in testing.
- *Priority:* Must

**FR-AO-6 — Human approval gate before finalization**
- *Requirement:* The agent shall present a review/approval step before any deliverable is marked "final" and written to the output directory, for roles where this is configured as mandatory.
- *Rationale:* Regulated environments require a human-in-the-loop checkpoint before AI-drafted material is treated as an official document.
- *Acceptance criteria:* For a role with the approval gate enabled, no `.docx`/`.pptx`/`.xlsx` deliverable is written to `/local/output` without a recorded approval action in the audit log.
- *Priority:* Should

#### 6.3 Multimodal Ingestion and Processing

**FR-MI-1 — OCR for scanned/printed documents**
- *Requirement:* The system shall extract machine-readable text and layout from scanned or photographed printed documents entirely on-premises.
- *Rationale:* Foundational capability for processing inspection reports, correspondence, and SOPs.
- *Acceptance criteria:* On a representative sample set of scanned inspection reports, extracted text achieves an acceptable word-level accuracy threshold agreed with stakeholders (baseline target ≥ 95% on clean scans).
- *Priority:* Must

**FR-MI-2 — Handwriting recognition on structured forms**
- *Requirement:* The system shall extract handwritten entries from common structured forms (checklists, approval sheets) with confidence scoring per field.
- *Rationale:* Many inspection and approval records are partially or fully handwritten.
- *Acceptance criteria:* On a representative handwriting sample set, extracted fields include a confidence score, and low-confidence fields are flagged for human review rather than silently accepted.
- *Priority:* Must

**FR-MI-3 — Image and drawing understanding**
- *Requirement:* The system shall accept photographs and scanned engineering drawings and produce a structured description of visible elements sufficient to support findings extraction or revision comparison.
- *Rationale:* Required for UC-5 and for general field-photo documentation use cases.
- *Acceptance criteria:* Given two drawing revisions, the system identifies at least the sample set of introduced test differences and produces an annotated overlay.
- *Priority:* Must

**FR-MI-4 — Unified multimodal document representation**
- *Requirement:* All ingested content (text, OCR output, handwriting, image regions) shall be normalized into a single internal document representation with page/region references usable for citation.
- *Rationale:* Enables consistent grounding/citation regardless of source modality.
- *Acceptance criteria:* A drafted approval note references specific page/region IDs of the source scan for each extracted finding, traceable in the audit log.
- *Priority:* Must

**FR-MI-5 — Confidence-gated escalation**
- *Requirement:* When OCR/vision confidence for a document region falls below a configurable threshold, the system shall flag the region rather than passing a guessed value silently into downstream drafting.
- *Rationale:* Prevents silent propagation of misread data into official deliverables.
- *Acceptance criteria:* Regions below threshold appear in the UI as "needs review" and are excluded from auto-drafted text until confirmed.
- *Priority:* Should

#### 6.4 Deliverable Generation

**FR-DG-1 — Native Word document generation**
- *Requirement:* The system shall generate `.docx` files with standard formatting (headings, tables, styles) suitable for direct organizational use, not plain-text dumps.
- *Rationale:* Deliverables must be usable without manual reformatting to be adopted.
- *Acceptance criteria:* Generated approval note opens correctly in standard word processors with intact headings, a findings table, and consistent styling.
- *Priority:* Must

**FR-DG-2 — Native Excel generation with live formulas**
- *Requirement:* The system shall generate `.xlsx` files where calculation results are backed by real spreadsheet formulas, not hard-coded values.
- *Rationale:* Engineering calc sheets must be independently auditable and re-computable by the recipient.
- *Acceptance criteria:* Opening the generated workbook and changing an input cell recalculates dependent cells correctly.
- *Priority:* Must

**FR-DG-3 — Native PowerPoint generation**
- *Requirement:* The system shall generate `.pptx` decks including simple charts derived from extracted data, not only text-only slides.
- *Rationale:* Board-level deliverables require visual summarization.
- *Acceptance criteria:* Generated deck includes at least one native (editable) chart object sourced from extracted figures.
- *Priority:* Should

**FR-DG-4 — Reproducible code artifacts with execution logs**
- *Requirement:* Generated code shall be saved as runnable source files accompanied by the sandbox execution/test log used to validate it.
- *Rationale:* Supports the "coding task executed and verified in a sandbox" MVP requirement and downstream code review.
- *Acceptance criteria:* Source file and matching execution log are both present in `/local/output`, and re-running the saved script against the saved sample data reproduces the logged result.
- *Priority:* Must

**FR-DG-5 — Calculation trace export**
- *Requirement:* Numeric/engineering results shall be exportable with a visible step-by-step trace (inputs, intermediate values, formula/standard reference, final result), not only the final number.
- *Rationale:* Regulated engineering sign-off requires an auditable calculation path.
- *Acceptance criteria:* Exported calc sheet includes an intermediate-steps section referencing the specific formula/standard clause applied.
- *Priority:* Must

#### 6.5 Local Knowledge Base Integration and Grounding

**FR-KB-1 — Local document indexing and semantic search**
- *Requirement:* The system shall index designated local document repositories (file shares, uploaded corpora) into a locally hosted vector store and support semantic retrieval over them.
- *Rationale:* Required for grounded synthesis tasks (e.g., UC-4) and for citation-backed answers.
- *Acceptance criteria:* A query returns relevant passages from the indexed corpus with document ID and location, verified against a labeled test set.
- *Priority:* Must

**FR-KB-2 — Citation-backed generation**
- *Requirement:* Where a generated deliverable draws on retrieved local documents, each substantive claim shall be traceable to a specific source document ID.
- *Rationale:* Builds trust and supports audit/compliance review of AI-assisted outputs.
- *Acceptance criteria:* Sampled sentences in a generated board deck each resolve to a specific indexed source document in the audit log.
- *Priority:* Must

**FR-KB-3 — Incremental re-indexing**
- *Requirement:* The knowledge base shall support incremental re-indexing of new or changed documents without a full rebuild.
- *Rationale:* Operational usability for growing document repositories on an air-gapped network with no continuous connectivity.
- *Acceptance criteria:* Adding one new document to a watched folder makes it retrievable without re-indexing the full corpus, within a defined SLA (e.g., under 5 minutes for a typical document).
- *Priority:* Should

**FR-KB-4 — Access-scoped retrieval**
- *Requirement:* Retrieval results shall be filtered according to the requesting user's RBAC permissions on the underlying documents.
- *Rationale:* Prevents the AI layer from becoming a bypass around existing document access controls.
- *Acceptance criteria:* A user without access to a restricted folder does not receive retrieval results sourced from that folder, verified by test.
- *Priority:* Must

#### 6.6 Auditability and Sovereignty Proofing

**FR-AS-1 — Append-only structured audit log**
- *Requirement:* Every agent step, tool invocation, model call, and file write shall be recorded in a structured, append-only local log including timestamp, user, model/tool identity, and input/output references.
- *Rationale:* Central to both operational debugging and compliance evidence.
- *Acceptance criteria:* Full audit trail for a demo workflow reconstructs the exact step sequence and inputs/outputs used, reviewable by an auditor with no system access beyond the log.
- *Priority:* Must

**FR-AS-2 — Tamper-evidence for audit logs**
- *Requirement:* Audit log entries shall be chained (e.g., hash-linked) so that retroactive modification or deletion of an entry is detectable.
- *Rationale:* An audit trail that can be silently edited provides no real compliance assurance.
- *Acceptance criteria:* Manually altering a historical log entry causes the chain-verification check to fail and flag the log as tampered.
- *Priority:* Must

**FR-AS-3 — Real-time network egress monitor**
- *Requirement:* The system shall provide a visible, running monitor of all network connection attempts made by any Workbench component, with an explicit allow/deny outcome per attempt.
- *Rationale:* Direct, observable proof of zero-egress operation, not just a policy statement.
- *Acceptance criteria:* During a full demo session, the monitor displays zero permitted external connections; any attempted external connection (simulated in test) is shown as denied and logged.
- *Priority:* Must

**FR-AS-4 — Default-deny network policy enforcement**
- *Requirement:* The host/container network configuration shall default to deny-all outbound traffic except explicitly declared localhost/intranet paths required for UI/API access.
- *Rationale:* Enforces air-gap operation at the infrastructure layer, independent of application-level correctness.
- *Acceptance criteria:* `iptables`/eBPF ruleset review confirms no outbound allow rules beyond the declared intranet scope; attempted external DNS/HTTP calls fail.
- *Priority:* Must

**FR-AS-5 — Signed model and binary attestation**
- *Requirement:* Model weights and critical deployment binaries/scripts shall be checksummed and signed at packaging time, with signature verification performed at install and at each service start.
- *Rationale:* Guards against tampered or substituted model files being introduced into an air-gapped environment where online reputation checks are unavailable.
- *Acceptance criteria:* Startup fails closed (service does not start) if a model file's signature/checksum does not match its manifest.
- *Priority:* Must

**FR-AS-6 — Output-to-source traceability**
- *Requirement:* Every generated deliverable shall carry (in its metadata or an accompanying manifest) references to the specific model(s), tool(s), and source document(s) used to produce it.
- *Rationale:* Supports both internal audit and any future external inspection of AI-assisted official documents.
- *Acceptance criteria:* Given any deliverable file in `/local/output`, the audit log can produce the full model/tool/source-document lineage for it.
- *Priority:* Must

#### 6.7 UI / CLI / SDK Requirements

**FR-UI-1 — Guided step-by-step demo mode**
- *Requirement:* The web UI shall offer a guided mode that walks a non-expert user through each of the three MVP demo workflows with clear step indicators.
- *Rationale:* Supports the usability success metric for non-expert users.
- *Acceptance criteria:* A first-time user completes a guided workflow unassisted within the target time in usability testing.
- *Priority:* Must

**FR-UI-2 — Localhost/intranet-only web UI**
- *Requirement:* The web UI shall bind only to localhost or a designated intranet interface, with no default exposure to any external-facing network.
- *Rationale:* Enforces air-gap posture at the presentation layer.
- *Acceptance criteria:* Port-scan from outside the isolated network segment shows the UI port unreachable.
- *Priority:* Must

**FR-UI-3 — CLI for install, model, and task management**
- *Requirement:* A CLI shall support installation, model registration/listing, task submission, and audit-log export.
- *Rationale:* Power users and administrators need scriptable, repeatable operations.
- *Acceptance criteria:* All three demo workflows can be triggered end-to-end via CLI commands alone, without the web UI.
- *Priority:* Must

**FR-UI-4 — Python SDK for programmatic access**
- *Requirement:* A minimal Python SDK shall expose task submission, status polling, and result/artifact retrieval.
- *Rationale:* Enables integration into existing internal tools and batch workflows.
- *Acceptance criteria:* A sample script using only the SDK submits UC-3 (coding task) and retrieves the resulting code and test log.
- *Priority:* Should

**FR-UI-5 — Role-appropriate view filtering**
- *Requirement:* The UI/CLI/SDK shall present only the actions and data a given RBAC role is permitted to perform/see (e.g., Auditor role sees logs but cannot submit tasks).
- *Rationale:* RBAC must be enforced consistently across all access surfaces, not only the API layer.
- *Acceptance criteria:* An Auditor-role session has no visible or callable task-submission action, verified by UI inspection and API-level test.
- *Priority:* Must

---

### 7. Non-Functional Requirements

**Security**
- NFR-SEC-1 (Must): No component shall include compiled-in telemetry, crash-reporting, or update-check network calls; verified by static binary/network analysis prior to release.
- NFR-SEC-2 (Must): All data at rest (model store, vector DB, audit logs, generated deliverables) shall be encrypted using an industry-standard algorithm (e.g., AES-256), with key material protected by OS-level or optional TPM/HSM storage.
- NFR-SEC-3 (Must): RBAC shall follow least-privilege defaults; new roles have no permissions until explicitly granted.
- NFR-SEC-4 (Should): Secure boot and signed-binary verification shall be supported for the host OS and critical services on hardware that provides the capability.
- NFR-SEC-5 (Should): All inter-service communication on the host shall use authenticated local sockets or mutually authenticated localhost TLS, not unauthenticated plaintext.

**Performance**
- NFR-PERF-1 (Must): Text summarization/drafting tasks shall complete within 30 seconds (P95) on the documented reference GPU.
- NFR-PERF-2 (Must): Moderate-length multimodal tasks shall complete within 2 minutes (P95) on the documented reference GPU.
- NFR-PERF-3 (Should): The system shall degrade gracefully (queue, or auto-select a smaller/quantized model) rather than fail outright when GPU resources are saturated.
- NFR-PERF-4 (Could): Batch/offline processing mode shall be available for bulk document sets where interactive latency is not required.

**Scalability**
- NFR-SCALE-1 (Must, MVP): The system shall operate correctly on a single-node, single-GPU deployment.
- NFR-SCALE-2 (Should, Beta+): The architecture shall support scaling to multiple GPUs within one node via sharded/parallel model loading, without redesign of the orchestrator.
- NFR-SCALE-3 (Could, GA): The architecture shall allow future multi-node deployment for larger sites, as an additive capability.

**Maintainability**
- NFR-MAINT-1 (Must): Adding a new model or tool shall require only configuration/manifest changes, per FR-MM-1 and FR-AO-2.
- NFR-MAINT-2 (Should): All services shall expose structured local logs (not only the audit log) sufficient for operational troubleshooting without external log shipping.
- NFR-MAINT-3 (Should): Patch/update packages shall be deliverable via offline media (signed update bundles) given the air-gapped environment.

**Compatibility**
- NFR-COMPAT-1 (Must): The system shall install and run on a specified Ubuntu LTS release with a defined minimum kernel/driver version.
- NFR-COMPAT-2 (Should): Generated Office documents shall be compatible with both Microsoft Office and common open-source viewers (LibreOffice) without formatting loss.
- NFR-COMPAT-3 (Could): The system shall support both NVIDIA (CUDA) and, where feasible, AMD (ROCm) GPUs to reduce hardware lock-in.

---

### 8. System Architecture

**8.1 Components**

1. **Orchestrator Service (air-gapped host process)** — central coordinator; receives requests from UI/CLI/SDK, invokes the Agent Runtime, enforces RBAC, and writes to the Audit Logger.
2. **Model Manager** — maintains the model catalog and manifests; loads/unloads/quantizes models via adapters; performs GPU-memory-aware scheduling; exposes a uniform generate/embed/vision-infer interface.
3. **Agent Runtime** — Planner (task decomposition), Executor (step execution), Tool Registry (declared tool schemas), Execution Sandbox (isolated code execution), Session State store.
4. **Tooling Layer** — OCR/handwriting pipeline; Document Indexer/local vector database; Code Sandbox (containerized, resource-limited, no network namespace); Spreadsheet engine; Office File Generator (Word/PPT/Excel).
5. **Security & Infrastructure Layer** — RBAC/Auth service; Audit Logger (append-only, hash-chained); Network Monitor (egress visibility/enforcement); optional TPM/HSM integration for key storage.
6. **User Interfaces** — Web UI (localhost/intranet only), CLI, Python SDK.
7. **Local Model & Data Store** — on-disk model weights (checksummed/signed), vector database, audit log store, generated-output directory (`/local/output`).

**8.2 Data Flow (textual) — Demo Workflow A: Scanned Inspection Report → Approval Note**

1. User uploads scanned report via Web UI → Orchestrator receives file, assigns task ID, RBAC check passes.
2. Orchestrator invokes Tooling Layer's OCR/vision pipeline on the file (local, no network) → normalized multimodal document representation produced (FR-MI-4) with page/region references.
3. Agent Runtime's Planner decomposes task into: [extract findings] → [draft note] → [export] steps.
4. Model Manager routes the "extract findings" step to the text/reasoning model; findings are extracted with citations to source regions.
5. Planner invokes the "draft note" step; the drafting model produces approval-note text using the extracted findings and a template retrieved from local storage.
6. If the approval-gate role setting is active, the draft is held for human review (FR-AO-6).
7. On approval, the Office File Generator tool renders the `.docx` file to `/local/output`.
8. Audit Logger records each step (1–7) with timestamps, model/tool identities, and source references; Network Monitor confirms zero outbound connections throughout.

**8.3 Data Flow (textual) — Demo Workflow B: Coding Task with Sandbox Execution**

1. User submits a code request via CLI/UI.
2. Planner decomposes into [generate code] → [execute in sandbox] → [evaluate result] → [fix if needed] → [finalize].
3. Model Manager routes generation to the code-capable model.
4. Execution Sandbox runs the generated script against supplied sample data with no network namespace, bounded CPU/memory/time (FR-AO-3).
5. On failure, Planner loops back to generation with the error context (bounded iterations, FR-AO-5).
6. On success, source file and execution log are written to `/local/output` (FR-DG-4).
7. Audit Logger records the full generate→execute→(fix)→finalize chain.

**8.4 Data Flow (textual) — Demo Workflow C: Image/Drawing Understanding**

1. User uploads an image/drawing (or two revisions) via UI.
2. Vision model (via Model Manager) analyzes the image(s) locally, producing structured element descriptions.
3. For revision comparison, a diffing step identifies changed elements and the Office/File Generator produces an annotated overlay image and a text summary.
4. Audit Logger records model identity, input image references, and output artifact locations.

**8.5 Deployment Topology (single-server demo)**

- One physical/virtual Ubuntu LTS server with one mid-range GPU, isolated on a network segment with no route to the public internet (air-gapped or logically isolated intranet).
- All Workbench services run as containers or systemd units under a host firewall/network-namespace configuration that defaults to deny-all outbound traffic; only localhost/intranet ports required for the Web UI/API are open.
- Model weights, vector database, audit logs, and generated outputs are stored on local encrypted disk volumes.
- No DNS resolution beyond localhost is configured; the Network Monitor runs continuously as a host-level process independent of the application containers, so it can observe egress attempts even if an application component is compromised.
- Administrative access (install, patch, model updates) occurs via physically present media (USB/offline package) or a separately controlled maintenance network segment, never via the same path used for day-to-day operation.

```
                  ┌───────────────────────────────────────────────┐
                  │        Isolated / Air-Gapped Network           │
                  │                                                 │
   [Intranet UI]──┼──► Web UI / CLI / SDK                           │
                  │        │                                        │
                  │        ▼                                        │
                  │   Orchestrator ──► RBAC/Auth ──► Audit Logger    │
                  │        │                              ▲         │
                  │        ▼                              │         │
                  │   Agent Runtime (Planner/Executor) ────┘         │
                  │        │        │            │                  │
                  │        ▼        ▼            ▼                  │
                  │   Model Mgr   Tool Registry  Session State       │
                  │   (Adapters)   │  │   │                          │
                  │        │       │  │   │                          │
                  │        ▼       ▼  ▼   ▼                          │
                  │   Local Models  OCR  Sandbox  Spreadsheet/Office │
                  │   & Vector DB                  Generator         │
                  │                                                 │
                  │   Network Monitor (host-level, always-on) ──────┼──X── (no external route)
                  └───────────────────────────────────────────────┘
```

---

### 9. Integration Points and Extensibility

**Adding a new model:** package weights with a manifest (capability tags, VRAM requirement, quantization options, checksum/signature) → place in the local model store → register via CLI/UI → Model Manager loads it through the standard adapter interface. No orchestrator or agent-runtime code changes required (FR-MM-1, FR-MM-4).

**Adding a new tool:** define a tool schema (name, description, input/output types, sandbox/permission requirements) → register with the Tool Registry → the Planner can select it once registered (FR-AO-2). Example future tools: CAD-viewer parser, ERP read-only connector, ticketing-system connector.

**Connectors to internal document stores:** read-only connector interface for common on-prem repositories (SMB/file shares, on-prem SharePoint, existing DMS). Each connector respects the source system's existing access controls and surfaces them to the Access-Scoped Retrieval requirement (FR-KB-4). Initial MVP ships with a local-folder connector; additional connectors are a Beta-phase item.

**Identity/RBAC integration:** MVP ships with a local user/role store; Beta phase adds integration with on-prem directory services (e.g., AD/LDAP) as an optional identity backend, without changing the RBAC enforcement points already built into the Orchestrator and UI/CLI/SDK layers.

---

### 10. Data Security and Compliance

- **Air-gapped operation:** Default-deny outbound network policy enforced at the host/container level (FR-AS-4); continuous egress monitoring independent of application code (FR-AS-3).
- **RBAC:** Least-privilege role model (Admin, Standard User, Approver, Auditor/read-only) enforced consistently across UI, CLI, SDK, and API layers (FR-UI-5).
- **Encryption at rest:** Model store, vector database, audit logs, and generated deliverables encrypted (AES-256 or equivalent); key material protected by OS keystore or optional TPM/HSM.
- **Secure model binaries:** Signature/checksum verification of model weights and critical binaries at install and service start; fail-closed on mismatch (FR-AS-5).
- **Supply chain checks:** A software bill of materials (SBOM) shall be produced for every release; all third-party components and open-weight model packages shall be vulnerability-scanned and provenance-checked at packaging time, before they ever reach an air-gapped site (since the site itself cannot pull live vulnerability feeds).
- **Session isolation:** Each user session's working data and sandbox execution shall be isolated from other concurrent sessions.
- **Data residency:** All generated artifacts are written only to designated local output paths; no component shall write user data outside the local storage volumes.
- **Physical security assumption:** The Workbench provides software-level enforcement and verification of data sovereignty; physical security and network isolation of the hosting facility remain the customer's responsibility (see Open Questions/Assumptions).

---

### 11. Implementation Plan and Roadmap

Assumptions: team of 3–6 engineers (covering backend/orchestration, ML/model integration, frontend, security/infra, and QA), one mid-range GPU server available throughout for development and demo.

| Phase | Duration | Weeks | Key Milestones |
|---|---|---|---|
| **Phase 0 — Prototype** | 4 weeks | W1–W4 | Single model wired into a basic chat UI; local file upload; no agent loop yet; network-deny policy scaffolded from day one. |
| **Phase 1 — MVP** | 10 weeks | W5–W14 | Model Manager with 2 models (text + vision/OCR); Agent Runtime with planner/executor and 5 core tools; all 3 demo workflows (A, B, C) working end-to-end; audit logger; network monitor; baseline RBAC (3 roles); CLI + guided web UI. |
| **Phase 2 — Beta** | 10 weeks | W15–W24 | Additional model(s) onboarded via adapter config (validates extensibility metric); multi-GPU/sharding support; document-store connectors beyond local folder; AD/LDAP identity integration; hardened security (TPM/HSM optional path, secure boot support); SDK maturation; pilot deployment at 1–2 reference sites. |
| **Phase 3 — GA** | 12 weeks | W25–W36 | SBOM and supply-chain documentation finalized; certification-readiness package assembled (e.g., for CERT-In/STQC/defence empanelment as applicable); performance/scale hardening; installer and offline-update packaging polish; full documentation and training materials; support/patch process defined for air-gapped sites. |

Total estimated timeline: **~36 weeks (≈9 months)** from prototype start to GA readiness, with the MVP demo achievable by end of **Week 14**.

---

### 12. Demo Plan and Acceptance Criteria

**Pre-conditions for all demos:** Reference hardware provisioned and isolated on a network segment with no route to the public internet; Network Monitor running and visible on a secondary screen/log tail for the full session; audit log export ready.

**Demo A — Inspection Report → Approval Note**
1. Upload a sample scanned/handwritten inspection report.
2. Trigger the guided "Approval Note" workflow.
3. Review and approve the drafted note.
4. Export to Word.

*Acceptance criteria:* A `.docx` file with the extracted findings is generated and saved to `/local/output`; the audit log shows the ingest → extract → draft → approve → export step sequence with source-region citations for each finding; the network monitor shows zero outbound connections for the full session; total session time meets the <2-minute multimodal latency target for the extraction/drafting steps combined.

**Demo B — Coding Task with Sandbox Execution**
1. Submit a code request with an accompanying sample data file.
2. Allow the agent to generate, execute, and (if needed) self-correct the script.
3. Present the final code and results.

*Acceptance criteria:* Source file and execution/test log are both present in `/local/output`; the audit log shows at least one full generate→execute cycle (and, if a seeded bug is used for the demo, at least one fix→re-run cycle); the sandbox log shows no network namespace access was available to the executed code; network monitor shows zero outbound connections.

**Demo C — Multimodal Image/Drawing Analysis**
1. Upload two revisions of a sample drawing.
2. Trigger the revision-comparison workflow.
3. Present the annotated overlay and change summary.

*Acceptance criteria:* An annotated image file and a text change-summary document are generated and saved to `/local/output`; the audit log records the vision model used and the two source image references; the sample set of intentionally introduced differences is correctly identified; network monitor shows zero outbound connections.

**Cross-cutting verification (run once for the full combined session):**
- Network monitor log (iptables counters or eBPF capture) reviewed live, showing an outbound-attempt count of zero for the session.
- Audit log exported and independently reviewed by a non-presenter (acting as auditor) to confirm every generated deliverable can be traced to its source documents and models used.
- RBAC test: an Auditor-role account is shown to view the audit log but cannot submit a new task.
- Model swap test: a second, previously unregistered small open-weight model is added via CLI using only a manifest file, and successfully used to complete a simple summarization task, timed to confirm the <1-engineer-day extensibility target is plausible in production (for the demo, this is shown as "config-only, no code change," not a full day's exercise).

---

### 13. Risks and Mitigations

| Risk | Category | Mitigation |
|---|---|---|
| Mid-range GPU VRAM insufficient for target model sizes | Technical | Support quantization/sharding (FR-MM-5); document a minimum-viable smaller-model fallback path (FR-MM-2/PERF-3). |
| Open-weight model hallucination in numeric/engineering results | Technical/Safety | Route all numeric computation through deterministic sandboxed tools, never free-text LLM arithmetic (FR-DG-5); mandatory human approval gate for critical deliverables (FR-AO-6). |
| Base container/OS images contain hidden telemetry or update-check calls | Security | Build from vetted minimal base images; disable all telemetry flags; verify via network capture as part of the release CI pipeline (NFR-SEC-1). |
| Code-execution sandbox escape | Security | Use strong isolation (e.g., microVM/gVisor-class sandboxing), no network namespace access, strict syscall/resource limits (FR-AO-3). |
| Tampered or backdoored open-weight model weights introduced into an air-gapped site | Security/Supply chain | Checksum/signature verification at packaging, install, and runtime start (FR-AS-5); scan model packages for embedded executable payloads before release. |
| RBAC misconfiguration exposing sensitive documents/actions | Security | Default-deny role model; automated RBAC test suite run on every release (NFR-SEC-3, FR-KB-4). |
| User distrust of AI-drafted content in regulated/government workflows | Adoption | Full citation-to-source for every claim (FR-KB-2, FR-MI-4); mandatory human review/approval before finalization; structured training/rollout program. |
| Latency degradation under GPU contention with larger models | Performance | Auto-selection favors smaller/quantized models under load; graceful degradation rather than failure (NFR-PERF-3). |
| Architecture becomes implicitly coupled to one model family over time | Technical/Extensibility | Keep prompt/response handling in the adapter layer, not hardcoded in the orchestrator; validate extensibility with a real second-model onboarding each release (FR-MM-1). |
| Customer site hardware below reference GPU spec | Adoption/Technical | Publish a clear minimum hardware bar; document a CPU-fallback path for lightweight tasks. |
| Air-gapped sites cannot receive live security patches/model updates | Security/Maintainability | Offline, signed update-bundle mechanism (NFR-MAINT-3); documented periodic manual patch cycle. |

---

### 14. Open Questions and Assumptions

1. Which open-weight model families are pre-approved for use in defence-linked environments, given potential provenance/export-control review requirements?
2. What identity backend(s) already exist at target customer sites (on-prem AD/LDAP, other) that RBAC must integrate with in Beta/GA?
3. What disk footprint is acceptable for the local model store, given multiple models at tens of gigabytes each?
4. Should the human-approval gate before deliverable finalization be mandatory for all roles, or configurable per role/deployment?
5. What OCR/vision model licensing terms are acceptable in export-controlled or defence-linked contexts?
6. Is a single mid-range discrete GPU (e.g., a 24 GB-class card) the right MVP hardware baseline, or should the MVP also validate a CPU-only path for widest deployability across older sites?
7. What formal certification or empanelment (e.g., CERT-In, STQC, defence vendor empanelment) is required for GA, and does that impose architectural constraints not yet captured here?
8. **Assumption:** The customer is responsible for physical security and network isolation of the hosting facility; the Workbench provides software-level enforcement and verification of sovereignty, not physical security.
9. **Assumption:** The MVP and Beta phases target single-node deployment only; multi-node/distributed clustering is deferred to GA or later.
10. **Assumption:** "Air-gapped" for MVP purposes includes logically isolated intranet deployments with a verifiably enforced default-deny egress policy, not exclusively physically disconnected hardware; this should be confirmed with security stakeholders as a defined term for the product.

---

### 15. Appendices

#### Appendix A — Example CLI/API Commands (illustrative)

```bash
# Install (single-server, Ubuntu LTS, GPU pre-flight check included)
./install-workbench.sh --gpu auto --data-dir /srv/workbench --enforce-air-gap

# List registered models
workbench model list

# Add a new open-weight model (manifest-driven, no code change)
workbench model add --manifest ./models/new-model-manifest.yaml

# Submit a task via CLI (Demo A)
workbench task submit --workflow approval-note --input ./samples/inspection_scan.pdf

# Submit a coding task via CLI (Demo B)
workbench task submit --workflow code-task --prompt "parse historian CSV, flag out-of-range readings" --sample-data ./samples/historian_sample.csv

# Export the audit log for a session
workbench audit export --session <session-id> --out ./audit/session_export.json

# Check current network egress status
workbench netmon status
```

#### Appendix B — Example Log Entries and Network-Monitor Checks (illustrative)

Example audit log entry (hash-chained, append-only):

```json
{
  "seq": 4821,
  "prev_hash": "b3f0...9ac1",
  "hash": "e19d...44f0",
  "timestamp": "2026-09-08T10:14:32Z",
  "session_id": "sess-7f2a",
  "user": "engineer.rao",
  "action": "tool_invoke",
  "tool": "office_generator.docx",
  "model_used": "text-reasoner-7b-q4",
  "source_documents": ["scan-2026-0908-114", "template-approval-note-v3"],
  "output_artifact": "/local/output/approval_note_2026-09-08.docx",
  "approval_status": "approved_by:supervisor.k"
}
```

Example network-monitor check (host-level egress capture summary):

```
Session window: 2026-09-08T10:10:00Z – 2026-09-08T10:22:00Z
Outbound connection attempts observed: 0
DNS resolution attempts (non-localhost): 0
Denied-by-default-policy events: 0
Interfaces monitored: eth0 (intranet, allowed: 10.20.0.0/24 UI/API only), lo
Result: PASS — zero external network activity for session
```

#### Appendix C — Minimal Hardware/Software Bill of Materials (MVP Demo)

| Component | Minimum Spec (MVP demo) |
|---|---|
| OS | Ubuntu 22.04 LTS (or later LTS), air-gapped/isolated network segment |
| GPU | One mid-range discrete GPU, 24 GB VRAM class (e.g., consumer/prosumer tier), CUDA-capable |
| CPU | 8+ cores, modern x86_64 |
| RAM | 64 GB system memory |
| Disk | 1 TB SSD (model store + vector DB + logs + generated output headroom) |
| Container runtime | Docker or Podman with rootless/isolated networking support |
| Model 1 (text/reasoning) | One mid-size open-weight instruction/reasoning model, quantized variant sized to fit reference GPU VRAM budget |
| Model 2 (vision/OCR) | One open-weight vision/OCR-capable model for scanned-document and image understanding |
| Sandbox isolation | Container/microVM-based isolation with no network namespace access and enforced CPU/memory/time limits |
| Network monitor | Host-level iptables counters or eBPF-based capture tool, independent of application containers |

---

### Launch Demo Checklist

**Steps to run (in order):**
1. Confirm reference server is on the isolated network segment; start the Network Monitor and leave it visible.
2. Start Workbench services; confirm all three roles (Admin, Standard User, Auditor) are provisioned.
3. Run Demo A: upload scanned inspection report → guided approval-note workflow → review/approve → export `.docx`.
4. Run Demo B: submit coding task with sample data → observe generate/execute/(fix)/finalize cycle → confirm `.docx`/code + log output.
5. Run Demo C: upload two drawing revisions → run comparison workflow → produce annotated image + change summary.
6. Add a second, previously unregistered small model via CLI using only a manifest file; run a simple summarization task on it.
7. Log in as the Auditor role; confirm the audit log is viewable and task submission is unavailable.
8. Export the full session audit log and network-monitor summary.

**Verifiable artifacts to present:**
- `.docx` approval note (Demo A) with findings table.
- `.xlsx` calc sheet or code + execution log and test results (Demo B).
- Annotated image + change-summary document (Demo C).
- Full session audit log export, hash-chain-verified.
- Network-monitor session summary showing zero external connection attempts.
- CLI transcript of the config-only model add-on (extensibility proof).
- RBAC test result showing Auditor-role restriction enforced.

