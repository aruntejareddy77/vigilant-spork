---
phase: "02"
slug: "local-model-management-adapters-vram-scheduler"
status: draft
nyquist_compliant: true
wave_0_complete: false
created: "2026-09-10"
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|:---|:---|
| **Framework** | pytest 9.1.1 (Python 3.11) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest -v tests/test_models/` |
| **Full suite command** | `pytest -v` |
| **Estimated runtime** | ~6 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command for the affected test file (`pytest -v tests/test_models/<target_test>.py`)
- **After every plan wave:** Run `pytest -v tests/test_models/`
- **Before Phase 2 completion:** Full suite (`pytest -v`) must be green (all 66 Phase 1 tests + all Phase 2 tests)
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| `02-01-01` | 01 | 1 | MODL-01 | T-02-01 | Validates manifest schema and rejects invalid YAML/JSON fields | unit | `pytest -v tests/test_models/test_model_manifest.py` | ❌ W0 | ⬜ pending |
| `02-01-02` | 01 | 1 | MODL-01 | T-02-01 | Hot-registers models and queries by capability without code edits | unit | `pytest -v tests/test_models/test_model_registry.py` | ❌ W0 | ⬜ pending |
| `02-02-01` | 02 | 2 | MODL-04 | — | Deterministic mock inference across text, chat, JSON, and embedding | unit | `pytest -v tests/test_models/test_mock_adapter.py` | ❌ W0 | ⬜ pending |
| `02-02-02` | 02 | 2 | MODL-01 | T-02-03 | Unified HTTP adapter handles local engine protocols and connection timeouts | integration | `pytest -v tests/test_models/test_local_adapters.py` | ❌ W0 | ⬜ pending |
| `02-03-01` | 03 | 3 | MODL-02 | — | Auto-routes task prompts by capability and honors manual `--model` override | unit | `pytest -v tests/test_models/test_task_router.py` | ❌ W0 | ⬜ pending |
| `02-03-02` | 03 | 3 | MODL-03 | T-02-02 | Tracks VRAM budget, evicts LRU models, and prevents OOM crashes | integration | `pytest -v tests/test_models/test_vram_scheduler.py` | ❌ W0 | ⬜ pending |
| `02-03-03` | 03 | 3 | MODL-01, MODL-02 | — | CLI commands `sovereign model list`, `register`, `route` work end-to-end | cli | `pytest -v tests/test_models/test_model_cli.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/fixtures/models/`: Sample model manifest YAMLs (`qwen_reasoning.yaml`, `qwen_coder.yaml`, `florence_vision.yaml`, `bge_embedding.yaml`)
- [ ] `tests/test_models/`: Test package directory with test stubs for plans 02-01, 02-02, and 02-03
- [ ] `src/sovereign/models/`: Source package directory for Phase 2 implementation

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all test fixtures and directory structures
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-09-10
