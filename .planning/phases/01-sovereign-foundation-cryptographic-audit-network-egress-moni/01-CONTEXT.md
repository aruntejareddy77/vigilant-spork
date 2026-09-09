# Phase 1: Sovereign Foundation, Cryptographic Audit & Network Egress Monitoring - Context

**Gathered:** 2026-09-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish verifiable host/container zero-egress isolation, real-time connection telemetry, tamper-evident hash-chained audit logging, startup binary attestation, and deliverable lineage metadata generation. This phase provides the core security and observability foundation upon which all subsequent model management, agent orchestration, and deliverable pipelines depend.
</domain>

<decisions>
## Implementation Decisions

### Audit Ledger Architecture & Hash-Chaining Format
- **D-01:** Dual Storage: Append-Only JSONL Ledger (udit_ledger.jsonl) + SQLite Query Mirror (udit_index.sqlite). JSONL serves as the immutable cryptographic ground truth for verification, while SQLite mirrors events for fast search, filtering, and UI queries. — **Reversibility:** one-way — Changing the ground-truth ledger storage format later would require migrating the cryptographic verification chain and audit parser contracts.
- **D-02:** Strict RFC 8785 Canonical JSON Hashing. SHA-256 is calculated over exact canonical JSON (deterministic key sort, normalized whitespace) containing: previous_hash, seq_num, 	imestamp_iso, session_id, event_type, ctor_role, and payload. — **Reversibility:** one-way — Any modification to the serialization rules invalidates historical hash chains.
- **D-03:** Continuous Global Ledger with Session-Tagged Streams. Single monolithic append-only JSONL ledger (0..N sequence numbers) providing unbroken global tamper verification across system lifetime, with session_id tags enabling extraction of standalone per-session audit slices. — **Reversibility:** costly — Impacts audit log rotation policies and session extraction utilities.
- **D-04:** Dual Verifier & Runtime Guard. Comprehensive CLI Verifier (sovereign audit verify) pinpoints corrupted sequence numbers, diffs, and timestamps; Runtime Guard verifies the ledger tip hash on startup and before writing, aborting if tampered. — **Reversibility:** reversible — Diagnostics and verification triggers can be enhanced without altering stored log formats.

### Network Egress Monitoring & Cross-Platform Execution
- **D-05:** Layered Strategy: Native Linux Kernel (eBPF/Tetragon & iptables) for Production + Cross-Platform Socket/psutil Monitor for Dev/Windows. Full kernel-level drop & eBPF telemetry in Linux containers, paired with a portable Python socket/connection telemetry monitor and synthetic egress test harness that runs natively on Windows/macOS. — **Reversibility:** costly — Subsystems across container manifests, OS scripts, and Python runtime depend on this dual-mode design.
- **D-06:** Declarative Network Policy (
etwork_policy.yaml) defaulting to Localhost + Configurable Intranet CIDR. Loopback (127.0.0.1, ::1) is always allowed for internal IPC/services; intranet LAN access (e.g. 10.0.0.0/8, 192.168.0.0/16) is allowed via explicit CIDR declaration; all public internet IP ranges and external DNS (port 53) are strictly denied. — **Reversibility:** reversible — Policy CIDR lists and port mappings are configurable at runtime.
- **D-07:** Fast In-Memory Ring Buffer + WebSocket Streaming + Audit Ledger Sink on Deny. High-frequency network connection telemetry is held in a 10,000-event circular ring buffer for real-time UI/CLI streaming, while any DENY or anomalous connection attempt is immediately escalated and permanently written to the SHA-256 audit ledger. — **Reversibility:** reversible — Buffer size and streaming protocols can be tuned independently of the audit logger.
- **D-08:** Comprehensive Multi-Protocol Egress Test Suite (sovereign test-egress). Automated test harness attempts external connections across DNS (UDP 53), HTTP/S (TCP 80/443), NTP (UDP 123), and arbitrary raw sockets, verifying that 100% fail, the monitor logs DENY events, and the audit ledger captures security alerts. — **Reversibility:** reversible — Test suites and simulated probes can be extended as new protocols are tested.

### Startup Attestation & Checksum Verification Protocol
- **D-09:** Signed JSON Manifest with SHA-256 Hashes & Ed25519 Signature. ttestation_manifest.json catalogs file paths, file sizes, and SHA-256 hashes for model weights, binaries, and core scripts, signed with an offline Ed25519 private key during packaging and validated at runtime against an embedded trusted public key. — **Reversibility:** one-way — Changing cryptographic signing schemes or key infrastructure impacts deployment packaging and release verification.
- **D-10:** Strict Fail-Closed in Production with Explicit --dev-mode / --mock-models Bypass. By default, any missing file, size mismatch, or checksum failure immediately halts startup (exit 1) and logs a tamper alert. When --dev-mode or --mock-models is passed, missing model weights emit audit warnings and fall back to deterministic mock adapters. — **Reversibility:** reversible — Startup guard evaluation flags can be adjusted in configuration.
- **D-11:** Two-Tier Verification: Full SHA-256 on Install/First Boot + Inode/Stat Guard with Sparse Chunk Hashing on Warm Restarts. Full byte-by-byte SHA-256 on initial install/package verify and on explicit --full-attest runs; fast warm boot verifies file size, mtime/inode, plus first/last 64MB hash chunks to boot in under 2 seconds. — **Reversibility:** reversible — Caching heuristics can be tuned based on disk throughput.
- **D-12:** Built-in Workbench CLI Commands (sovereign attest generate / sovereign attest verify / sovereign attest sign). Native subcommands in the CLI for hashing files, signing manifests, and performing audits, usable both programmatically in CI/CD and by on-prem system administrators. — **Reversibility:** reversible — CLI interfaces and command arguments follow standard CLI patterns.

### Deliverable Lineage Metadata & Traceability Packaging
- **D-13:** Dual Packaging: Sidecar JSON Manifest (<filename>.lineage.json) + Embedded Office Custom Properties. Every output file gets a sibling <filename>.lineage.json with the full cryptographic lineage graph; Office documents (.docx, .xlsx, .pptx) additionally embed core provenance tags directly into their standard OOXML document properties. — **Reversibility:** one-way — Establishing the deliverable contract and metadata schema creates expectation for all downstream generators and viewers.
- **D-14:** Comprehensive Auditable Lineage Schema (W3C PROV-O inspired). Captures deliverable SHA-256, session ID, user identity/role, model identity & weights SHA-256, source input documents (with file SHA-256 and page/bounding-box citation coordinates), tool execution trace with inputs/outputs, and exact audit ledger sequence span & tip hash. — **Reversibility:** costly — Downstream generators in Phase 4 and Phase 6 depend on this metadata structure.
- **D-15:** Bidirectional Lineage CLI (sovereign lineage verify <file> & sovereign lineage trace <file>). Reverse verification confirms deliverable SHA-256, validates sidecar metadata, and proves inclusion in the cryptographic audit ledger; forward trace finds all deliverables derived from a specific input document or model weights hash. — **Reversibility:** reversible — Search and traversal queries can be expanded without breaking stored metadata.
- **D-16:** Uniform Sidecar Manifest + Format-Native Comment/Header Injections. Every artifact receives its sibling <file>.lineage.json; generated code (.py/.sh) embeds a standardized header docstring with lineage IDs; generated images (.png) embed a PNG tEXt chunk with lineage summary. — **Reversibility:** reversible — Header comment injection formatting is isolated to deliverable serializer writers.

### the agent's Discretion
None — all 16 key technical decisions were explicitly discussed and resolved with the user.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Functional Specifications & Requirements
- Sovereign_AI_Workbench_PRD.md §3 — Goals and Measurable Success Metrics (zero egress, 100% audit log actions, attestation coverage)
- Sovereign_AI_Workbench_PRD.md §5.1 — MVP Features (deployment, sovereignty verification, audit log, network monitor)
- Sovereign_AI_Workbench_PRD.md §6.6 — Auditability and Sovereignty Proofing requirements (FR-AS-1 through FR-AS-6)
- .planning/REQUIREMENTS.md §Sovereignty Verification & Auditability (SOVG) — Requirements SOVG-01 to SOVG-06

### Technical Architecture & Reference Implementation
- Air-Gapped Industrial AI Workbench.md §1 — Air-Gapped Architecture and Logical Isolation (iptables/nftables default-deny rules, container networking)
- Air-Gapped Industrial AI Workbench.md §2 — Zero-Egress Network Monitoring and Observability (eBPF Tetragon process attribution, sys_enter_connect interception)
- Air-Gapped Industrial AI Workbench.md §3 — Security, Supply-Chain Provenance, and Auditing (Ed25519/SHA-256 attestation, RFC 8785 canonical JSON hash-chained audit ledger)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Greenfield repository. No legacy code components to reuse.
- Documentation authority established: Sovereign_AI_Workbench_PRD.md and Air-Gapped Industrial AI Workbench.md.

### Established Patterns
- High-integrity cryptographic design: SHA-256 hash chaining, RFC 8785 canonical serialization, Ed25519 digital signatures.
- Dual-tier architecture: In-memory/local SQLite fast queries backed by immutable JSONL cryptographic ground truth.
- Cross-platform operational parity: Linux kernel-level enforcement (eBPF/iptables) in production containers paired with portable socket/psutil monitoring for Windows/local developer testing.

### Integration Points
- /local/output directory for generated deliverables and <filename>.lineage.json sidecar manifests.
- Root or runtime data directory for udit_ledger.jsonl, udit_index.sqlite, and 
etwork_policy.yaml.
- CLI binary/module entry point (sovereign) providing udit, 
etwork, ttest, and lineage subcommands.
</code_context>

<specifics>
## Specific Ideas
- SIH evaluation relies heavily on visible empirical demonstration of sovereignty: the network monitor must visually display 0 permitted external connections, and the synthetic test command (sovereign test-egress) must deterministically prove denial across DNS, HTTP, NTP, and TCP.
- Tamper detection should be demonstrably testable by modifying a single byte in udit_ledger.jsonl and seeing sovereign audit verify immediately pinpoint the tampered record and break the chain.
</specifics>

<deferred>
## Deferred Ideas
None — discussion stayed strictly within Phase 1 sovereign foundation scope.
</deferred>

---

*Phase: 01-sovereign-foundation-cryptographic-audit-network-egress-monitoring*
*Context gathered: 2026-09-09*
