---
phase: "06"
slug: "sih-end-to-end-demonstration-workflows-verification"
status: draft
nyquist_compliant: true
wave_0_complete: false
created: "2026-09-14"
---

# Phase 06 — Validation Strategy: SIH End-to-End Demonstration Workflows & Verification

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|:---|:---|
| **Framework** | pytest 9.1.1 (Python 3.11) + FastAPI TestClient + SovereignClient SDK |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest -v tests/test_demos/` |
| **Full suite command** | `pytest -v` |
| **Estimated runtime** | ~18 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command for affected demo module (`pytest -v tests/test_demos/test_...py`)
- **After every plan wave:** Run `pytest -v tests/test_demos/`
- **Before Phase 6 completion:** Full suite (`pytest -v`) must be green (all previous 377 tests + all Phase 6 tests)
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| `06-01-01` | 01 | 1 | DEMO-01, DEMO-02, DEMO-03 | — | Programmatic asset generator produces high-resolution inspection scan, historian CSV with anomalies, and dual-revision P&ID drawings | unit | `pytest -v tests/test_demos/test_sample_assets.py` | ❌ W0 | ⬜ pending |
| `06-01-02` | 01 | 1 | DEMO-01 | T-06-01, T-06-03 | Demo A executes unassisted: OCR extraction, confidence thresholding (<0.85 review flag), HITL pause/approval, and styled Word (.docx) export with scan citations | integration | `pytest -v tests/test_demos/test_demo_a.py` | ❌ W0 | ⬜ pending |
| `06-01-03` | 01 | 1 | DEMO-02 | T-06-02, T-06-04 | Demo B executes unassisted: code generation, zero-network sandbox execution, seeded KeyError auto-fix recovery loop, runnable script and execution log export | integration | `pytest -v tests/test_demos/test_demo_b.py` | ❌ W0 | ⬜ pending |
| `06-01-04` | 01 | 1 | DEMO-03 | T-06-05 | Demo C executes unassisted: P&ID drawing revision comparison detects exactly 3 diff regions (added, removed, modified), visual overlay PNG, and change register table export | integration | `pytest -v tests/test_demos/test_demo_c.py` | ❌ W0 | ⬜ pending |
| `06-02-01` | 02 | 2 | SOVG-01..04, UI-05 | T-06-06, T-06-07 | Full cross-cutting session executes all 3 demos; proves 0 outbound network packets in NetworkMonitor, unbroken SHA-256 audit chain in verify_ledger(), and RBAC Auditor fencing | e2e | `pytest -v tests/test_demos/test_demo_e2e_session.py` | ❌ W0 | ⬜ pending |
| `06-02-02` | 02 | 2 | DEMO-01..03, UI-01..05 | — | Physical deliverable verification in output directory, CLI/SDK execution parity check, and comprehensive Judge Presentation Runbook (DEMO_RUNBOOK.md) | integration | `pytest -v tests/test_demos/` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Directory: `samples/` for deterministic demo assets
- [ ] Directory: `tests/test_demos/` for demo workflow test fixtures
- [ ] Script: `scripts/generate_sample_assets.py`
- [ ] Conftest fixture: `tests/test_demos/conftest.py` with mock server, client, and deliverable output folder
