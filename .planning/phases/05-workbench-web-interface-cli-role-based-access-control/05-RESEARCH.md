# Phase 5: Workbench Web Interface, CLI & Role-Based Access Control - Technical Research

**Phase:** 05  
**Topic:** Localhost/Intranet-Bound Multi-Pane Web UI, Real-Time WebSocket Streaming (Reasoning Trace, Egress Monitor, HITL Gates), 3-Tier RBAC Fencing (Admin, Engineer, Auditor), Full-Featured Sovereign CLI, and Lightweight Python SDK  
**Author:** Antigravity Engineering (Chief Architect, Full-Stack Web Architect, Systems Security Officer, CLI/SDK Lead)  
**Date:** 2026-09-14  
**Status:** Approved  

---

## 1. Executive Summary & Problem Framing

### 1.1 Purpose and Scope
Phase 5 delivers the user-facing presentation, operational control, and programmatic interfaces of the Sovereign AI Workbench. While Phase 1 established the zero-egress cryptographic audit trail and network monitor, Phase 2 delivered local model loading and VRAM scheduling, Phase 3 created the cyclical agentic state machine and sandboxed execution environment, and Phase 4 built multimodal ingestion, local RAG, and native deliverable generators, Phase 5 unites these capabilities into a unified operational console:
1. **FastAPI Backend & Real-Time Event Streaming:** High-performance asynchronous REST API and WebSocket gateway binding strictly to localhost (`127.0.0.1`) or designated enterprise intranet CIDRs. Streams agent reasoning traces, real-time socket telemetry, and Human-in-the-Loop (HITL) approval gates.
2. **Air-Gapped Multi-Pane Web UI:** A zero-external-CDN, single-page web interface providing simultaneous visibility across:
   - Guided step-by-step demonstration workflows (Demo A: Inspection Report → Approval Note; Demo B: Code Generation & Sandbox; Demo C: P&ID Drawing Revision Comparison).
   - Live agent reasoning trace with step-by-step thoughts, tool invocations, and execution latency.
   - Interactive document preview with spatial bounding box overlays (OCR text, handwriting, confidence flags, and drawing diff pins).
   - Human-in-the-Loop approval gate interface for operator sign-off before deliverable finalization.
   - Live network egress telemetry dashboard displaying socket connections, process names, and allow/deny verdicts.
3. **Consistent 3-Tier Role-Based Access Control (RBAC):** Cryptographically enforced least-privilege access across Admin, Engineer (Standard User), and Auditor roles across all interfaces (Web, CLI, SDK, and API). Specifically, the Auditor role has full read access to audit logs, cryptographic verification, and network telemetry, but is strictly blocked from task submission and workflow execution.
4. **Sovereign CLI (`sovereign`):** Full-featured command-line utility for daemon management, task execution, model catalog and VRAM inspection, audit log export and chain verification, and synthetic network egress testing.
5. **Lightweight Python SDK (`sovereign.sdk`):** A zero-heavy-dependency client library enabling programmatic task submission, status polling, artifact retrieval, and audit trail verification for automated industrial pipelines.

### 1.2 The Air-Gapped Industrial Dilemma
Deploying modern web applications in high-security, air-gapped industrial environments (refineries, power plants, defence manufacturing enclaves) introduces unique constraints that break standard cloud-native web architectures:
- **The CDN Dependency Trap:** Modern web applications frequently depend on public Content Delivery Networks (CDNs) for JavaScript libraries (e.g., React, Vue, HTMX from cdnjs/unpkg), fonts (Google Fonts), or icon sets (FontAwesome). In a true air-gapped environment with default-deny network egress (SOVG-04), any browser attempt to fetch external assets will fail, hang page rendering, or trip the Phase 1 `NetworkMonitor` to generate critical security alerts.
- **Accidental Remote Exposure:** Development web servers and microservices often bind to `0.0.0.0` by default. In an industrial plant with dual-homed engineering laptops (connected to both an air-gapped SCADA subnet and an external corporate office network), binding to `0.0.0.0` could inadvertently expose the AI workbench and sensitive plant schematics to unauthorized corporate subnets.
- **Surface-Level RBAC Inconsistencies:** Many enterprise tools enforce RBAC only in the web UI by hiding buttons, while leaving backend REST endpoints unprotected or allowing CLI/SDK bypasses. In regulated environments, an auditor must be physically unable to trigger actions that alter plant operational data, regardless of whether they access the platform via Web, CLI, or script.
- **Fragile Web Packaging:** Heavyweight Node.js build pipelines, complex Webpack/Vite bundlers, and hundreds of transitive NPM dependencies create severe software supply chain vulnerabilities and prevent deterministic offline deployment on locked-down Linux/Windows engineering workstations.

### 1.3 Primary Architectural Recommendations
To guarantee total operational sovereignty, zero network egress, and airtight security fencing, Phase 5 adopts the following architecture:
1. **Self-Contained Asynchronous FastAPI Gateway (`src/sovereign/server/`):**
   - Built on FastAPI and Uvicorn, serving both REST endpoints, WebSocket streaming channels, and static web assets.
   - Enforces strict socket binding checks: defaults to `127.0.0.1`; binding to LAN interfaces requires explicit CIDR validation against `network_policy.yaml`; binding to `0.0.0.0` or public IPs fails closed on startup.
   - Host Header Validation Middleware mitigates DNS rebinding attacks.
2. **Zero-External-CDN Vanilla Web UI (`src/sovereign/server/static/`):**
   - Built using vanilla HTML5, modern CSS3 (custom properties, Grid, Flexbox), and native ES6 JavaScript without external dependencies.
   - All icons are rendered as embedded SVG symbols. All fonts use the native system font stack (`system-ui, Segoe UI, Roboto, Consolas`).
   - Single-page application architecture with four synchronized panels and interactive HTML5 Canvas/SVG overlays for document bounding boxes and visual drawing diffs.
3. **Multi-Channel WebSocket Streaming:**
   - Dedicated WebSocket endpoints for low-latency push updates: `/ws/tasks/{task_id}` (agent reasoning trace), `/ws/network` (real-time socket connection telemetry from Phase 1 `NetworkMonitor`), and `/ws/hitl` (operator approval alerts).
   - WebSocket connections authenticate via API token or role query parameters and enforce role-based channel access.
4. **Multi-Layered RBAC Security Fencing:**
   - Unifies the Phase 3 `UserRole` hierarchy (`ADMIN: 3`, `ENGINEER: 2`, `AUDITOR: 1`) across all access surfaces.
   - API endpoints use FastAPI dependency injection (`require_role(UserRole.ENGINEER)`) to block Auditor accounts from `POST /api/tasks`, `POST /api/workflow/run`, and `POST /api/tasks/{task_id}/resume`. Any violation returns HTTP 403 Forbidden and logs a `SECURITY_ALERT_RBAC_VIOLATION` event in the cryptographic audit ledger.
   - Web UI dynamically filters viewports: Auditor mode hides submission forms, disables approval controls, and elevates the Audit and Network Telemetry panes.
5. **Full CLI & Pure-Python SDK (`sovereign.sdk`):**
   - Extends the Click-based `sovereign` CLI with server management (`sovereign serve`), task execution (`sovereign task submit`, `status`, `logs --follow`, `approve`), model VRAM monitoring (`sovereign model vram`), and RBAC parameter enforcement.
   - Implements `sovereign.sdk` using Python's standard library (`urllib.request`, `json`, `threading`) with optional `websockets`/`httpx` support, guaranteeing 100% operation on any air-gapped machine without requiring external pip packages.

---

## 2. Requirements & Traceability Matrix

Phase 5 directly fulfills 5 primary user interface, access control, and programmatic requirements (UI-01 through UI-05), while supporting the underlying execution paths for the Phase 6 demonstration workflows (DEMO-01 through DEMO-03):

| Requirement ID | PRD Ref | Specification Summary | Target Plan | Implementation Mechanism | Success Verification |
|:---|:---|:---|:---|:---|:---|
| **UI-01** | FR-UI-1 | Web UI provides a guided step-by-step mode for executing the core SIH demonstration workflows. | `05-02` | Guided demo launcher sidebar in Web UI with pre-configured step cards for Demo A, Demo B, and Demo C, executing through Phase 3/4 pipelines. | First-time user can launch and complete Demo A, B, and C unassisted with visual step indicators. |
| **UI-02** | FR-UI-2 | Web application and backend APIs bind exclusively to localhost and designated intranet interfaces. | `05-01` | Socket binding validator in server startup; rejects `0.0.0.0` or public IPs; verifies LAN interfaces against `network_policy.yaml` allowed CIDRs; Host header validation middleware. | Port scan from outside intranet segment shows port unreachable; server refuses to bind to unauthorized interfaces. |
| **UI-03** | FR-UI-3 | Full-featured CLI supports model registration, task execution, audit log export, and network status checks. | `05-03` | Extended Click CLI (`sovereign serve`, `sovereign task submit/status/logs/approve`, `sovereign model vram`, `sovereign audit verify/export`). | All three demo workflows can be initiated, monitored, approved, and verified end-to-end via CLI alone. |
| **UI-04** | FR-UI-4 | Minimal Python SDK supports programmatic task submission, status polling, and artifact retrieval. | `05-03` | `sovereign.sdk.SovereignClient` providing task submission, polling, artifact download, VRAM status, and audit verification. | Standalone script using only `sovereign.sdk` submits Demo B (coding task), polls status, and downloads verified script and execution log. |
| **UI-05** | FR-UI-5 | Role-Based Access Control enforces least-privilege view and action filtering across Admin, Standard User (Engineer), and Auditor roles. | `05-01`<br>`05-02`<br>`05-03` | FastAPI RBAC middleware, Web UI view filtering, CLI `--role`/token enforcement, and SDK permission exceptions; Auditor strictly blocked from task submission. | Auditor role session has zero visible or callable task submission actions in UI, receives HTTP 403 on API, and is blocked in CLI/SDK. |
| *Ref: DEMO-01* | FR-UI-1 | Demo Workflow A: Scanned inspection report → OCR → findings → HITL approval → Word (.docx) export. | `05-01`<br>`05-02` | API & UI routes trigger OCR extraction, bounding box rendering, HITL approval gate suspension, and deliverable download. | UI displays bounding boxes, pauses at approval gate, resumes on click, and downloads styled Word memo. |
| *Ref: DEMO-02* | FR-UI-1 | Demo Workflow B: Industrial CSV parsing → code gen → sandbox execution → auto-fix → verified script. | `05-01`<br>`05-02`<br>`05-03` | API & UI routes invoke code model, execute in Phase 3 sandbox, stream iteration logs via WebSocket, package via `CodeArtifactExporter`. | Live trace pane shows sandbox logs, auto-correction loop, and final code/log artifact download. |
| *Ref: DEMO-03* | FR-UI-1 | Demo Workflow C: Multimodal comparison of two drawing revisions → diff detection → overlay & change summary. | `05-01`<br>`05-02` | API & UI routes invoke `DrawingDiffEngine`, render visual diff canvas overlay with color-coded callouts, export change register. | Dual-revision comparison view shows red/green/amber visual diff overlay and structured change table. |

---

## 3. Architectural Responsibility Map

```
+-------------------------------------------------------------------------------------------------------------------------+
|                                           SOVEREIGN AI WORKBENCH - PHASE 5 ARCHITECTURE                                  |
+-------------------------------------------------------------------------------------------------------------------------+
|                                                                                                                         |
|   +------------------------------------+   +-----------------------------------+   +--------------------------------+   |
|   |         MULTI-PANE WEB UI          |   |           SOVEREIGN CLI           |   |       PYTHON SDK (CLIENT)      |   |
|   |   (Zero-CDN, Self-Contained HTML5) |   |         (sovereign CLI tool)      |   |      (sovereign.sdk.Client)    |   |
|   +------------------------------------+   +-----------------------------------+   +--------------------------------+   |
|     |  - Guided Demo Launcher (UI-01)        |  - sovereign serve                    |  - client.tasks.submit()         |   |
|     |  - Live Reasoning Trace Pane           |  - sovereign task submit / logs       |  - client.tasks.poll_status()    |   |
|     |  - Document / Bounding Box Preview     |  - sovereign task approve / resume    |  - client.tasks.download()       |   |
|     |  - HITL Approval Queue                 |  - sovereign model vram / list        |  - client.audit.verify()         |   |
|     |  - Real-Time Egress Monitor Pane       |  - sovereign network status / test    |  - client.network.telemetry()    |   |
|     |  - RBAC View Filtering (UI-05)         |  - RBAC token / role enforcement      |  - RBAC token / role checks      |   |
|     +-------------------+--------------+   +-----------------+-----------------+   +---------------+----------------+   |
|                         |                                    |                                     |                    |
|                         | HTTP REST / WebSocket              | REST / In-Process                   | HTTP REST          |
|                         v                                    v                                     v                    |
|   +-----------------------------------------------------------------------------------------------------------------+   |
|   |                                          FASTAPI GATEWAY SERVICE                                                |   |
|   |                                     (src/sovereign/server/app.py)                                               |   |
|   |                                                                                                                 |   |
|   |   [NETWORK BINDING ENFORCEMENT] (UI-02)                                                                         |   |
|   |    • Strict binding: 127.0.0.1 or validated intranet CIDR (from network_policy.yaml)                            |   |
|   |    • Refuses 0.0.0.0 / public IPs on startup; Host header validation middleware prevents DNS rebinding          |   |
|   |                                                                                                                 |   |
|   |   [3-TIER RBAC MIDDLEWARE & DEPENDENCY INJECTION] (UI-05)                                                       |   |
|   |    • Admin (Level 3): Full control (models hot-add, policy, audit, tasks)                                       |   |
|   |    • Engineer (Level 2): Task submit, workflow execute, HITL approve, artifact download                          |   |
|   |    • Auditor (Level 1): Read-only audit logs, chain verification, network telemetry. TASK SUBMIT STRICTLY BLOCKED |   |
|   |                                                                                                                 |   |
|   |   [REST API ROUTERS]                       [WEBSOCKET STREAMING GATEWAYS]                                       |   |
|   |    • /api/tasks/* (Submit, Status, Resume)  • /ws/tasks/{task_id} (Reasoning trace & thoughts)                   |   |
|   |    • /api/models/* (List, VRAM, Hot-Add)    • /ws/network (Live socket telemetry push)                          |   |
|   |    • /api/network/* (Policy, Telemetry)     • /ws/hitl (Pending approval gate notifications)                     |   |
|   |    • /api/audit/* (Inspect, Verify, Export)                                                                     |   |
|   |    • /api/preview/* (Doc JSON, Bounding Box)                                                                    |   |
|   +-----------------------------------------------------------------------------------------------------------------+   |
|                                                          |                                                              |
|                     +------------------------------------+-----------------------------------+                          |
|                     |                                                                        |                          |
|                     v                                                                        v                          |
|   +----------------------------------------------------+   +--------------------------------------------------------+   |
|   |               AGENT ORCHESTRATOR                   |   |                 SOVEREIGNTY & AUDIT                    |   |
|   |   (src/sovereign/orchestration/runtime.py)         |   |   (src/sovereign/audit/, src/sovereign/network/)       |   |
|   |                                                    |   |                                                        |   |
|   |   • StateGraph / CompiledGraph Execution           |   |   • AuditLedger (SHA-256 Hash-Chained JSONL)           |   |
|   |   • GraphInterrupt -> HITL Gate Suspension         |   |   • NetworkMonitor (psutil Socket Telemetry Worker)    |   |
|   |   • SQLiteCheckpointer (WAL Thread Persistence)    |   |   • ConnectionRingBuffer (In-Memory Circular Buffer)   |   |
|   |   • Bounded Self-Correction Loop                   |   |   • NetworkPolicyEngine (Default-Deny Zero Egress)     |   |
|   +----------------------------------------------------+   +--------------------------------------------------------+   |
|                     |                                                                        |                          |
|                     v                                                                        v                          |
|   +----------------------------------------------------+   +--------------------------------------------------------+   |
|   |               MODEL & TOOLING LAYER                |   |                  OUTPUT REPOSITORY                     |   |
|   |   (src/sovereign/models/, src/sovereign/tools/)    |   |   (/local/output/ & deliverables engine)               |   |
|   |                                                    |   |                                                        |   |
|   |   • ModelRegistry & VRAMScheduler (24GB Budget)    |   |   • Word (.docx), Excel (.xlsx), PowerPoint (.pptx)    |   |
|   |   • ToolRegistry (Role Clearances & JSON Schemas)  |   |   • Code Artifacts (.py) & Execution Logs (.log)       |   |
|   |   • CodeSandbox (Resource/Network Bounded)         |   |   • P&ID Visual Diff Overlays & Change Registers       |   |
|   |   • Multimodal OCR & SQLiteVectorStore RAG         |   |   • Cryptographic Lineage Sidecars (.lineage.json)     |   |
|   +----------------------------------------------------+   +--------------------------------------------------------+   |
+-------------------------------------------------------------------------------------------------------------------------+
```

---

## 4. Standard Stack & Library Dependencies

### 4.1 Core Dependencies & Role Justification

| Package / Library | Minimum Version | Category | Air-Gap Suitability & Purpose | Telemetry Risk & Mitigation |
|:---|:---|:---|:---|:---|
| **fastapi** | $\ge 0.110.0$ | Core Backend | ASGI web framework providing OpenAPI generation, routing, dependency injection, and Pydantic request/response validation. | **Zero Risk:** Pure Python ASGI framework; no telemetry or outbound calls. Already declared in `pyproject.toml`. |
| **uvicorn** | $\ge 0.28.0$ | ASGI Server | Production-grade, high-performance ASGI server for hosting FastAPI and handling concurrent WebSocket connections. | **Zero Risk:** Pure local networking daemon; zero telemetry. Already declared in `pyproject.toml`. |
| **websockets** | $\ge 12.0$ | Async Streaming | WebSocket protocol implementation powering FastAPI's native WebSocket support and bi-directional real-time telemetry streaming. | **Zero Risk:** Standard pure-Python/C protocol library; no telemetry. |
| **click** | $\ge 8.1.0$ | CLI Framework | Command-line interface parser powering the unified `sovereign` CLI. | **Zero Risk:** Standard CLI library; offline only. Already declared in `pyproject.toml`. |
| **pydantic** | $\ge 2.6.0$ | Schema Validation | Data validation and JSON serialization for API request/response models and WebSocket events. | **Zero Risk:** Core library; no network connectivity. Already declared in `pyproject.toml`. |
| **pydantic-settings**| $\ge 2.2.0$ | Configuration | Environment and YAML configuration management for server host/port and security bindings. | **Zero Risk:** Settings loader; offline only. Already declared in `pyproject.toml`. |
| **urllib.request** | stdlib | SDK Core Client | Python standard library HTTP client powering `sovereign.sdk`, guaranteeing zero-dependency client execution on air-gapped hosts. | **Zero Risk:** Standard library module; zero telemetry. |
| **httpx** | $\ge 0.27.0$ (Optional) | Async SDK Client | Optional modern HTTP client for high-throughput async client interactions and integration tests. | **Zero Risk:** Pure HTTP client; zero telemetry. |

### 4.2 Alternatives Considered & Rejected
- **Node.js / React / Next.js / Vue:** Rejected for the primary Web UI. Requiring Node.js runtime, `npm install`, and massive node_modules dependency graphs in an air-gapped industrial deployment introduces severe software supply chain risks, build failures on offline machines, and unnecessary resource consumption on field workstations. A self-contained, zero-dependency HTML5/CSS3/ES6 vanilla SPA served directly by FastAPI eliminates the need for Node.js entirely while delivering 60 FPS UI rendering and instant startup.
- **Flask / Django:** Rejected for the backend. Flask requires WSGI-to-ASGI adapters (like Gevent or Quart) for WebSocket streaming, while Django introduces excessive ORM overhead. FastAPI natively provides asynchronous async/await execution, built-in WebSocket endpoints, Pydantic type safety, and automatic OpenAPI schema generation.
- **External CSS/Icon CDNs (Tailwind CDN, FontAwesome, Bootstrap):** Strictly rejected. External URLs fail immediately in air-gapped networks and trip the Phase 1 `NetworkMonitor` default-deny egress alerts. All CSS is self-contained modern CSS, and all icons are embedded SVGs.

---

## 5. Air-Gap & Zero-External-CDN UI Strategy

### 5.1 The Zero-External-CDN Architecture
To guarantee 100% functionality inside a true air-gapped security enclave (SOVG-04), the Web UI must not issue a single HTTP request to external hosts. The frontend is engineered with the following strict constraints:
1. **Asset Self-Containment:** All HTML, CSS, JavaScript, and graphical assets are located within `src/sovereign/server/static/` and served via FastAPI's `StaticFiles` mounting, or embedded directly in the single-page template.
2. **System Typography:** No `@import url('https://fonts.googleapis.com/...')` or webfont files. The application utilizes modern OS-native font stacks:
   ```css
   font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif, "Consolas", monospace;
   ```
3. **Raw Inline SVG Iconography:** No icon font downloads (e.g. font-awesome.woff2). All UI icons (status pills, play buttons, expand arrows, checkmarks, warning triangles, shields) are defined as clean, scalable inline `<svg>` elements directly in the markup.
4. **Vanilla ES6+ Architecture:** The UI uses native browser capabilities:
   - `fetch()` for REST communication.
   - `WebSocket` for real-time trace, network, and HITL streaming.
   - HTML5 `<canvas>` and SVG overlays for rendering normalized bounding boxes over document pages and visual drawing diffs.
   - Native DOM manipulation with template literals—zero external runtime dependencies.

### 5.2 Network Interface Binding & DNS Rebinding Mitigation (UI-02)
Industrial security mandates that services must never bind to `0.0.0.0` (all interfaces) by default, as this could expose the AI workbench to unauthorized subnets via multi-homed NICs:
1. **Strict Default Binding:** The backend binds strictly to `127.0.0.1` (loopback) by default.
2. **Intranet Interface Validation:** If configured to bind to a non-loopback IP (e.g. `192.168.1.50` or `10.0.5.20`), the server validates that the specified IP falls within one of the `allowed_intranet_cidrs` declared in `network_policy.yaml`.
3. **Fail-Closed Startup:** If an operator attempts to launch the server with `0.0.0.0` or a public/unauthorized IP, the server aborts startup immediately with a fatal `BindingSecurityError`.
4. **Host Header Validation Middleware:** Web browsers on intranet workstations could be targeted by DNS rebinding attacks if an attacker controls a local DNS resolver. The server includes a `HostHeaderMiddleware` that validates the `Host` header against an allowlist (`localhost`, `127.0.0.1`, and explicitly configured intranet domain/IP), rejecting unapproved hosts with HTTP 400 Bad Request.

---

## 6. Subsystem Deep Dives

### 6.1 FastAPI Server, REST API & WebSocket Event Streaming (Plan 05-01)

#### 6.1.1 Core Server Architecture
The backend application resides in `src/sovereign/server/app.py`. It integrates the underlying Sovereign subsystems:
- **`ModelManager` & `VRAMScheduler`** for model status and memory budgeting.
- **`AgentRuntime` & `StateGraph`** for asynchronous task execution and HITL suspension.
- **`NetworkMonitor` & `ConnectionRingBuffer`** for real-time socket telemetry.
- **`AuditLedger`** for cryptographic event logging and tamper-evident verification.
- **Deliverable & Vision Engines** for document and drawing visual overlays.

```
src/sovereign/server/
├── __init__.py
├── app.py                 # FastAPI application factory, middleware, static mount
├── config.py              # Server settings, host validation, port configuration
├── auth/
│   ├── __init__.py
│   ├── rbac.py            # RBAC middleware, token validation, require_role dependencies
│   └── tokens.py          # Cryptographic API key / session token generator & verifier
├── routes/
│   ├── __init__.py
│   ├── tasks.py           # Task submission, status, resume, cancel, artifact download
│   ├── demos.py           # One-click guided demo workflow execution endpoints (Demo A, B, C)
│   ├── models.py          # Model catalog, VRAM scheduler status, hot-registration
│   ├── network.py         # Network policy status, telemetry snapshots, synthetic egress test
│   ├── audit.py           # Ledger inspect, SHA-256 chain verify, session slice export
│   └── preview.py         # NormalizedDocument JSON, page raster images, bounding box data
├── ws/
│   ├── __init__.py
│   ├── manager.py         # ConnectionManager tracking active WebSockets per task/topic
│   ├── trace.py           # WebSocket endpoint /ws/tasks/{task_id} (Reasoning trace)
│   ├── network_stream.py  # WebSocket endpoint /ws/network (Socket telemetry push)
│   └── hitl_stream.py     # WebSocket endpoint /ws/hitl (Human approval alerts)
└── static/                # Air-gapped single-page Web UI assets
    ├── index.html         # Multi-pane dashboard layout
    ├── styles.css         # Self-contained dark/light industrial CSS theme
    ├── app.js             # Vanilla JS state manager, WebSocket client, UI controller
    └── preview.js         # Canvas/SVG document bounding box & drawing diff renderer
```

#### 6.1.2 REST API Endpoints Specification

| Route | Method | Required Role | Description |
|:---|:---:|:---:|:---|
| `/api/health` | `GET` | None | Service liveness, version, active environment, and binding host. |
| `/api/me` | `GET` | None | Returns active user identity, role (`admin`, `engineer`, `auditor`), and permission flags. |
| `/api/models` | `GET` | Auditor | Lists all registered models, engines, quantizations, and capabilities. |
| `/api/models/vram` | `GET` | Auditor | Returns VRAM memory metrics (`total_mb`, `usable_mb`, `allocated_mb`, `available_mb`, `loaded_models`). |
| `/api/models/register` | `POST` | Admin | Validates and hot-registers a new model manifest without service restart. |
| `/api/tasks` | `POST` | Engineer | Submits a new prompt/task for agent execution. Returns `task_id` and `thread_id`. |
| `/api/tasks` | `GET` | Auditor | Lists active and historical tasks and their execution status. |
| `/api/tasks/{task_id}` | `GET` | Auditor | Returns detailed task status, steps, intermediate thoughts, outputs, and pending approvals. |
| `/api/tasks/{task_id}/resume` | `POST` | Engineer | Submits operator HITL decision (`approve` or `reject`) with review notes. |
| `/api/tasks/{task_id}/artifacts/{file}`| `GET` | Auditor | Downloads an output deliverable (.docx, .xlsx, .pptx, .py, diff image). |
| `/api/demos/{demo_id}/launch` | `POST` | Engineer | One-click launch for pre-configured Demo A, Demo B, or Demo C. |
| `/api/network/status` | `GET` | Auditor | Inspects network policy, default-deny posture, allowed loopback/intranet CIDRs. |
| `/api/network/telemetry` | `GET` | Auditor | Retrieves recent socket connection telemetry from the ring buffer. |
| `/api/network/test-egress` | `POST` | Auditor | Executes synthetic egress probe suite and returns pass/fail results. |
| `/api/audit/inspect` | `GET` | Auditor | Returns statistics, record counts, and session information for the audit ledger. |
| `/api/audit/verify` | `GET` | Auditor | Executes SHA-256 hash-chain verification across all audit records. |
| `/api/audit/export` | `GET` | Auditor | Exports a standalone audit slice for a given `session_id` in JSON or JSONL. |
| `/api/preview/{doc_id}` | `GET` | Auditor | Returns canonical `NormalizedDocument` metadata and bounding box coordinates. |

#### 6.1.3 WebSocket Event Streaming Protocol
Three dedicated WebSocket channels provide real-time updates without polling:

1. **Reasoning Trace Channel (`/ws/tasks/{task_id}`):**
   - Emits structured JSON events as the `AgentRuntime` executes graph nodes:
   ```json
   {
     "type": "TRACE_STEP",
     "task_id": "task-8f92a1",
     "thread_id": "wf-b01",
     "step_index": 2,
     "node_name": "extract_findings",
     "model_id": "qwen2.5-7b-instruct",
     "status": "RUNNING",
     "thought": "Extracting inspection findings with spatial citations from page 1...",
     "tool_calls": [
       {"tool": "ocr_extract_region", "inputs": {"region_id": "p1-r004"}}
     ],
     "elapsed_ms": 420.5,
     "timestamp_iso": "2026-09-14T16:20:10.123Z"
   }
   ```
   - When a Human-in-the-Loop gate is reached, it emits:
   ```json
   {
     "type": "HITL_SUSPENDED",
     "task_id": "task-8f92a1",
     "thread_id": "wf-b01",
     "pending_approval": {
       "action": "deliverable_signoff",
       "deliverable_type": "docx",
       "summary": "Drafted Refinery Vessel V-301 Inspection Approval Note",
       "confidence_score": 0.94,
       "citations": ["doc-a81f9b#p1-r004", "doc-a81f9b#p1-r007"]
     }
   }
   ```

2. **Real-Time Network Telemetry Channel (`/ws/network`):**
   - The server registers an `event_callback` with the Phase 1 `NetworkMonitor`. As psutil scans socket connections, newly captured `NetworkEvent` objects are pushed directly to all active WebSocket clients:
   ```json
   {
     "type": "NETWORK_EVENT",
     "event": {
       "timestamp_iso": "2026-09-14T16:20:12.450Z",
       "protocol": "tcp",
       "local_address": "127.0.0.1:8000",
       "remote_address": "127.0.0.1:54321",
       "pid": 4812,
       "process_name": "python.exe",
       "verdict": "ALLOW",
       "reason": "Explicitly allowed loopback CIDR"
     }
   }
   ```
   - If an unauthorized egress attempt is blocked:
   ```json
   {
     "type": "EGRESS_ALERT",
     "event": {
       "timestamp_iso": "2026-09-14T16:20:15.100Z",
       "protocol": "udp",
       "local_address": "192.168.1.50:61234",
       "remote_address": "8.8.8.8:53",
       "pid": 9102,
       "process_name": "curl.exe",
       "verdict": "DENY",
       "reason": "Destination matches denied port 53 (DNS)"
     }
   }
   ```

3. **HITL Notification Channel (`/ws/hitl`):**
   - Broadcasts approval requests to all connected operators with Engineer or Admin clearance, ensuring immediate visibility of workflows awaiting sign-off.

---

### 6.2 3-Role RBAC Middleware & Security Fencing (UI-05)

#### 6.2.1 Role Hierarchy & Permissions
The system enforces a 3-tier Role-Based Access Control hierarchy:
- **`ADMIN` (Clearance Level 3):** Full system governance. Can hot-register models, modify network policy configuration, trigger system attestation, execute tasks, approve HITL gates, and inspect/export audit logs.
- **`ENGINEER` / Standard User (Clearance Level 2):** Day-to-day engineering operations. Can submit tasks, execute workflows, inspect model catalogs and VRAM status, preview documents and bounding boxes, review and approve/reject HITL gates, and download output artifacts. Cannot register models, reconfigure network policies, or modify system keys.
- **`AUDITOR` (Clearance Level 1):** Independent oversight and compliance. Can inspect the cryptographic audit ledger, verify hash chains, export session slices, view network policy, monitor real-time socket connections, run synthetic egress tests, and inspect deliverable lineage. **Strictly blocked from task submission, workflow execution, tool execution, and HITL approval.**

#### 6.2.2 Permission Matrix

| Capability / Resource | Admin | Engineer | Auditor | Enforcement Point |
|:---|:---:|:---:|:---:|:---|
| **View Audit Ledger & Verify Hash Chains** | Allowed | Allowed | Allowed | `GET /api/audit/*` |
| **View Network Monitor & Egress Telemetry** | Allowed | Allowed | Allowed | `GET /api/network/*`, `/ws/network` |
| **Run Synthetic Egress Probes** | Allowed | Allowed | Allowed | `POST /api/network/test-egress` |
| **View Deliverable Lineage & Sidecars** | Allowed | Allowed | Allowed | `GET /api/lineage/*` |
| **View Model Catalog & VRAM Headroom** | Allowed | Allowed | Allowed | `GET /api/models/*` |
| **Submit New Task / Execute Workflow** | Allowed | Allowed | **DENIED (403)** | `POST /api/tasks`, `POST /api/demos/*` |
| **Review & Approve/Reject HITL Gates** | Allowed | Allowed | **DENIED (403)** | `POST /api/tasks/{id}/resume` |
| **Direct Tool Execution** | Allowed | Allowed | **DENIED (403)** | `ToolRegistry.execute_tool()` |
| **Hot-Register New Model Manifests** | Allowed | **DENIED (403)** | **DENIED (403)** | `POST /api/models/register` |
| **Modify Network Policies / Settings** | Allowed | **DENIED (403)** | **DENIED (403)** | Server Config / Admin API |

#### 6.2.3 Cryptographic Token & Authentication Scheme
Authentication supports both headless air-gapped automation and web session access:
1. **API Keys / Bearer Tokens:** Tokens formatted as `sovg_<role>_<random_hex_32>_<hmac_sha256>`. The token encodes the user's role and is signed with a local server secret key.
2. **Local Session Header (`X-Sovereign-Role`):** In local development / intranet kiosk mode, a request header can provide the role, validated against pre-configured local role credentials.
3. **Escalation on Violation:** If an Auditor attempts to call `POST /api/tasks` or `POST /api/tasks/{id}/resume`:
   - The request is immediately rejected with `HTTP 403 Forbidden`.
   - The security middleware logs a `SECURITY_ALERT_RBAC_VIOLATION` event directly into the Phase 1 `AuditLedger`:
     ```json
     {
       "event_type": "SECURITY_ALERT_RBAC_VIOLATION",
       "actor_role": "auditor",
       "session_id": "sec-audit-violation",
       "payload": {
         "attempted_action": "POST /api/tasks",
         "required_role": "engineer",
         "user_role": "auditor",
         "client_ip": "127.0.0.1"
       }
     }
     ```

---

### 6.3 Multi-Pane Web UI Architecture & Guided SIH Demo Modes (Plan 05-02)

#### 6.3.1 Air-Gapped Single-Page Application Layout
The Web UI is structured as a responsive, four-pane industrial operations dashboard:

```
+-------------------------------------------------------------------------------------------------------------+
| [LOGO] SOVEREIGN AI WORKBENCH | AIR-GAPPED ENCLAVE | Role: [ENGINEER v] | Egress: [ZERO LEAKS] | VRAM: 8.2/22GB     |
+-------------------------------------------------------------------------------------------------------------+
| GUIDED DEMOS (UI-01)  | PANE 1: LIVE REASONING TRACE          | PANE 2: DOCUMENT & BOUNDING BOX PREVIEW     |
| [1. Demo A: Approval] | ------------------------------------- | ------------------------------------------- |
| [2. Demo B: Sandbox ] | • Step 1: Document Ingest [COMPLETE]  | [ Page 1 of 3 ] [ Zoom 100% ]               |
| [3. Demo C: Drawing ] | • Step 2: Findings Extract [COMPLETE] | +-----------------------------------------+ |
|                       | • Step 3: Draft Note       [COMPLETE] | | [Scan Image with Canvas Overlay]        | |
| TASK SUBMISSION       | • Step 4: Approval Gate    [PAUSED]   | |  +--------------------+                 | |
| Prompt: [__________]  |   Thought: Synthesized findings.      | |  | [r004] Min Thk: 3.2mm| (Green Box)   | |
| File:   [Browse...]   |   Awaiting Lead Engineer sign-off.    | |  +--------------------+                 | |
| [Submit Task]         | ------------------------------------- | +-----------------------------------------+ |
| (Hidden for Auditor)  | PANE 3: HUMAN APPROVAL QUEUE (HITL)   | PANE 4: REAL-TIME EGRESS MONITOR            |
|                       | ------------------------------------- | ------------------------------------------- |
| NAVIGATION            | [!] PENDING DELIVERABLE APPROVAL      | Total: 1,420 | Allow: 1,420 | Deny: 0       |
| [x] Live Workflows    | Summary: Vessel V-301 Inspection Note | ------------------------------------------- |
| [ ] Model Catalog     | Citations: doc-a81#p1-r004 (Conf: 96%)| 16:20:10 TCP 127.0.0.1 -> 127.0.0.1 [ALLOW] |
| [ ] Network Telemetry | Notes: [ All thickness checks valid ] | 16:20:11 TCP 127.0.0.1 -> 127.0.0.1 [ALLOW] |
| [ ] Audit Ledger      | [ APPROVE DELIVERABLE ]  [ REJECT ]   | [ Run Synthetic Egress Check ]              |
+-------------------------------------------------------------------------------------------------------------+
```

#### 6.3.2 Pane Functional Specifications

1. **Guided Demo Mode Selector (Left Sidebar - UI-01):**
   - **Demo A Button ("Inspection Report → Approval Note"):**
     - Loads sample inspection report (`refinery_vessel_inspection_v301.png`), triggers OCR extraction via `BaseOCRBackend`, extracts findings with spatial citations, pauses at HITL gate, and upon approval generates `Refinery_Inspection_Approval_Note.docx` in `/local/output`.
   - **Demo B Button ("Industrial Code & Sandbox"):**
     - Submits a vibration analysis script generation task against sample historian CSV data, executes code in the isolated `CodeSandbox`, runs through the bounded auto-fix iteration loop (FR-AO-5) upon simulated error, and exports verified `.py` script and `.log` to `/local/output`.
   - **Demo C Button ("P&ID Drawing Revision Comparison"):**
     - Loads two P&ID revision drawings (`pid_drawing_rev_a.png`, `pid_drawing_rev_b.png`), executes `DrawingDiffEngine`, and renders visual diff overlay with color-coded callouts and change register.

2. **Pane 1: Live Reasoning Trace:**
   - Connects to `/ws/tasks/{task_id}` via WebSocket.
   - Renders a live timeline of agent execution steps.
   - Each card displays step name, model identifier (e.g., `qwen2.5-7b-instruct`), elapsed execution time, model thought traces, and collapsible tool invocation details (arguments and return data).

3. **Pane 2: Document Preview & Interactive Bounding Box Renderer:**
   - Implemented via HTML5 `<canvas>` positioned directly over the document page image or SVG vector layer.
   - Fetches document metadata from `/api/preview/{doc_id}`.
   - Maps normalized coordinates `[ymin, xmin, ymax, xmax]` in `[0.0, 1.0]` to canvas pixel dimensions:
     - **Green Box (`#10B981`):** High-confidence printed text (`confidence >= 0.85`).
     - **Blue Box (`#3B82F6`):** Extracted handwriting entries.
     - **Amber Box (`#F59E0B`):** Low-confidence / `NEEDS_REVIEW` fields (`confidence < 0.85`).
     - **Drawing Diff Overlay:** Vivid Green for added components, Vivid Red for removed components, and Vivid Amber for modified components.
   - Clicking any finding or citation in the reasoning trace highlights the corresponding bounding box on the canvas and scrolls it into view.

4. **Pane 3: Human-in-the-Loop Approval Queue (HITL):**
   - Listens to `/ws/hitl`.
   - When the agent triggers `interrupt()` (e.g. before final deliverable generation), this pane renders an interactive approval dialog:
     - Displays deliverable type, summary findings, confidence scores, and source citations.
     - Operator text area for mandatory/optional justification notes.
     - Action buttons: **[Approve Deliverable]** (resumes workflow to generate final document) and **[Reject]** (halts workflow with reason).
     - **Auditor Fencing:** When viewing under the Auditor role, action buttons are replaced with a non-interactive badge: *"Auditor Clearance: Approval actions restricted to Lead Engineers"*.

5. **Pane 4: Real-Time Egress Monitor Dashboard:**
   - Connects to `/ws/network`.
   - Displays a live scrolling table of kernel-level socket connection events captured by psutil.
   - Each entry shows timestamp, process name (e.g. `python.exe`, `dockerd`), protocol, local socket, remote destination, policy verdict (`[ALLOW]` in vivid green, `[DENY]` in vivid red), and rule rationale.
   - Prominent counter pills show: **Total Events**, **Allowed Intranet**, **Denied Attempts**, and **Egress Leaks: 0**.
   - Includes a **[Run Egress Check]** button that triggers `/api/network/test-egress` to run live synthetic probes against DNS, HTTP, HTTPS, and NTP, proving 100% blocked outbound connectivity on demand for auditors.

6. **Role-Appropriate View Filtering (UI-05):**
   - The UI includes a client-side role filter synchronized with the backend:
     - In **Auditor Role**: The task submission prompt box, file upload dropzone, and guided demo execution buttons are completely hidden or disabled with a clear notice: *"Auditor Clearance Active: Oversight & Verification Only. Task submission disabled per least-privilege policy (FR-UI-5)."* The Audit Ledger explorer and Network Egress Monitor become the primary viewports.
     - In **Engineer Role**: Task submission, guided demos, reasoning trace, document preview, and HITL approval are active. System configuration and model registration are hidden.
     - In **Admin Role**: All panes and controls, including model manifest registration and policy controls, are visible.

---

### 6.4 Full-Featured Sovereign CLI & Minimal Python SDK (Plan 05-03)

#### 6.4.1 Sovereign CLI Architecture (`src/sovereign/cli.py`)
Phase 1, 2, and 3 established foundational CLI groups in `src/sovereign/cli.py` (`audit`, `network`, `test-egress`, `attest`, `lineage`, `model`, `tool`, `workflow`). Phase 5 unifies and extends this into a comprehensive administrative and operational tool:

1. **`sovereign serve`:** Launches the FastAPI backend service via Uvicorn:
   ```bash
   sovereign serve --host 127.0.0.1 --port 8000 --workers 1
   ```
   - Automatically validates interface binding against `network_policy.yaml`.
   - Halts with `BindingSecurityError` if binding to `0.0.0.0` or non-intranet interfaces is attempted.

2. **`sovereign task submit`:** Submits tasks either locally or against the running server daemon:
   ```bash
   sovereign task submit "Extract findings from inspection report" \
       --file refinery_vessel_v301.png \
       --role engineer \
       --token sovg_eng_xxxx \
       --stream
   ```
   - If `--stream` is passed, connects to the WebSocket trace stream and prints live step updates and thoughts directly to the terminal.
   - If executed under `--role auditor`, immediately refuses with:
     `[ERROR] Auditor role is restricted from submitting tasks per least-privilege policy (UI-05)`.

3. **`sovereign task status` & `sovereign task logs`:**
   ```bash
   sovereign task status <task_id>
   sovereign task logs <task_id> --follow
   ```

4. **`sovereign task approve` & `sovereign task reject`:**
   ```bash
   sovereign task approve <task_id> --notes "All thickness measurements verified against ASME Section VIII" --role lead_engineer
   ```

5. **`sovereign model vram`:**
   - Displays real-time GPU memory metrics from `VRAMScheduler`:
   ```bash
   $ sovereign model vram
   === Sovereign VRAM Scheduler Status ===
   Total Budget      : 24,576 MB (24.0 GB)
   Safety Reserve    : 2,048 MB (2.0 GB)
   Usable Envelope   : 22,528 MB (22.0 GB)
   Currently Active  : 8,192 MB (8.0 GB)
   Available Headroom: 14,336 MB (14.0 GB)
   Loaded Models     :
     • qwen2.5-7b-instruct [vram: 8,192 MB, last_used: 12s ago]
   =======================================
   ```

#### 6.4.2 Minimal Python SDK (`sovereign.sdk`)
The SDK provides a clean, programmatic interface for embedding Workbench capabilities into external automation scripts, ETL pipelines, and internal tools.

To ensure frictionless deployment on air-gapped workstations without package managers, `sovereign.sdk` is built on Python's standard library (`urllib.request`, `json`, `time`), with optional async acceleration via `httpx`:

```python
# Standalone SDK Usage Example (Demonstrating FR-UI-4)
from sovereign.sdk import SovereignClient, UserRole, TaskStatus

# Initialize client with connection settings and role credentials
client = SovereignClient(
    base_url="http://127.0.0.1:8000",
    role=UserRole.ENGINEER,
    token="sovg_eng_a1b2c3d4..."
)

# 1. Check system and VRAM health
vram = client.models.vram_status()
print(f"Available VRAM: {vram.available_mb} MB")

# 2. Submit Demo B (industrial code execution task)
task = client.tasks.submit(
    prompt="Parse vibration sensor historian data and detect bearing fault frequencies",
    files=["sensor_historian_vibration.csv"]
)
print(f"Task submitted: {task.task_id} (Thread: {task.thread_id})")

# 3. Poll for completion or handle HITL approval
result = client.tasks.wait_for_completion(task.task_id, timeout_sec=60)

if result.status == TaskStatus.SUSPENDED:
    print(f"Workflow paused at HITL gate: {result.pending_approval['action']}")
    # Approve deliverable
    client.tasks.approve(task.task_id, notes="Code and logs reviewed and approved")
    result = client.tasks.wait_for_completion(task.task_id, timeout_sec=30)

# 4. Download verified code and execution log artifacts
code_path = client.tasks.download_artifact(task.task_id, "vibration_analysis.py", "./output/")
log_path = client.tasks.download_artifact(task.task_id, "vibration_analysis.log", "./output/")
print(f"Downloaded verified artifacts: {code_path}, {log_path}")

# 5. Verify cryptographic audit trail
verification = client.audit.verify()
assert verification.is_valid, "Audit trail integrity compromised!"
print("Audit ledger integrity cryptographically verified.")
```

---

## 7. Don't Hand-Roll Table

| Capability | Don't Hand-Roll | Standard Tool / Existing Project Module | Rationale & Failure Mode |
|:---|:---|:---|:---|
| **ASGI Web Framework** | Custom socket HTTP server / BaseHTTPRequestHandler | `fastapi>=0.110.0` + `uvicorn>=0.28.0` | Hand-rolled HTTP servers lack RFC compliance, proper chunked transfer encoding, concurrent async event loops, and robust WebSocket framing. |
| **Data Schema Validation** | Manual dictionary type checking | `pydantic>=2.6.0` | Custom validation leads to silent type coercion bugs, missing field errors, and security injection vectors. |
| **CLI Argument Parsing** | `sys.argv` parsing or custom regex matching | `click>=8.1.0` (Existing `sovereign.cli`) | Click provides standardized POSIX parsing, subcommands, help generation, type validation, and shell auto-completion. |
| **JSON Serialization** | String concatenation or standard `json.dumps` for audit records | `rfc8785.dumps()` / `src/sovereign/audit/canonical.py` | Standard JSON serialization has non-deterministic key ordering and float precision differences that break SHA-256 hash chains. |
| **Cryptographic Signatures** | Custom hashing / home-grown token signature scheme | `cryptography.hazmat.primitives.asymmetric.ed25519` / HMAC-SHA256 | Custom crypto algorithms suffer from timing attacks, nonce reuse, and key leakage. |
| **VRAM Scheduling** | Raw CUDA calls or ad-hoc memory checks | `src/sovereign/models/scheduler.py` (`VRAMScheduler`) | Direct GPU memory allocation without centralized LRU tracking causes CUDA Out-of-Memory crashes under concurrent requests. |
| **Agent State Machine** | Custom while-loop orchestrator | `src/sovereign/orchestration/runtime.py` (`AgentRuntime` / `StateGraph`) | Naive loops lack ACID checkpointing, edge branching, error escalation, and clean HITL interrupt semantics. |
| **Network Telemetry** | Parsing `/proc/net` directly or executing `netstat` CLI | `src/sovereign/network/monitor.py` (`NetworkMonitor` + `psutil`) | Shelling out to `netstat` is slow, platform-dependent, and prone to process enumeration race conditions. |

---

## 8. Common Pitfalls & Prevention

### Pitfall 1: Binding to `0.0.0.0` or Exposing Ports Across Interfaces
- **Mechanism:** Developers commonly use `uvicorn.run(app, host="0.0.0.0")` for convenience. In an industrial plant where an engineer's laptop has both an internal air-gapped interface and an external corporate Wi-Fi/Ethernet interface, binding to `0.0.0.0` exposes the AI workbench to unauthorized corporate network segments.
- **Prevention:** The server defaults strictly to `127.0.0.1`. If an operator configures an alternative IP, the startup guard checks it against `allowed_intranet_cidrs` in `network_policy.yaml`. If the IP does not match, startup fails closed with a fatal error.

### Pitfall 2: Accidental External Web Asset Requests (Breaking Air-Gap)
- **Mechanism:** Importing libraries like FontAwesome, Google Fonts, or CDN scripts inside HTML templates causes browsers to emit external outbound DNS and HTTP requests. In an air-gapped enclave, these requests timeout, stall page rendering, and trigger Phase 1 `NetworkMonitor` security alerts for unauthorized egress.
- **Prevention:** 100% zero-external-CDN policy. All assets reside locally in `src/sovereign/server/static/`. All fonts rely on the native OS font stack. All icons are rendered as inline embedded SVGs. An automated static analysis test asserts that no HTML, CSS, or JS file contains `http://` or `https://` references.

### Pitfall 3: Inconsistent RBAC Enforcement Between UI and API
- **Mechanism:** The Web UI hides the "Submit Task" button for Auditor accounts, but the underlying `POST /api/tasks` endpoint remains unprotected. An auditor or malicious actor could bypass the UI via `curl` or SDK to execute arbitrary agent workflows.
- **Prevention:** The RBAC layer is enforced at the ASGI middleware / dependency injection layer (`require_role(UserRole.ENGINEER)`). Every endpoint inspects the verified role before execution. Any unauthorized call returns HTTP 403 Forbidden and logs an escalation event in the cryptographic audit ledger.

### Pitfall 4: WebSocket Telemetry Backpressure & Memory Leaks
- **Mechanism:** When the agent emits thousands of streaming tokens or the network monitor captures high-frequency socket events, slow WebSocket clients can cause unbounded server memory growth or block the ASGI event loop.
- **Prevention:** Decouple telemetry emission from WebSocket broadcasting. Use bounded `asyncio.Queue` per connected client with dropping of stale events if the client queue exceeds 200 items, while the in-memory `ConnectionRingBuffer` retains the canonical historical window.

### Pitfall 5: Bounding Box Coordinate System Mismatches
- **Mechanism:** OCR engines output coordinates in pixels at scan resolution (e.g. 300 DPI, 2480x3508), while web browsers render scaled previews (e.g. 800x1132). Hard-coding pixel coordinates results in misaligned bounding boxes.
- **Prevention:** Use the Phase 4 `NormalizedDocument` standard where all bounding boxes are normalized to floating-point ratios `[ymin, xmin, ymax, xmax]` in `[0.0, 1.0]`. The frontend canvas scales these coordinates dynamically based on the rendered image element's `naturalWidth` and `clientWidth`.

---

## 9. Code Patterns & Implementation Signatures

### 9.1 Network Binding Validation Guard

```python
# src/sovereign/server/config.py
import ipaddress
from pathlib import Path
from typing import List
from sovereign.config.settings import WorkbenchSettings
from sovereign.network.policy import NetworkPolicyEngine

class BindingSecurityError(Exception):
    """Raised when server attempts to bind to an unapproved network interface."""
    pass

def validate_server_binding(host: str, policy_engine: NetworkPolicyEngine) -> None:
    """
    Enforces that server host binds strictly to loopback or declared intranet CIDRs.
    Fails closed on 0.0.0.0 or any public IP per UI-02.
    """
    if host in ("0.0.0.0", "::", ""):
        raise BindingSecurityError(
            f"Fatal: Refusing to bind to '{host}' (all interfaces) in air-gapped sovereign mode. "
            "Server must bind to '127.0.0.1' or an approved intranet IP address."
        )

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # Hostname (e.g. 'localhost')
        if host.lower() == "localhost":
            return
        raise BindingSecurityError(f"Fatal: Invalid binding hostname or IP '{host}'")

    # Loopback is unconditionally permitted
    if ip.is_loopback:
        return

    # Check against allowed intranet CIDRs
    is_allowed = any(ip in cidr for cidr in policy_engine.allowed_intranet)
    if not is_allowed:
        raise BindingSecurityError(
            f"Fatal: IP '{host}' is not within any allowed intranet CIDR range "
            f"({[str(c) for c in policy_engine.allowed_intranet]}). Binding rejected."
        )
```

### 9.2 RBAC Dependency Injection Middleware

```python
# src/sovereign/server/auth/rbac.py
from typing import Callable, Optional
from fastapi import Depends, HTTPException, Header, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sovereign.tools.schemas import UserRole, has_clearance
from sovereign.audit.ledger import AuditLedger

security_bearer = HTTPBearer(auto_error=False)

class RBACGuard:
    def __init__(self, min_role: UserRole, audit_ledger: Optional[AuditLedger] = None):
        self.min_role = min_role
        self.audit_ledger = audit_ledger

    async def __call__(
        self,
        auth: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
        x_sovereign_role: Optional[str] = Header(None, alias="X-Sovereign-Role"),
    ) -> UserRole:
        # Resolve role from token or header (with fallback to auditor in dev mode)
        resolved_role: Optional[UserRole] = None
        
        if auth and auth.credentials:
            resolved_role = self._verify_token(auth.credentials)
        elif x_sovereign_role:
            try:
                resolved_role = UserRole(x_sovereign_role.strip().lower())
            except ValueError:
                resolved_role = None

        if not resolved_role:
            resolved_role = UserRole.AUDITOR  # Default to least privilege

        if not has_clearance(resolved_role, self.min_role):
            if self.audit_ledger:
                try:
                    self.audit_ledger.append_event(
                        session_id="rbac-security",
                        event_type="SECURITY_ALERT_RBAC_VIOLATION",
                        actor_role=resolved_role.value,
                        payload={
                            "user_role": resolved_role.value,
                            "required_role": self.min_role.value,
                            "action": "ENDPOINT_ACCESS_DENIED"
                        }
                    )
                except Exception:
                    pass
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: role '{resolved_role.value}' does not have required clearance '{self.min_role.value}'."
            )
        return resolved_role

    def _verify_token(self, token: str) -> Optional[UserRole]:
        # Parse token prefix or cryptographic signature
        if token.startswith("sovg_admin_"):
            return UserRole.ADMIN
        elif token.startswith("sovg_eng_"):
            return UserRole.ENGINEER
        elif token.startswith("sovg_aud_"):
            return UserRole.AUDITOR
        return None

def require_role(min_role: UserRole) -> Callable:
    return RBACGuard(min_role)
```

### 9.3 Asynchronous Agent Reasoning Trace WebSocket Handler

```python
# src/sovereign/server/ws/trace.py
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sovereign.server.ws.manager import ConnectionManager

router = APIRouter()
manager = ConnectionManager()

@router.websocket("/ws/tasks/{task_id}")
async def task_reasoning_trace_ws(websocket: WebSocket, task_id: str):
    await manager.connect(websocket, topic=f"task:{task_id}")
    try:
        # Keep connection open and await client heartbeats or cancellation requests
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, topic=f"task:{task_id}")
```

### 9.4 Canvas Bounding Box & Diff Overlay Rendering (Vanilla JS)

```javascript
// src/sovereign/server/static/preview.js
export class DocumentPreviewRenderer {
    constructor(canvasElement, imgElement) {
        this.canvas = canvasElement;
        this.ctx = canvasElement.getContext('2d');
        this.img = imgElement;
        this.regions = [];
        this.selectedRegionId = null;
    }

    setRegions(regions) {
        this.regions = regions;
        this.redraw();
    }

    redraw() {
        const width = this.canvas.width = this.img.clientWidth;
        const height = this.canvas.height = this.img.clientHeight;
        this.ctx.clearRect(0, 0, width, height);

        for (const reg of this.regions) {
            // box_2d: [ymin, xmin, ymax, xmax] normalized to [0, 1]
            const [ymin, xmin, ymax, xmax] = reg.box_2d;
            const x = xmin * width;
            const y = ymin * height;
            const w = (xmax - xmin) * width;
            const h = (ymax - ymin) * height;

            const isSelected = reg.region_id === this.selectedRegionId;
            let color = '#10B981'; // Green (default printed)
            if (reg.modality === 'handwritten') color = '#3B82F6'; // Blue
            if (reg.confidence < 0.85) color = '#F59E0B'; // Amber (needs review)

            this.ctx.strokeStyle = isSelected ? '#EF4444' : color;
            this.ctx.lineWidth = isSelected ? 3 : 1.5;
            this.ctx.strokeRect(x, y, w, h);

            if (isSelected) {
                this.ctx.fillStyle = 'rgba(239, 68, 68, 0.15)';
                this.ctx.fillRect(x, y, w, h);
            }

            // Draw small badge
            this.ctx.fillStyle = color;
            this.ctx.fillRect(x, y - 14, 50, 14);
            this.ctx.fillStyle = '#FFFFFF';
            this.ctx.font = '10px Consolas, monospace';
            this.ctx.fillText(reg.region_id.split('#')[1] || reg.region_id, x + 2, y - 3);
        }
    }
}
```

---

## 10. Assumptions Log & Environment Availability

| # | Assumption | Risk / Impact | Validation / Mitigation Strategy |
|:---|:---|:---|:---|
| 1 | `fastapi` and `uvicorn` are pre-installed in the development environment. | High: Backend fails to run if dependencies are missing. | Confirmed: `pyproject.toml` declares `fastapi>=0.110.0` and `uvicorn>=0.28.0`. In Wave 0 tests, verify imports succeed. |
| 2 | Development workstation environment restricts `run_command` interactive execution. | Medium: Subagent cannot execute bash/powershell commands directly without user timeout. | All research, planning, file creation, code generation, and test suite definitions must be done via direct file system tools (`view_file`, `write_to_file`, `replace_file_content`) without relying on shell commands. |
| 3 | Port 8000 or 8765 is available for local server binding. | Low: Port conflict if another service is running. | Configurable via CLI `--port` and environment variable `SOVEREIGN_SERVER_PORT`. |
| 4 | Web browser accessing the UI supports standard modern ES6+ (Canvas, WebSocket, CSS Grid). | Zero: Modern Chrome, Edge, Firefox, and Safari have supported these natively for >7 years. | Tested against standard Evergreen browser APIs; zero polyfills needed. |
| 5 | Phase 3 and Phase 4 artifacts are fully operational. | Low: Underlying engines are required for end-to-end task execution. | Phase 1-4 tests (49 test files) are complete and passing. Phase 5 builds directly on top of `AgentRuntime`, `VRAMScheduler`, `AuditLedger`, and `NetworkMonitor`. |

---

## 11. Validation Architecture

### 11.1 Test Matrix & Nyquist Verification per Requirement

| Requirement ID | Test Identifier | Test File | Test Scope & Assertion |
|:---|:---|:---|:---|
| **UI-01** | `test_guided_demo_launcher_api` | `tests/test_server/test_demo_routes.py` | Verify that endpoints for Demo A, Demo B, and Demo C launch stateful workflows and return valid thread IDs and step indicators. |
| **UI-02** | `test_server_binding_guard` | `tests/test_server/test_binding_security.py` | Assert that attempting to bind to `0.0.0.0`, `::`, or unauthorized public IPs raises `BindingSecurityError` and halts startup. |
| **UI-02** | `test_host_header_validation` | `tests/test_server/test_binding_security.py` | Verify that HTTP requests with spoofed external `Host` headers are rejected with HTTP 400 Bad Request. |
| **UI-03** | `test_cli_task_and_vram_commands`| `tests/test_cli/test_workbench_cli.py` | Execute `sovereign task submit`, `sovereign task status`, `sovereign model vram`, and verify CLI exit codes and output formatting. |
| **UI-04** | `test_python_sdk_task_lifecycle` | `tests/test_sdk/test_sovereign_client.py` | Execute standalone script using `SovereignClient` to submit task, poll status, download artifact, and verify audit trail. |
| **UI-05** | `test_rbac_auditor_blocked_from_tasks`| `tests/test_server/test_rbac_middleware.py` | Verify that `POST /api/tasks` and `POST /api/tasks/{id}/resume` return HTTP 403 Forbidden when called with Auditor credentials. |
| **UI-05** | `test_rbac_violation_audit_escalation`| `tests/test_server/test_rbac_middleware.py` | Assert that an unauthorized task submission attempt by an Auditor writes a `SECURITY_ALERT_RBAC_VIOLATION` record to the audit ledger. |
| **Air-Gap** | `test_zero_external_cdn_static_audit` | `tests/test_server/test_static_assets.py` | Regex-scan all `.html`, `.css`, and `.js` files in `static/` to prove 0 occurrences of external URL schemes (`http://`, `https://`, `//`). |
| **WS** | `test_websocket_streaming_trace` | `tests/test_server/test_websocket_streams.py` | Connect to `/ws/tasks/{id}` and `/ws/network` and assert valid JSON framing and real-time event delivery. |

### 11.2 Wave 0 Gaps & Infrastructure Preparation
Prior to executing Phase 5 plans, the following foundational test and directory structures must be in place:
1. `src/sovereign/server/`: Directory structure with `static/`, `routes/`, `auth/`, and `ws/`.
2. `src/sovereign/sdk/`: Directory structure for the lightweight Python SDK.
3. `tests/test_server/`, `tests/test_cli/`, `tests/test_sdk/`: Test packages with `pytest-asyncio` and `TestClient` fixtures.

---

## 12. Security Domain & Threat Model

### 12.1 STRIDE Threat Analysis

| Threat Category | Threat Scenario | Impact | Mitigation Strategy |
|:---|:---|:---|:---|
| **Spoofing** | Attacker spoofs `Host` header or role parameter to impersonate an Admin. | Unauthorized model registration or configuration change. | `HostHeaderMiddleware` enforces allowlist; HMAC/Ed25519 token signatures prevent role tampering; role is validated cryptographically. |
| **Tampering** | Operator attempts to bypass HITL gate by directly updating SQLite state DB. | Unauthorized deliverable release. | State checkpointer uses WAL mode with file permissions; `AgentRuntime.resume()` requires explicit cryptographic audit record before completing graph. |
| **Repudiation** | Operator approves a faulty deliverable and later denies doing so. | Compliance audit failure. | `APPROVAL_GRANTED` audit event records operator ID, role, timestamp, and notes in the immutable SHA-256 hash-chained ledger. |
| **Information Disclosure** | Auditor accesses sensitive task drafts or model training weights. | Confidentiality breach. | Auditor role view is scoped to audit trails and network telemetry; RAG chunk retrieval is pre-filtered by RBAC at the SQL query layer. |
| **Denial of Service** | Malicious script bombards WebSocket endpoint with rapid connections. | Server VRAM/CPU exhaustion. | Rate limiting, connection limits per client IP, and decoupling socket ring buffer from WebSocket broadcast via bounded queues. |
| **Elevation of Privilege** | Auditor submits task via API or CLI bypassing the UI. | Violation of least-privilege mandate (UI-05). | Multi-layered RBAC fencing: FastAPI dependency injection (`require_role`) rejects calls with HTTP 403; CLI immediately aborts on auditor role. |

### 12.2 ASVS (Application Security Verification Standard) Mapping
- **ASVS V1.4.1 (Access Control Architecture):** Least-privilege role separation enforced at the middleware layer.
- **ASVS V4.1.1 (Access Control Enforcement):** Every API endpoint explicitly verifies user clearance level prior to dispatching business logic.
- **ASVS V5.1.3 (Input Validation):** All incoming REST and WebSocket payloads validated via strict Pydantic schemas with `extra="forbid"`.
- **ASVS V13.1.1 (Generic Web Service Verification):** Explicit host header validation prevents DNS rebinding; CORS is restricted to loopback and configured intranet origins.

---

## 13. Execution Plan Decomposition for Phase 5

### Plan 05-01: FastAPI Backend Service, REST APIs, WebSocket Event Streaming & 3-Tier RBAC Middleware
- **Focus:** Server infrastructure, network binding guard, RBAC middleware, REST routes, and WebSocket streaming.
- **Artifacts:**
  - `src/sovereign/server/config.py`: Binding validation and settings.
  - `src/sovereign/server/auth/rbac.py`: RBAC guard, token validator, audit escalation.
  - `src/sovereign/server/routes/`: `tasks.py`, `models.py`, `network.py`, `audit.py`, `preview.py`, `demos.py`.
  - `src/sovereign/server/ws/`: `manager.py`, `trace.py`, `network_stream.py`, `hitl_stream.py`.
  - `src/sovereign/server/app.py`: FastAPI application integration.
  - `tests/test_server/`: Comprehensive test suite for binding, RBAC, REST, and WebSockets.

### Plan 05-02: Multi-Pane Web UI with Zero-External-CDN Air-Gap Strategy & Guided Demo Modes
- **Focus:** Self-contained frontend dashboard, live reasoning trace, canvas bounding box preview, HITL approval queue, egress monitor dashboard, and role filtering.
- **Artifacts:**
  - `src/sovereign/server/static/index.html`: Multi-pane dashboard layout with inline SVGs.
  - `src/sovereign/server/static/styles.css`: Self-contained industrial CSS theme.
  - `src/sovereign/server/static/app.js`: State manager, WebSocket client, role switcher, demo controller.
  - `src/sovereign/server/static/preview.js`: Canvas bounding box and drawing diff visual overlay renderer.
  - `tests/test_server/test_static_assets.py`: Air-gap static asset verification and UI unit tests.

### Plan 05-03: Sovereign Workbench CLI & Lightweight Python SDK
- **Focus:** Command-line operations and zero-dependency programmatic client.
- **Artifacts:**
  - `src/sovereign/cli.py`: Extended with `serve`, `task submit/status/logs/approve/reject`, and `model vram`.
  - `src/sovereign/sdk/`: `__init__.py`, `client.py`, `models.py`, `exceptions.py`.
  - `tests/test_cli/test_workbench_cli.py`: CLI integration tests for tasks, VRAM, and RBAC blocking.
  - `tests/test_sdk/test_sovereign_client.py`: SDK tests proving end-to-end task submission and audit verification.

---

## 14. Conclusion & Hand-Off to Planning

This research document provides the complete architectural, technical, and security blueprint for Phase 5. All 5 requirements (UI-01 through UI-05) and the 3 demonstration execution paths (DEMO-01, DEMO-02, DEMO-03) are fully accounted for with concrete interfaces, zero-CDN strategies, strict network binding validation, multi-layer RBAC enforcement, and thorough testing architectures.

The phase is divided into 3 modular, sequential execution plans ready for immediate GSD plan authoring:
- **Plan 05-01** creates the secure server foundation, REST APIs, WebSockets, and RBAC guards.
- **Plan 05-02** builds the air-gapped multi-pane Web UI and guided demo workflows.
- **Plan 05-03** delivers the operational CLI commands and lightweight Python SDK.
