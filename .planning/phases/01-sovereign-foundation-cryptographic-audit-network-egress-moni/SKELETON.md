# Walking Skeleton — Sovereign AI Workbench

**Phase:** 1
**Generated:** 2026-09-10

## Capability Proven End-to-End

An offline operator can execute a sovereign task that verifies file integrity via Ed25519/SHA-256 attestation, validates zero-egress network isolation against a declarative policy, records the action in an append-only canonical SHA-256 hash-chained ledger mirrored in SQLite, and emits an auditable deliverable with embedded and sidecar cryptographic lineage.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Core Runtime & Language | Python 3.11.15 | Standardized across air-gapped enterprise Linux and Windows environments; rich standard library (`hashlib`, `sqlite3`, `ipaddress`, `zipfile`, `xml.etree`). |
| Canonicalization & Hashing | RFC 8785 Canonical JSON (`rfc8785`) + SHA-256 (`hashlib`) | Produces deterministic canonical UTF-8 bytes with strict ECMAScript float formatting and UTF-16 code-unit key sorting; guarantees single-byte tamper detection across platforms. |
| Cryptographic Signatures | Ed25519 (`cryptography.hazmat.primitives.asymmetric.ed25519`) | Provides deterministic, non-malleable digital signatures immune to side-channel timing attacks; pre-compiled wheels operate 100% offline with zero external network dependencies. |
| Ground Truth Audit Ledger | Append-only JSONL (`audit_ledger.jsonl`) with advisory locking (`portalocker`) | Immutable cryptographic ground truth with sequential integer sequence numbers (0..N); process-safe atomic writes prevent file corruption. |
| Query & Mirror Storage | SQLite 3 in WAL mode (`audit_index.sqlite`) with `synchronous=NORMAL` | Zero-daemon embedded relational database providing sub-millisecond query indexing, full-text filtering, and per-session audit slice extraction without compromising the JSONL ground truth. |
| Network Boundary & Policy | Declarative YAML (`network_policy.yaml`) with Python `ipaddress` containment | Strict default-deny policy for public IP ranges and port 53 (DNS); permits loopback (`127.0.0.0/8`, `::1/128`) and declared intranet CIDRs. |
| Network Telemetry & Streaming | `psutil.net_connections` + 10,000-slot `collections.deque` ring buffer + FastAPI WebSockets | High-frequency socket telemetry is held in-memory and broadcast to real-time UI dashboards; only policy DENY events write to disk to prevent I/O thrashing. |
| Startup Attestation Protocol | Two-tier verification (`attestation_manifest.json`) | Full byte-by-byte SHA-256 on installation and cold boots; fast (<2s) file size, stat/inode, and 64MB sparse head/tail chunk hashing on warm restarts; strict fail-closed startup halt unless `--dev-mode` or `--mock-models` is active. |
| Provenance & Deliverable Lineage | W3C PROV-O sidecars (`<file>.lineage.json`) + Open Packaging Conventions (OPC) injection | Emits standalone JSON provenance graphs alongside deliverables; injects custom properties into OOXML archives (`.docx`, `.xlsx`, `.pptx`), PNG `tEXt` chunks, and script comment headers. |
| CLI Interface | Unified CLI entry point (`sovereign`) | POSIX-compliant CLI exposing five subcommands: `audit`, `network`, `attest`, `lineage`, and `test-egress`. |
| Directory Layout | `src/sovereign/{audit, network, attestation, lineage, config}/` | Modular package structure cleanly decoupling cryptographic, networking, supply chain, and lineage concerns. |

## Stack Touched in Phase 1

- [x] Project scaffold (`pyproject.toml`, pytest configuration, type annotations)
- [x] Routing & CLI (`sovereign` CLI entry point with `audit`, `network`, `attest`, `lineage`, `test-egress` subcommands and FastAPI WebSocket route `/ws/network-telemetry`)
- [x] Database & Persistence (`audit_ledger.jsonl` append-only writes, `audit_index.sqlite` WAL queries and transactions)
- [x] Telemetry & Network Guard (`psutil` socket scanner, declarative policy engine, in-memory ring buffer)
- [x] Attestation & Packaging (Ed25519 signer/verifier, 64MB chunk hasher, OOXML OPC/PNG/code lineage injectors)
- [x] Local verification — runnable test commands exercising the entire Phase 1 cryptographic and network suite.

## Out of Scope (Deferred to Later Slices)

- Multi-step LLM planning state machine and cyclical agent graph (Phase 3)
- Real GPU model weight execution, VRAM allocation, and tensor runtime adapters (Phase 2)
- Sandboxed code execution within isolated Linux cgroups/network namespaces (Phase 3)
- OCR, handwriting recognition, and engineering drawing vision diffing (Phase 4)
- Local vector database (Chroma/Qdrant/LanceDB) and RAG chunking pipelines (Phase 4)
- Multi-pane web UI frontend and user role-based web dashboard (Phase 5)
- Full end-to-end SIH demonstration workflows (Approval Note, Sandboxed Coding, Drawing Diff) (Phase 6)

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- Phase 2: Local Model Management, Adapters & VRAM Scheduler
- Phase 3: Agentic State Machine, Tool Registry & Isolated Sandbox
- Phase 4: Multimodal Ingestion, Local RAG & Native Deliverable Engines
- Phase 5: Workbench Web Interface, CLI & Role-Based Access Control
- Phase 6: SIH End-to-End Demonstration Workflows & Verification
