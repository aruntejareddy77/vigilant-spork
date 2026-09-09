# Phase 1: Sovereign Foundation, Cryptographic Audit & Network Egress Monitoring - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-09
**Phase:** 01-sovereign-foundation-cryptographic-audit-network-egress-monitoring
**Areas discussed:** Audit Ledger Architecture & Hash-Chaining Format, Network Egress Monitoring & Cross-Platform Execution, Startup Attestation & Checksum Verification Protocol, Deliverable Lineage Metadata & Traceability Packaging

---

## Audit Ledger Architecture & Hash-Chaining Format

### Q1: Storage Architecture
| Option | Description | Selected |
|--------|-------------|----------|
| Dual Storage: Append-Only JSONL Ledger + SQLite Query Mirror | JSONL serves as immutable cryptographic ground truth for verification, while SQLite mirrors events for fast search, filtering, and UI queries. | ✓ |
| Pure Append-Only JSONL Ledger | Minimal and zero-database dependency; entries streamed directly to disk and verified via linear SHA-256 pass. | |
| Embedded SQLite Database Only | Uses SQLite with schema constraints and hash-chaining stored in table columns. Relational queries out of the box, but binary SQLite files are harder to inspect with basic CLI tools. | |
| You decide | Captured agent discretion. | |

**User's choice:** Dual Storage: Append-Only JSONL Ledger + SQLite Query Mirror
**Notes:** Provides both compliance proof (human-readable raw stream) and UI performance (fast indexing).

### Q2: Hash Chaining Formula
| Option | Description | Selected |
|--------|-------------|----------|
| Strict RFC 8785 Canonical JSON Hashing | Calculate SHA-256 over exact canonical JSON (deterministic key sort, normalized whitespace) containing: previous_hash, seq_num, timestamp_iso, session_id, event_type, actor_role, and payload. | ✓ |
| Header + Payload Digest Chaining | Hash consists of SHA-256(previous_hash || timestamp || event_type || sha256(raw_payload_bytes)), isolating payload hashing from ledger envelope metadata. | |
| You decide | Captured agent discretion. | |

**User's choice:** Strict RFC 8785 Canonical JSON Hashing
**Notes:** Establishes rigorous mathematical determinism for cryptographic audit verification.

### Q3: Ledger Partitioning Structure
| Option | Description | Selected |
|--------|-------------|----------|
| Continuous Global Ledger with Session-Tagged Streams | Single monolithic append-only JSONL ledger (0..N) providing unbroken global tamper verification, with session_id tags allowing the CLI and UI to extract standalone per-session audit slices. | ✓ |
| Strictly Per-Session Ledgers with Master Root Index | Each workflow session writes its own isolated hash-chain file; an umbrella master index chains the session termination hashes. | |
| Periodic Epoch-Rotated Chains | Chains rotate daily/weekly with each new epoch's genesis block committing the SHA-256 hash of the prior epoch's terminal block. | |
| You decide | Captured agent discretion. | |

**User's choice:** Continuous Global Ledger with Session-Tagged Streams
**Notes:** Preserves end-to-end unbroken chain while allowing sliced export.

### Q4: Audit Verification Behavior
| Option | Description | Selected |
|--------|-------------|----------|
| Both: Comprehensive CLI Verifier + Runtime Guard | The CLI outputs exact corrupted sequence numbers, diffs, and timestamps; the runtime verifies the ledger tip hash on startup and before writing, aborting if tampered. | ✓ |
| Standalone Offline CLI Verifier Only | Keep runtime append lightweight without read-before-write checks; verification is executed purely on-demand or during scheduled compliance audits. | |
| You decide | Captured agent discretion. | |

**User's choice:** Both: Comprehensive CLI Verifier + Runtime Guard
**Notes:** Combines active runtime defense with in-depth auditor diagnostics.

---

## Network Egress Monitoring & Cross-Platform Execution

### Q1: Cross-Platform Strategy
| Option | Description | Selected |
|--------|-------------|----------|
| Layered Strategy: Native Linux Kernel (eBPF/iptables) for Production + Cross-Platform Socket/psutil Monitor for Dev/Windows | Full kernel-level drop & eBPF telemetry in Linux containers, paired with a portable Python socket/connection telemetry monitor and synthetic egress test harness that runs natively on Windows/macOS. | ✓ |
| Container/WSL2 Strict Requirement | Require Docker / Linux containers (or WSL2) for any network monitoring and default-deny tests; no native Windows socket emulation. | |
| Application-Level Socket Monkey-Patching / Proxy | Intercept outbound network calls within the Python runtime process space, backed by OS firewall rules only when running on Linux with elevated privileges. | |
| You decide | Captured agent discretion. | |

**User's choice:** Layered Strategy: Native Linux Kernel (eBPF/iptables) for Production + Cross-Platform Socket/psutil Monitor for Dev/Windows
**Notes:** Essential for local development on Windows while supporting production air-gapped Linux deployment.

### Q2: Default-Deny Policy Scope
| Option | Description | Selected |
|--------|-------------|----------|
| Declarative Network Policy (network_policy.yaml) defaulting to Localhost + Configurable Intranet CIDR | Loopback (127.0.0.1, ::1) is always allowed for internal IPC/services; intranet LAN access is allowed via explicit CIDR declaration; all public internet IP ranges and external DNS (port 53) are strictly denied. | ✓ |
| Strict Localhost-Only (127.0.0.1) with No Intranet | Only loopback sockets are permitted; multi-machine intranet UI/client access is disabled by default until an admin unlocks it. | |
| You decide | Captured agent discretion. | |

**User's choice:** Declarative Network Policy (network_policy.yaml) defaulting to Localhost + Configurable Intranet CIDR
**Notes:** Gives administrators structured control over intranet client boundaries.

### Q3: Network Telemetry Streaming & Storage
| Option | Description | Selected |
|--------|-------------|----------|
| Fast In-Memory Ring Buffer + WebSocket Streaming + Audit Ledger Sink on Deny | High-frequency network connection telemetry is held in a 10,000-event circular ring buffer for real-time UI/CLI streaming, while any DENY or anomalous connection attempt is immediately escalated and permanently written to the SHA-256 audit ledger. | ✓ |
| Dedicated Append-Only Network Event Log File (network_events.jsonl) | Stream all network events directly to a flat JSONL log file; the dashboard and CLI tail this file. | |
| SQLite Network Events Table | Store all connection records in a dedicated local SQLite database with indexing on process ID, destination IP, and outcome. | |
| You decide | Captured agent discretion. | |

**User's choice:** Fast In-Memory Ring Buffer + WebSocket Streaming + Audit Ledger Sink on Deny
**Notes:** Prevents high-frequency I/O thrashing while ensuring tamper-proof logging of security violations.

### Q4: Egress Test Harness Design
| Option | Description | Selected |
|--------|-------------|----------|
| Comprehensive Multi-Protocol Egress Test Suite (DNS, HTTP/S, NTP, Raw TCP) | An automated test harness (sovereign test-egress) attempts external connections across DNS (UDP 53), HTTP/S (TCP 80/443), NTP (UDP 123), and arbitrary raw sockets, verifying that 100% fail, the monitor logs DENY events, and the audit ledger captures security alerts. | ✓ |
| Simple HTTP/HTTPS Probe Only | Test harness checks only outbound web requests to external IP addresses and domains. | |
| Multi-Protocol Suite + Optional Continuous Background Canary | Multi-protocol test suite for CI/verification, plus an optional background thread that attempts a canary egress probe every 5 minutes. | |
| You decide | Captured agent discretion. | |

**User's choice:** Comprehensive Multi-Protocol Egress Test Suite (DNS, HTTP/S, NTP, Raw TCP)
**Notes:** Provides bulletproof empirical demonstration for hackathon judges and security compliance officers.

---

## Startup Attestation & Checksum Verification Protocol

### Q1: Attestation Manifest Format
| Option | Description | Selected |
|--------|-------------|----------|
| Signed JSON Manifest with SHA-256 Hashes & Ed25519 Signature | ttestation_manifest.json catalogs file paths, file sizes, and SHA-256 hashes for model weights, binaries, and core scripts, signed with an offline Ed25519 private key during packaging and validated at runtime against an embedded trusted public key. | ✓ |
| Standard sha256sum Checksum File (No Asymmetric Signature) | Simple text file (checksums.sha256) containing SHA-256 hashes and file paths, verified with standard sha256sum -c semantics. | |
| GPG/OpenPGP Detached Signature Manifest | JSON manifest paired with a detached .sig or .asc GPG signature verified using local GPG keyring. | |
| You decide | Captured agent discretion. | |

**User's choice:** Signed JSON Manifest with SHA-256 Hashes & Ed25519 Signature
**Notes:** Clean, modern asymmetric cryptography without GPG daemon dependencies.

### Q2: Attestation Fail-Closed Behavior
| Option | Description | Selected |
|--------|-------------|----------|
| Strict Fail-Closed in Production with Explicit --dev-mode / --mock-models Bypass | By default, any missing file, size mismatch, or checksum failure immediately halts startup (exit 1) and logs a tamper alert. When --dev-mode or --mock-models is passed, missing model weights emit audit warnings and fall back to deterministic mock adapters. | ✓ |
| Strict Fail-Closed Everywhere (No Bypass) | Startup strictly aborts if any model file or binary in the manifest is missing or altered. | |
| Permissive Audit-Only Mode | Discrepancies are logged as critical audit events, but the service attempts to continue running. | |
| You decide | Captured agent discretion. | |

**User's choice:** Strict Fail-Closed in Production with Explicit --dev-mode / --mock-models Bypass
**Notes:** Ensures zero security compromise in production while enabling rapid developer testing without 50GB model files.

### Q3: Large File Verification Optimization
| Option | Description | Selected |
|--------|-------------|----------|
| Two-Tier Verification: Full SHA-256 on Install/First Boot + Inode/Stat Guard with Sparse Chunk Hashing on Warm Restarts | Full byte-by-byte SHA-256 on initial install/package verify and on explicit --full-attest runs; fast warm boot verifies file size, mtime/inode, plus first/last 64MB hash chunks to boot in under 2 seconds. | ✓ |
| Always Full Byte-by-Byte SHA-256 | Hash 100% of all model weights on every single service start, prioritizing absolute compliance proof over startup latency. | |
| Asynchronous Background Attestation | Core services and UI start immediately; large model files are hashed in a background thread. | |
| You decide | Captured agent discretion. | |

**User's choice:** Two-Tier Verification: Full SHA-256 on Install/First Boot + Inode/Stat Guard with Sparse Chunk Hashing on Warm Restarts
**Notes:** Delivers instant cold/warm restarts without sacrificing cryptographic integrity.

### Q4: Attestation Tooling & Management
| Option | Description | Selected |
|--------|-------------|----------|
| Built-in Workbench CLI Commands (sovereign attest generate / sovereign attest verify / sovereign attest sign) | Native subcommands in the CLI for hashing files, signing manifests, and performing audits, usable both programmatically in CI/CD and by on-prem system administrators. | ✓ |
| Standalone Stand-alone Script (scripts/build_attestation.py) | Lightweight standalone utility script kept outside the core application codebase. | |
| You decide | Captured agent discretion. | |

**User's choice:** Built-in Workbench CLI Commands (sovereign attest generate / sovereign attest verify / sovereign attest sign)
**Notes:** Single cohesive developer and admin experience.

---

## Deliverable Lineage Metadata & Traceability Packaging

### Q1: Lineage Packaging Format
| Option | Description | Selected |
|--------|-------------|----------|
| Dual Packaging: Sidecar JSON Manifest (<filename>.lineage.json) + Embedded Office Custom Properties | Every output file gets a sibling <filename>.lineage.json with the full cryptographic lineage graph; Office documents (.docx, .xlsx, .pptx) additionally embed core provenance tags directly into their standard OOXML document properties. | ✓ |
| Standalone Sidecar JSON Manifest Only (<filename>.lineage.json) | All provenance data resides strictly in an adjacent JSON metadata file in /local/output, keeping binary deliverable files completely untouched. | |
| Embedded Document Metadata Only | Store metadata solely inside document properties; no sidecar files. | |
| You decide | Captured agent discretion. | |

**User's choice:** Dual Packaging: Sidecar JSON Manifest (<filename>.lineage.json) + Embedded Office Custom Properties
**Notes:** Enables automated verification via sidecar and built-in human inspection in Office applications.

### Q2: Lineage Schema Depth
| Option | Description | Selected |
|--------|-------------|----------|
| Comprehensive Auditable Lineage Schema (W3C PROV-O inspired) | Captures deliverable SHA-256, session ID, user identity/role, model identity & weights SHA-256, source input documents (with file SHA-256 and page/bounding-box citation coordinates), tool execution trace with inputs/outputs, and exact audit ledger sequence span & tip hash. | ✓ |
| Lightweight Lineage Schema | Captures deliverable hash, model identifier, list of source document filenames, execution timestamp, and session ID without granular bounding boxes or intermediate tool hashes. | |
| You decide | Captured agent discretion. | |

**User's choice:** Comprehensive Auditable Lineage Schema (W3C PROV-O inspired)
**Notes:** Fully satisfies the highest enterprise and regulatory audit standards.

### Q3: Lineage Verification CLI
| Option | Description | Selected |
|--------|-------------|----------|
| Bidirectional Lineage CLI (sovereign lineage verify <file> & sovereign lineage trace <file>) | Reverse verification confirms deliverable SHA-256, validates sidecar metadata, and proves inclusion in the cryptographic audit ledger; forward trace finds all deliverables derived from a specific input document or model weights hash. | ✓ |
| Unidirectional Verification Only (sovereign verify-output <file>) | Checks that the deliverable file hash matches its sidecar manifest and validates that the sidecar hash matches the entry in the audit log. | |
| You decide | Captured agent discretion. | |

**User's choice:** Bidirectional Lineage CLI (sovereign lineage verify <file> & sovereign lineage trace <file>)
**Notes:** Allows auditors to ask both Where did this file come from? and What was produced from this sensitive input?.

### Q4: Non-Office Deliverable Lineage
| Option | Description | Selected |
|--------|-------------|----------|
| Uniform Sidecar Manifest + Format-Native Comment/Header Injections | Every single artifact receives its sibling <file>.lineage.json; generated code (.py/.sh) embeds a standardized header docstring with lineage IDs; generated images (.png) embed a PNG tEXt chunk with lineage summary. | ✓ |
| Strict Sidecar Manifest Only (Zero In-File Injections) | Never inject comments or metadata into code or image binaries; all non-Office lineage is strictly contained in the adjacent .lineage.json file. | |
| You decide | Captured agent discretion. | |

**User's choice:** Uniform Sidecar Manifest + Format-Native Comment/Header Injections
**Notes:** Ensures code scripts and images retain embedded identity even when moved outside /local/output.

---

## the agent's Discretion
None — all options were explicitly chosen by the user.

## Deferred Ideas
None.
