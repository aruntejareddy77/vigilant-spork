# Phase 3: Agentic State Machine, Tool Registry & Isolated Sandbox - Context

**Gathered:** 2026-09-10  
**Status:** Ready for planning  

<domain>
## Phase Boundary

Phase 3 delivers the sovereign agentic orchestration runtime, explicit tool execution registry, and isolated code sandbox:
1. Multi-step LangGraph-style state machine runtime (`StateGraph`) with sequential tool and model invocations.
2. Persistent session state across multi-turn iterations (`agent_state.sqlite`).
3. Bounded self-correction loop (default max 3 attempts) for tool/code execution failures.
4. Human-in-the-Loop (HITL) approval gate (`interrupt()`) pausing graph traversal before critical/final actions and resuming on confirmation.
5. Rigid JSON Schema Tool Registry with role-based access control (Admin, Engineer, Auditor) and filesystem fencing.
6. Isolated code execution sandbox enforcing zero outbound network egress, CPU/memory limits, and execution timeouts across Linux (production) and Windows (local development).
</domain>

<decisions>
## Implementation Decisions

### 1. State Machine & Persistence Architecture
- **D-28:** Native self-contained StateGraph engine (nodes, conditional transitions, state schema, and SQLite WAL checkpointer) matching LangGraph semantics with zero heavy external framework bloat.
  — **Reversibility:** costly — The agent runtime state machine is the core execution loop for all downstream workflows (Refinery, PSU, Defense).
- **D-29:** Persistent SQLite WAL database (`agent_state.sqlite`) storing thread state, node transitions, checkpoints, and payload snapshots with atomic rollback/resume.
  — **Reversibility:** reversible — Standard schema migration path.

### 2. Sandboxed Code Execution Environment
- **D-30:** Multi-tier sandbox engine: Linux network namespace (`unshare -n` / drop capabilities / cgroups v2) in production Linux, with subprocess restricted sandbox (no network sockets, timeout termination, memory/CPU bounding, and restricted workspace temp dir) for Windows local dev & CI.
  — **Reversibility:** costly — Core security containment boundary protecting host server from untrusted generated scripts.

### 3. Human-in-the-Loop (HITL) Approval Gate
- **D-31:** Asynchronous `interrupt(payload)` pausing graph execution, persisting frozen state to SQLite, emitting an `APPROVAL_REQUIRED` audit event to `AuditLedger`, and exposing `sovereign workflow approve/reject <thread_id>` API and CLI commands to resume execution.
  — **Reversibility:** costly — Defines the human verification contract for plant engineers and regulatory approvals.

### 4. Tool Registry Architecture & Execution Safety
- **D-32:** Rigid JSON Schema Tool Registry with declared RBAC role clearance (Admin, Engineer, Auditor) and workspace filesystem path fencing (preventing path traversal outside approved directories).
  — **Reversibility:** costly — Affects how all built-in and dynamic tools are declared and invoked.
- **D-33:** Built-in tools implemented:
  - File operations: `read_file`, `write_file`, `list_directory` (fenced to workspace).
  - Structured document parsing: `parse_table`, `extract_text`.
  - Engineering calculation: `execute_calculation` with auditable formula traces.

### 5. Self-Correction & Retry Governance
- **D-34:** Bounded iterative reflection loop (default max 3 retries): runtime error tracebacks are injected into model prompt context with corrective instructions. If retries are exhausted, the graph halts and transitions to `ERROR_ESCALATION` requiring human review.
  — **Reversibility:** reversible — Configurable retry limits and prompt formatting.

### Antigravity's Discretion
- Specific schema design for thread checkpoints and node transitions.
- Internal IPC mechanisms for the subprocess sandbox on Windows.
- CLI formatting and color scheme for the `sovereign workflow` and `sovereign tool` commands.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product & Technical Requirements
- `Sovereign_AI_Workbench_PRD.md` §6.2 — Agent Orchestration and Tools (FR-AO-1 through FR-AO-6).
- `Air-Gapped Industrial AI Workbench.md` §10 — The Agentic State Machine (LangGraph deterministic state transitions, interrupt() paradigm).
- `Air-Gapped Industrial AI Workbench.md` §11 — Tool Orchestration and Document Generation (Explicit Tool Schemas, Tool Registry).
- `Air-Gapped Industrial AI Workbench.md` §12 — The Secure Code Sandbox (Network Namespaces, Zero-Egress, Resource Bounding, MicroVM/Process isolation).

### Prior Phase Deliverables & Contracts
- `.planning/phases/01-sovereign-foundation-cryptographic-audit-network-egress-moni/01-01-SUMMARY.md` — `AuditLedger` for logging graph transitions, tool invocations, and approval gates.
- `.planning/phases/01-sovereign-foundation-cryptographic-audit-network-egress-moni/01-02-SUMMARY.md` — `NetworkPolicyEngine` enforcing 0 outbound packets.
- `.planning/phases/02-local-model-management-adapters-vram-scheduler/02-01-SUMMARY.md` — `ModelRegistry` catalog.
- `.planning/phases/02-local-model-management-adapters-vram-scheduler/02-02-SUMMARY.md` — `BaseModelAdapter` and `MockModelAdapter` for multi-modal inference.
- `.planning/phases/02-local-model-management-adapters-vram-scheduler/02-03-SUMMARY.md` — `TaskRouter` and `VRAMScheduler`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/sovereign/audit/ledger.py`: `AuditLedger` to record `AGENT_NODE_ENTER`, `AGENT_NODE_EXIT`, `TOOL_INVOKED`, `APPROVAL_REQUIRED`, `APPROVAL_GRANTED`, and `SELF_CORRECTION_ATTEMPT`.
- `src/sovereign/models/registry.py` & `src/sovereign/models/scheduler.py`: Invocable by the state machine to route model requests and ensure loaded weights.
- `src/sovereign/models/types.py`: `ChatMessage` and `ModelResponse` for agent thought traces.

### Established Patterns
- Pydantic models for all declarative schemas and validation.
- Standard library preference (`urllib`, `sqlite3`, `threading`, `json`, `subprocess`) for air-gapped zero-dependency robustness.
- Strict loopback and local resource isolation.
- Click CLI commands under `sovereign`.

### Integration Points
- `src/sovereign/orchestration/`: New package for `StateGraph`, `checkpointer.py`, `runtime.py`.
- `src/sovereign/tools/`: New package for `registry.py`, `schemas.py`, `builtin/`.
- `src/sovereign/sandbox/`: New package for `executor.py`, `process.py`, `limits.py`.
- `src/sovereign/cli.py`: Extended with `sovereign workflow` and `sovereign tool`.

</code_context>

<specifics>
## Specific Ideas
- The `StateGraph` should allow defining nodes as Python callables taking state and returning state updates, with conditional routing edges evaluating state predicates (e.g. `has_errors -> retry`, `needs_approval -> interrupt`, `ready -> finalize`).
- The `interrupt(payload)` function should raise a special `GraphInterrupt` exception that the engine catches, causing it to checkpoint state as `SUSPENDED` and pause execution cleanly.
- Sandboxed code execution must create a clean ephemeral directory per run and delete it immediately after capture.

</specifics>

<deferred>
## Deferred Ideas
- Distributed multi-node task queues (Redis/Celery) — deferred to GA/Beta.
- MicroVM Firecracker virtualization — deferred to Phase 6 / hardware hardening.
- Real-time collaborative multi-user editing — deferred to future milestone.

</deferred>

---

*Phase: 03-Agentic State Machine, Tool Registry & Isolated Sandbox*  
*Context gathered: 2026-09-10*
