# Phase 5 Plan 05-03: Sovereign Workbench CLI & Lightweight Python SDK — Execution Summary

**Phase:** 05 — Workbench Web Interface, CLI & Role-Based Access Control  
**Plan:** 05-03 (Wave 3: Sovereign Workbench CLI & Lightweight Python SDK)  
**Status:** Completed  
**Execution Date:** 2026-09-14  
**Head Commits:**
- `5848ee5` — `feat(05-03): implement Sovereign CLI extensions for serve, task operations, and model vram`
- `fd94bea` — `feat(05-03): implement lightweight pure-Python SDK with modular namespaces and RBAC enforcement`

---

## 1. Executive Summary

Plan 05-03 delivered the command-line interface (CLI) extensions and zero-external-dependency Python client SDK (`sovereign.sdk`) for the Sovereign AI Workbench. Operators, automation engineers, and plant data scientists can now interact with the workbench either via the unified Click CLI or programmatically through a pure-Python library designed to execute deterministically on air-gapped industrial workstations without installing external pip packages.

Key operational milestones delivered:
1. **Server Lifecycle & Security Binding Guard:** `sovereign serve` integrates `validate_server_binding(host)`, strictly preventing accidental binding to `0.0.0.0`, `::`, or unauthorized public IPs (UI-02), and launching the Uvicorn ASGI server with configurable host, port, and worker options.
2. **Comprehensive Task CLI Operations:** `sovereign task` command group supporting `submit` (with `--stream`, `--model`, `--file`), `status`, `logs` (with `--follow`), `approve`, and `reject`. The Auditor role is fenced client-side, terminating immediately with exit code 1 and descriptive least-privilege error messages before any network traffic is emitted (UI-05).
3. **GPU VRAM Inspection:** `sovereign model vram` displays GPU budget envelopes, safety reserves (2GB), active allocations, usable headroom, and loaded models table with ASCII memory usage visualization.
4. **Pure Standard-Library Python SDK (`sovereign.sdk`):** Built strictly on Python 3.10+ standard library modules (`urllib.request`, `json`, `dataclasses`, `time`), featuring dedicated modular namespaces (`client.tasks`, `client.models`, `client.network`, `client.audit`), client-side clearance checks, and strict directory traversal guards on artifact downloads (T-05-08).

---

## 2. Tasks Completed

### Task 05-03-01 (Tracer): Sovereign CLI Extensions (`serve`, `task`, `model vram`)
- Modified `src/sovereign/cli.py`:
  - Added `_send_api_request` helper supporting JSON payload serialization, error response extraction, Bearer tokens, and `X-Sovereign-Role` header injection.
  - Implemented `sovereign serve`: validates binding host with `validate_server_binding(host)`, raises `BindingSecurityError` and halts with code 1 if binding to `0.0.0.0` or public IPs; launches Uvicorn factory `sovereign.server.app:create_app`.
  - Implemented `sovereign task` command group:
    - `task submit <prompt>`: enforces `--role` least-privilege policy (immediately exits with code 1 if `--role auditor`); supports `--file`, `--model`, `--stream`, `--token`, `--server-url`.
    - `task status <task_id>`: displays task state, step count, pending HITL approval alerts, and deliverables.
    - `task logs <task_id>`: displays execution trace timeline; supports `--follow` streaming.
    - `task approve <task_id>` & `task reject <task_id>`: submits operator review decisions to `/api/tasks/{task_id}/resume`; halts immediately if attempted under Auditor role.
  - Implemented `sovereign model vram`: queries `/api/models/vram` (remote) or `VRAMScheduler` (in-process); renders Total Budget, Safety Reserve, Usable Envelope, Active Allocation, Allocated MB, Available Headroom, and Loaded Models.
- Implemented `tests/test_cli/__init__.py` and `tests/test_cli/test_workbench_cli.py` with 16 integration tests verifying fail-closed binding, Auditor role fencing, task lifecycle, and VRAM reporting.
- **Commit:** `5848ee5` — `feat(05-03): implement Sovereign CLI extensions for serve, task operations, and model vram`

### Task 05-03-02 (Auto): Lightweight Pure-Python SDK (`src/sovereign/sdk/`)
- Created `src/sovereign/sdk/` package with zero third-party runtime dependencies:
  - `exceptions.py`:
    - `SovereignError(Exception)`: base SDK exception.
    - `SovereignAPIError(SovereignError)`: captures HTTP status code, message, and error details.
    - `RBACPermissionError(SovereignError)`: raised when a user role lacks required clearance or when backend returns 403 Forbidden.
    - `SovereignConnectionError(SovereignError)` (with `ConnectionError` alias): raised when API is unreachable.
  - `models.py`:
    - `TaskStatus(str, Enum)`: `SUBMITTED`, `QUEUED`, `RUNNING`, `SUSPENDED`, `COMPLETED`, `FAILED`, `REJECTED`.
    - Typed dataclasses: `TaskResult`, `VRAMStatus`, `AuditVerificationResult`, `NetworkTelemetryResult`.
  - `client.py`:
    - `SovereignClient(base_url, role, token, timeout)`: implements HTTP communication using `urllib.request`.
    - `client.tasks`: `submit`, `get_status`, `wait_for_completion`, `approve`, `reject`, `download_artifact`. Enforces client-side clearance: `submit`, `approve`, and `reject` immediately raise `RBACPermissionError` if `role == UserRole.AUDITOR`. Enforces `target_file.is_relative_to(output_dir)` path traversal defense.
    - `client.models`: `list_models()`, `vram_status()`.
    - `client.network`: `get_status()`, `get_telemetry()`, `run_egress_test()`.
    - `client.audit`: `inspect()`, `verify()`, `export_session()`.
  - `__init__.py`: exports `SovereignClient`, `UserRole`, exceptions, and typed dataclass models.
- Implemented `tests/test_sdk/__init__.py` and `tests/test_sdk/test_sovereign_client.py` with 19 comprehensive tests covering the full SDK lifecycle.
- **Commit:** `fd94bea` — `feat(05-03): implement lightweight pure-Python SDK with modular namespaces and RBAC enforcement`

---

## 3. Verification and Test Results

### Test Execution Metrics
- **CLI Test Suite (`tests/test_cli/test_workbench_cli.py`):** 16 passed in 1.33s.
- **SDK Test Suite (`tests/test_sdk/test_sovereign_client.py`):** 19 passed in 0.41s.
- **Combined Wave 3 Test Suite:** 35 passed in 1.33s.
- **Full Project Regression Suite:** 377 passed in 11.17s across all 5 phases (0 regressions).

### Test Matrix per Requirement

| Requirement | Test Description | Test Target | Outcome |
|:---|:---|:---|:---:|
| **UI-02** | `sovereign serve` fails closed on `0.0.0.0` | `tests/test_cli/test_workbench_cli.py::test_cli_serve_fails_on_all_interfaces` | **PASS** |
| **UI-02** | `sovereign serve` fails closed on `::` | `tests/test_cli/test_workbench_cli.py::test_cli_serve_fails_on_ipv6_all_interfaces` | **PASS** |
| **UI-02** | `sovereign serve` fails closed on public/unauthorized IP | `tests/test_cli/test_workbench_cli.py::test_cli_serve_fails_on_unauthorized_ip` | **PASS** |
| **UI-02** | `sovereign serve` launches Uvicorn on `127.0.0.1` | `tests/test_cli/test_workbench_cli.py::test_cli_serve_valid_loopback_starts_uvicorn` | **PASS** |
| **UI-03** | CLI task submit, status, logs, approve, reject | `tests/test_cli/test_workbench_cli.py::test_cli_task_*` | **PASS** |
| **UI-03** | CLI model VRAM inspection (in-process & remote) | `tests/test_cli/test_workbench_cli.py::test_cli_model_vram_*` | **PASS** |
| **UI-04** | Programmatic task submission, polling, artifact download | `tests/test_sdk/test_sovereign_client.py::test_task_*` | **PASS** |
| **UI-04** | Programmatic VRAM, Network, and Audit verification | `tests/test_sdk/test_sovereign_client.py::test_models_*, test_network_*, test_audit_*` | **PASS** |
| **UI-05** | CLI blocks Auditor from task submission with code 1 | `tests/test_cli/test_workbench_cli.py::test_cli_task_submit_blocks_auditor` | **PASS** |
| **UI-05** | CLI blocks Auditor from task approve/reject with code 1 | `tests/test_cli/test_workbench_cli.py::test_cli_task_approve_blocks_auditor` | **PASS** |
| **UI-05** | SDK blocks Auditor from submit/approve/reject locally | `tests/test_sdk/test_sovereign_client.py::test_auditor_client_side_blocking_*` | **PASS** |
| **UI-05** | SDK translates HTTP 403 Forbidden to `RBACPermissionError` | `tests/test_sdk/test_sovereign_client.py::test_server_403_translated_to_rbac_permission_error` | **PASS** |
| **T-05-08**| Path traversal guard in artifact download | `tests/test_sdk/test_sovereign_client.py::test_download_artifact_path_traversal_blocked` | **PASS** |

---

## 4. Threat Model & Security Validations

- **T-05-03 (Elevation of Privilege - Auditor Bypass):** Mitigated at two client boundaries:
  1. *CLI Boundary:* CLI parser checks `--role auditor`, immediately prints `[ERROR] Auditor role is restricted from submitting tasks per least-privilege policy (UI-05)`, and exits with status 1.
  2. *SDK Boundary:* `client.tasks.submit()`, `approve()`, and `reject()` check `self.client.role == UserRole.AUDITOR` and raise `RBACPermissionError` before emitting any network call.
- **T-05-08 (Path Traversal in Deliverable Downloads):** Mitigated by resolving destination paths with `Path(output_dir).resolve()` and asserting `target_file.is_relative_to(out_dir)`, raising `ValueError` on any traversal pattern (e.g. `../../etc/passwd`).
- **T-05-09 (Zero Supply Chain Risk on Air-Gapped Workstations):** `sovereign.sdk` uses zero external dependencies beyond Python standard library modules (`urllib.request`, `json`, `dataclasses`, `time`). It installs and runs out-of-the-box on any Python 3.10+ host without network access.

---

## 5. Artifacts Produced

### Source Code
- `src/sovereign/cli.py` — Extended CLI with `serve`, `task submit`, `task status`, `task logs`, `task approve`, `task reject`, and `model vram`.
- `src/sovereign/sdk/__init__.py` — Clean public exports for SDK client, models, and exceptions.
- `src/sovereign/sdk/exceptions.py` — Typed exception hierarchy (`SovereignError`, `SovereignAPIError`, `RBACPermissionError`, `SovereignConnectionError`).
- `src/sovereign/sdk/models.py` — Dataclass models (`TaskResult`, `VRAMStatus`, `AuditVerificationResult`, `NetworkTelemetryResult`, `TaskStatus`).
- `src/sovereign/sdk/client.py` — `SovereignClient` and namespace classes (`TaskNamespace`, `ModelNamespace`, `NetworkNamespace`, `AuditNamespace`).

### Test Suites
- `tests/test_cli/__init__.py` — Package marker.
- `tests/test_cli/test_workbench_cli.py` — 16 CLI integration tests using Click `CliRunner`.
- `tests/test_sdk/__init__.py` — Package marker.
- `tests/test_sdk/test_sovereign_client.py` — 19 SDK integration tests covering full lifecycle and RBAC enforcement.
