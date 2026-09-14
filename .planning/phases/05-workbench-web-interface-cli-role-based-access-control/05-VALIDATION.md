---
phase: "05"
slug: "workbench-web-interface-cli-role-based-access-control"
status: draft
nyquist_compliant: true
wave_0_complete: false
created: "2026-09-14"
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|:---|:---|
| **Framework** | pytest 9.1.1 (Python 3.11) + httpx / fastapi TestClient |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest -v tests/test_server/ tests/test_cli/ tests/test_sdk/` |
| **Full suite command** | `pytest -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command for affected module (`pytest -v tests/test_server/...`)
- **After every plan wave:** Run `pytest -v tests/test_server/ tests/test_cli/ tests/test_sdk/`
- **Before Phase 5 completion:** Full suite (`pytest -v`) must be green (all previous 238 tests + all Phase 5 tests)
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| `05-01-01` | 01 | 1 | UI-02 | T-05-01, T-05-02 | Server startup binding guard halts with `BindingSecurityError` on `0.0.0.0`; Host header middleware drops spoofed external hosts | unit | `pytest -v tests/test_server/test_binding_security.py` | ❌ W0 | ⬜ pending |
| `05-01-02` | 01 | 1 | UI-05 | T-05-03, T-05-06 | 3-tier RBAC middleware returns HTTP 403 Forbidden when Auditor attempts task submission, and writes `SECURITY_ALERT_RBAC_VIOLATION` to audit ledger | unit | `pytest -v tests/test_server/test_rbac_middleware.py` | ❌ W0 | ⬜ pending |
| `05-01-03` | 01 | 1 | UI-01, UI-05 | T-05-05 | WebSocket streaming manager broadcasts real-time agent reasoning trace, network monitor telemetry, and HITL interrupts with valid JSON framing | unit | `pytest -v tests/test_server/test_websocket_streams.py` | ❌ W0 | ⬜ pending |
| `05-01-04` | 01 | 1 | UI-01, UI-02, UI-05 | T-05-04 | REST API routes expose tasks, models, network, audit, preview, and demo launch endpoints with strict input validation and role clearance | integration | `pytest -v tests/test_server/test_api_routes.py` | ❌ W0 | ⬜ pending |
| `05-02-01` | 02 | 2 | UI-01, UI-05 | T-05-01 | Static HTML/CSS/JS assets contain zero external CDN links (`http://`, `https://`), use system fonts and embedded SVGs for air-gap compliance | unit | `pytest -v tests/test_server/test_static_assets.py` | ❌ W0 | ⬜ pending |
| `05-02-02` | 02 | 2 | UI-01, UI-05 | — | Multi-pane UI components render agent reasoning trace, canvas bounding boxes, HITL approval cards, and dynamic role filtering (hiding tasks for Auditor) | unit | `pytest -v tests/test_server/test_ui_components.py` | ❌ W0 | ⬜ pending |
| `05-02-03` | 02 | 2 | UI-01 | — | Guided demo workflows (Demo A, Demo B, Demo C) transition through step cards, display live execution state, and deliver downloadable artifacts | integration | `pytest -v tests/test_server/test_demo_workflows.py` | ❌ W0 | ⬜ pending |
| `05-03-01` | 03 | 3 | UI-03, UI-05 | T-05-06 | Sovereign CLI commands (`serve`, `task submit/status/logs/approve/reject`, `model vram`) execute and enforce RBAC token/role checks | integration | `pytest -v tests/test_cli/test_workbench_cli.py` | ❌ W0 | ⬜ pending |
| `05-03-02` | 03 | 3 | UI-04, UI-05 | T-05-03 | Lightweight pure-Python SDK (`SovereignClient`) enables task submission, polling, artifact retrieval, and raises `RBACPermissionError` on Auditor task calls | integration | `pytest -v tests/test_sdk/test_sovereign_client.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Directory structure: `src/sovereign/server/` (`static/`, `routes/`, `auth/`, `ws/`)
- [ ] Directory structure: `src/sovereign/sdk/`
- [ ] Test directories: `tests/test_server/`, `tests/test_cli/`, `tests/test_sdk/`
- [ ] Shared fixtures: `tests/test_server/conftest.py` with FastAPI TestClient and mock runtime/ledger

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|:---|:---|:---|:---|
| Visual Inspection of Multi-Pane Layout | UI-01 | Visual alignment, color contrast, and font rendering in browser | Open `http://127.0.0.1:8000` in Chrome/Firefox; verify 4-pane layout, dark industrial aesthetic, and responsive canvas scaling |
| Guided Demo Mode Interactive Experience | UI-01 | Real-time human feel and interaction smoothness | Click "Guided Demo A", verify step-by-step progress cards, inspect rendered bounding boxes on document canvas, click "Approve" |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** verified 2026-09-14
