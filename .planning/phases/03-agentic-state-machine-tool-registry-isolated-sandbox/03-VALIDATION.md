---
phase: "03"
slug: "agentic-state-machine-tool-registry-isolated-sandbox"
status: draft
nyquist_compliant: true
wave_0_complete: false
created: "2026-09-10"
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|:---|:---|
| **Framework** | pytest 9.1.1 (Python 3.11) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest -v tests/test_orchestration/ tests/test_tools/ tests/test_sandbox/` |
| **Full suite command** | `pytest -v` |
| **Estimated runtime** | ~8 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command for affected module (`pytest -v tests/test_orchestration/...`)
- **After every plan wave:** Run `pytest -v tests/test_orchestration/ tests/test_tools/ tests/test_sandbox/`
- **Before Phase 3 completion:** Full suite (`pytest -v`) must be green (all 106 Phase 1 & 2 tests + all Phase 3 tests)
- **Max feedback latency:** 8 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| `03-01-01` | 01 | 1 | ORCH-01, ORCH-03 | — | StateGraph executes multi-step nodes, loops, and self-corrects up to 3 times | unit | `pytest -v tests/test_orchestration/test_state_graph.py` | ❌ W0 | ⬜ pending |
| `03-01-02` | 01 | 1 | ORCH-02 | T-03-04 | SQLite checkpointer stores thread state in WAL mode and restores across sessions | integration | `pytest -v tests/test_orchestration/test_checkpointer.py` | ❌ W0 | ⬜ pending |
| `03-01-03` | 01 | 1 | ORCH-04 | — | `interrupt()` suspends execution and `resume()` continues graph traversal | integration | `pytest -v tests/test_orchestration/test_hitl_interrupt.py` | ❌ W0 | ⬜ pending |
| `03-02-01` | 02 | 2 | TOOL-01 | T-03-04 | ToolRegistry enforces strict JSON Schema and RBAC role clearances | unit | `pytest -v tests/test_tools/test_tool_registry.py` | ❌ W0 | ⬜ pending |
| `03-02-02` | 02 | 2 | TOOL-03 | T-03-04 | Built-in tools enforce workspace path fencing and safe AST calculations | unit | `pytest -v tests/test_tools/test_builtin_tools.py` | ❌ W0 | ⬜ pending |
| `03-03-01` | 03 | 3 | TOOL-02 | T-03-01, T-03-02 | CodeSandbox enforces execution timeouts, resource limits, and network block | integration | `pytest -v tests/test_sandbox/test_code_sandbox.py` | ❌ W0 | ⬜ pending |
| `03-03-02` | 03 | 3 | ORCH-01, TOOL-01 | — | CLI commands `sovereign workflow` and `sovereign tool` work end-to-end | cli | `pytest -v tests/test_orchestration/test_workflow_cli.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/sovereign/orchestration/`: Directory structure for StateGraph runtime and checkpointer
- [ ] `src/sovereign/tools/`: Directory structure for ToolRegistry and built-in tools
- [ ] `src/sovereign/sandbox/`: Directory structure for CodeSandbox
- [ ] `tests/test_orchestration/`, `tests/test_tools/`, `tests/test_sandbox/`: Test directories and fixtures

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all package structures and test suites
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-09-10
