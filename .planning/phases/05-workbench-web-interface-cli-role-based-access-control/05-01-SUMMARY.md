---
phase: "05-workbench-web-interface-cli-role-based-access-control"
plan: "05-01"
subsystem: "server"
tags:
  - "fastapi"
  - "uvicorn"
  - "binding-security"
  - "host-header-validation"
  - "dns-rebinding-protection"
  - "rbac-middleware"
  - "auditor-fencing"
  - "audit-escalation"
  - "websocket-streaming"
  - "rest-api"
requires:
  - "01-01"
  - "01-02"
  - "01-03"
  - "02-01"
  - "03-01"
  - "03-02"
provides:
  - "src/sovereign/server/__init__.py"
  - "src/sovereign/server/config.py"
  - "src/sovereign/server/auth/__init__.py"
  - "src/sovereign/server/auth/tokens.py"
  - "src/sovereign/server/auth/rbac.py"
  - "src/sovereign/server/ws/__init__.py"
  - "src/sovereign/server/ws/manager.py"
  - "src/sovereign/server/ws/trace.py"
  - "src/sovereign/server/ws/network_stream.py"
  - "src/sovereign/server/ws/hitl_stream.py"
  - "src/sovereign/server/routes/__init__.py"
  - "src/sovereign/server/routes/tasks.py"
  - "src/sovereign/server/routes/models.py"
  - "src/sovereign/server/routes/network.py"
  - "src/sovereign/server/routes/audit.py"
  - "src/sovereign/server/routes/preview.py"
  - "src/sovereign/server/routes/demos.py"
  - "src/sovereign/server/app.py"
affects:
  - "05-02-PLAN.md"
  - "05-03-PLAN.md"
tech-stack:
  added:
    - "fastapi>=0.110.0"
    - "uvicorn>=0.28.0"
    - "httpx>=0.27.0"
    - "websockets>=12.0"
  patterns:
    - "Fail-closed server binding guard (validate_server_binding) rejecting 0.0.0.0, ::, and public IPs with BindingSecurityError"
    - "HostHeaderMiddleware preventing DNS rebinding attacks by validating against allowed host list"
    - "3-Tier RBAC middleware enforcing Admin >= Engineer >= Auditor with cryptographic token validation and header fallback"
    - "Auditor security fencing strictly blocking task submission/resumption with HTTP 403 and logging SECURITY_ALERT_RBAC_VIOLATION to AuditLedger"
    - "Asyncio-safe multi-topic WebSocket connection manager with bounded 200-message queues and ping/pong keepalives"
    - "Modular REST API routes covering tasks, models/vram, network policy/telemetry/probes, audit ledger verification, preview bounding boxes, and demo workflow triggers"
key-files:
  created:
    - "src/sovereign/server/__init__.py"
    - "src/sovereign/server/config.py"
    - "src/sovereign/server/auth/__init__.py"
    - "src/sovereign/server/auth/tokens.py"
    - "src/sovereign/server/auth/rbac.py"
    - "src/sovereign/server/ws/__init__.py"
    - "src/sovereign/server/ws/manager.py"
    - "src/sovereign/server/ws/trace.py"
    - "src/sovereign/server/ws/network_stream.py"
    - "src/sovereign/server/ws/hitl_stream.py"
    - "src/sovereign/server/routes/__init__.py"
    - "src/sovereign/server/routes/tasks.py"
    - "src/sovereign/server/routes/models.py"
    - "src/sovereign/server/routes/network.py"
    - "src/sovereign/server/routes/audit.py"
    - "src/sovereign/server/routes/preview.py"
    - "src/sovereign/server/routes/demos.py"
    - "src/sovereign/server/app.py"
    - "tests/test_server/__init__.py"
    - "tests/test_server/conftest.py"
    - "tests/test_server/test_binding_security.py"
    - "tests/test_server/test_rbac_middleware.py"
    - "tests/test_server/test_websocket_streams.py"
    - "tests/test_server/test_api_routes.py"
  modified:
    - "pyproject.toml"
key-decisions:
  - "Enforced fail-closed network binding: Server only permits localhost or intranet CIDR addresses from network_policy.yaml; binding to 0.0.0.0 or public IPs raises BindingSecurityError."
  - "Deployed HostHeaderMiddleware on all requests to protect air-gapped web console from DNS rebinding and cross-site framing attacks."
  - "Reused existing canonical UserRole enum and clearance logic from src/sovereign/tools/schemas.py to guarantee 100% role consistency across tool execution and API layers."
  - "Enforced security audit escalation on unauthorized task attempts: Whenever an Auditor attempts to call task submission or resumption, an immutable SECURITY_ALERT_RBAC_VIOLATION event is recorded in the SHA-256 hash-chained AuditLedger."
  - "Implemented bounded WebSocket broadcast queues (max 200 items) to prevent slow-client memory exhaustion during high-throughput agent reasoning or telemetry streaming."
requirements-completed:
  - "UI-02"
  - "UI-05"
---

# Plan 05-01 Summary: FastAPI Backend Service, REST APIs, WebSocket Event Streaming & 3-Tier RBAC Middleware

Wave 1 of Phase 5 is complete. All 4 tasks have been executed, verified, and committed with 75 dedicated unit and integration tests passing.

## Accomplishments

1. **Server Startup Binding Guard & DNS Rebinding Protection (Task 05-01-01 / UI-02):**
   - Implemented `validate_server_binding()` which verifies socket binding addresses against `network_policy.yaml` allowed loopback (`127.0.0.0/8`, `::1/128`) and intranet subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
   - Rejects `0.0.0.0`, `::`, and public IPs with `BindingSecurityError`.
   - Implemented `HostHeaderMiddleware` rejecting requests with untrusted or external `Host` headers with HTTP 400.
   - 22 passing tests in `tests/test_server/test_binding_security.py`.

2. **3-Tier RBAC Middleware & Security Fencing (Task 05-01-02 / UI-05):**
   - Implemented HMAC-SHA256 signed access tokens (`sovg_<role>_<user_id>_<signature>`) and `RBACGuard` dependency.
   - Enforces hierarchical clearance: `ADMIN` (3) >= `ENGINEER` (2) >= `AUDITOR` (1).
   - Auditor role is strictly blocked from `POST /api/tasks` and `POST /api/tasks/{task_id}/resume` with HTTP 403 Forbidden.
   - Every unauthorized attempt logs a `SECURITY_ALERT_RBAC_VIOLATION` event to the Phase 1 `AuditLedger`.
   - 22 passing tests in `tests/test_server/test_rbac_middleware.py`.

3. **Multi-Channel WebSocket Streaming (Task 05-01-03 / UI-01, UI-05):**
   - Implemented `ConnectionManager` with topic-based pub/sub (`task:{id}`, `network:telemetry`, `hitl:alerts`) and bounded queues.
   - `/ws/tasks/{task_id}`: Streams live reasoning trace steps (`TRACE_STEP`) with ping/pong and cancellation keepalives.
   - `/ws/network`: Pushes real-time `NETWORK_EVENT` (allowed) and `EGRESS_ALERT` (denied) telemetry directly from the connection ring buffer.
   - `/ws/hitl`: Broadcasts `HITL_ALERT` for Human-in-the-Loop approval requests.
   - 10 passing tests in `tests/test_server/test_websocket_streams.py`.

4. **REST API Routes & App Factory (Task 05-01-04 / UI-01, UI-02, UI-05):**
   - Created comprehensive REST routes:
     - `/api/health` & `/api/me`: System status and role clearance introspection.
     - `/api/tasks`: Submit (Engineer+), list, status, resume approval/rejection (Engineer+), artifact download.
     - `/api/models`: Model catalog (Auditor+), VRAM metrics (Auditor+), hot-registration (Admin).
     - `/api/network`: Policy status, connection telemetry snapshot, synthetic egress test trigger.
     - `/api/audit`: Ledger inspection, SHA-256 hash-chain verification, session JSON export.
     - `/api/preview/{doc_id}`: Normalized document preview metadata with bounding box coordinates.
     - `/api/demos/{demo_id}/launch`: Guided demonstration workflow trigger (demo_a, demo_b, demo_c).
   - Assembled into `create_app()` factory with localhost/intranet CORS policy and static file serving.
   - 21 passing tests in `tests/test_server/test_api_routes.py`.

## Verification Results
- 75 server tests passing in `tests/test_server/`.
- All 313 total repository tests passing across Phases 1 through 5.
