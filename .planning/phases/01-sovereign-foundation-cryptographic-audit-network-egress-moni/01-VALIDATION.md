---
phase: "01"
slug: "sovereign-foundation-cryptographic-audit-network-egress-moni"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-09"
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 |
| **Config file** | `pyproject.toml` (Wave 0 creates) |
| **Quick run command** | `pytest -q tests/test_audit/` |
| **Full suite command** | `pytest -v tests/` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run matching test file, e.g. `pytest -q tests/test_audit/test_hash_chain.py`
- **After every plan wave:** Run `pytest -v tests/`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | SOVG-02 | T-01-02 | RFC 8785 byte determinism, single-byte tamper detection | unit | `pytest tests/test_audit/test_hash_chain.py` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | SOVG-01 | T-01-01 | Thread/process-safe atomic append to JSONL ledger | unit | `pytest tests/test_audit/test_ledger.py` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | SOVG-01 | T-01-01 | Synchronous mirror into SQLite WAL index | unit | `pytest tests/test_audit/test_ledger_mirror.py` | ❌ W0 | ⬜ pending |
| 01-01-04 | 01 | 1 | SOVG-02, SOVG-01 | T-01-02 | CLI verifier pinpoints tamper; runtime guard halts | unit | `pytest tests/test_audit/test_audit_cli.py` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 2 | SOVG-04 | T-01-04 | Loopback & Intranet CIDR allow; external IP/DNS deny | unit | `pytest tests/test_network/test_policy_engine.py` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 2 | SOVG-03 | T-01-05 | Polling, PID resolution, 10,000 ring buffer eviction | unit | `pytest tests/test_network/test_connection_monitor.py` | ❌ W0 | ⬜ pending |
| 01-02-03 | 02 | 2 | SOVG-03, SOVG-04 | T-01-04 | WebSocket streaming; DENY writes immediately to ledger | unit | `pytest tests/test_network/test_telemetry_sink.py` | ❌ W0 | ⬜ pending |
| 01-02-04 | 02 | 2 | SOVG-04 | T-01-04 | 100% fail on DNS 53, HTTP 80/443, NTP 123, raw TCP | unit | `pytest tests/test_network/test_egress_suite.py` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 3 | SOVG-05 | T-01-06 | Ed25519 manifest generation, signing, and verification | unit | `pytest tests/test_attestation/test_ed25519_signatures.py` | ❌ W0 | ⬜ pending |
| 01-03-02 | 03 | 3 | SOVG-05 | T-01-06 | Cold full SHA-256 vs warm sparse 64MB; fail-closed | unit | `pytest tests/test_attestation/test_startup_guard.py` | ❌ W0 | ⬜ pending |
| 01-03-03 | 03 | 3 | SOVG-06 | T-01-03 | W3C PROV-O JSON sidecar generation and binding | unit | `pytest tests/test_lineage/test_lineage_engine.py` | ❌ W0 | ⬜ pending |
| 01-03-04 | 03 | 3 | SOVG-06 | T-01-03 | OPC OOXML (.docx/.xlsx/.pptx), PNG tEXt, code headers | unit | `pytest tests/test_lineage/test_format_injectors.py` | ❌ W0 | ⬜ pending |
| 01-03-05 | 03 | 3 | SOVG-06 | T-01-03 | Reverse verify & forward trace CLI commands | unit | `pytest tests/test_lineage/test_lineage_cli.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — shared fixtures and temporary ledger/policy directories
- [ ] `tests/fixtures/test_ed25519_private.pem` & `test_ed25519_public.pub` — offline Ed25519 test keypair
- [ ] `tests/fixtures/mock_qwen.bin` — 130MB sparse dummy binary for 64MB head/tail chunk test
- [ ] `tests/fixtures/minimal_templates/` — minimal `.docx`, `.xlsx`, and `.pptx` archives for OPC custom property injection
- [ ] `pyproject.toml` — project metadata and pytest configuration

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | N/A | N/A | All Phase 1 behaviors have automated pytest verification |

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
