---
phase: "01-sovereign-foundation-cryptographic-audit-network-egress-moni"
plan: "01-03"
subsystem: "attestation, lineage"
tags:
  - "ed25519"
  - "attestation"
  - "manifest-signing"
  - "sparse-hashing"
  - "lineage"
  - "prov-o"
  - "ooxml-injection"
  - "png-metadata"
  - "code-docstrings"
  - "bidirectional-verification"
requires:
  - "01-01"
  - "01-02"
provides:
  - "src/sovereign/attestation/models.py"
  - "src/sovereign/attestation/hasher.py"
  - "src/sovereign/attestation/signer.py"
  - "src/sovereign/attestation/verifier.py"
  - "src/sovereign/lineage/models.py"
  - "src/sovereign/lineage/engine.py"
  - "src/sovereign/lineage/verifier.py"
  - "src/sovereign/lineage/injectors/ooxml.py"
  - "src/sovereign/lineage/injectors/png.py"
  - "src/sovereign/lineage/injectors/code.py"
affects: []
tech-stack:
  added:
    - "cryptography (Ed25519)"
    - "rfc8785"
    - "Pillow (PngImagePlugin)"
    - "zipfile (stdlib)"
    - "xml.etree.ElementTree (stdlib)"
  patterns:
    - "Ed25519 manifest signing over RFC 8785 canonical bytes"
    - "Two-tier startup attestation: full SHA-256 cold boot + 64MB sparse chunk warm restart"
    - "Fail-closed halt (exit 1) on tamper with --dev-mode / --mock-models bypass"
    - "W3C PROV-O inspired lineage metadata schema with audit ledger sequence span binding"
    - "Dual packaging: sibling .lineage.json sidecar + format-native embedded metadata"
    - "OPC custom properties injection for OOXML (.docx/.xlsx/.pptx) via stdlib only"
    - "PNG tEXt chunk injection via Pillow for image deliverables"
    - "Python/Shell docstring and comment header injection for code deliverables"
    - "Bidirectional lineage CLI: reverse verify + forward provenance trace"
key-files:
  created:
    - "src/sovereign/attestation/__init__.py"
    - "src/sovereign/attestation/models.py"
    - "src/sovereign/attestation/hasher.py"
    - "src/sovereign/attestation/signer.py"
    - "src/sovereign/attestation/verifier.py"
    - "src/sovereign/lineage/__init__.py"
    - "src/sovereign/lineage/models.py"
    - "src/sovereign/lineage/engine.py"
    - "src/sovereign/lineage/verifier.py"
    - "src/sovereign/lineage/injectors/__init__.py"
    - "src/sovereign/lineage/injectors/ooxml.py"
    - "src/sovereign/lineage/injectors/png.py"
    - "src/sovereign/lineage/injectors/code.py"
    - "tests/fixtures/test_ed25519_private.pem"
    - "tests/fixtures/test_ed25519_public.pub"
    - "tests/fixtures/mock_qwen.bin"
    - "tests/fixtures/minimal_templates/template.docx"
    - "tests/fixtures/minimal_templates/template.xlsx"
    - "tests/fixtures/minimal_templates/template.pptx"
    - "tests/test_attestation/test_ed25519_signatures.py"
    - "tests/test_attestation/test_sparse_chunk_hashing.py"
    - "tests/test_attestation/test_startup_guard.py"
    - "tests/test_lineage/test_prov_schema.py"
    - "tests/test_lineage/test_format_injectors.py"
    - "tests/test_lineage/test_lineage_cli.py"
  modified:
    - "src/sovereign/cli.py"
key-decisions:
  - "D-09: Signed JSON Manifest with SHA-256 Hashes & Ed25519 Signature (attestation_manifest.json)"
  - "D-10: Strict Fail-Closed in Production with Explicit --dev-mode / --mock-models Bypass"
  - "D-11: Two-Tier Verification: Full SHA-256 on Install/First Boot + 64MB Sparse Chunk Hashing on Warm Restarts"
  - "D-12: Built-in Workbench CLI Commands (sovereign attest generate / verify / sign, sovereign lineage verify / trace)"
  - "D-13: Dual Packaging: Sidecar JSON Manifest (<filename>.lineage.json) + Embedded Office Custom Properties"
  - "D-14: Comprehensive Auditable Lineage Schema (W3C PROV-O inspired with Entities, Activities, Agents, and Relations)"
  - "D-15: Bidirectional Lineage CLI (sovereign lineage verify <file> & sovereign lineage trace <file>)"
  - "D-16: Uniform Sidecar Manifest + Format-Native Comment/Header Injections (.py/.sh headers, .png tEXt chunks)"
requirements-completed:
  - "SOVG-05"
  - "SOVG-06"
duration: "35 min"
completed: "2026-09-10T13:30:00Z"
coverage:
  - deliverable: "Ed25519 manifest signing and verification over RFC 8785 canonical bytes"
    verification:
      kind: "pytest"
      ref: "tests/test_attestation/test_ed25519_signatures.py"
      status: "pass"
    human_judgment: false
  - deliverable: "64MB sparse head/tail chunk hashing for large model binaries (<200ms)"
    verification:
      kind: "pytest"
      ref: "tests/test_attestation/test_sparse_chunk_hashing.py"
      status: "pass"
    human_judgment: false
  - deliverable: "Two-tier startup attestation guard with fail-closed halt and --dev-mode bypass"
    verification:
      kind: "pytest"
      ref: "tests/test_attestation/test_startup_guard.py"
      status: "pass"
    human_judgment: false
  - deliverable: "W3C PROV-O inspired lineage metadata schema with PROV-JSON export"
    verification:
      kind: "pytest"
      ref: "tests/test_lineage/test_prov_schema.py"
      status: "pass"
    human_judgment: false
  - deliverable: "Format-native metadata injection across OOXML (.docx/.xlsx/.pptx), PNG, and Python/Shell"
    verification:
      kind: "pytest"
      ref: "tests/test_lineage/test_format_injectors.py"
      status: "pass"
    human_judgment: false
  - deliverable: "Bidirectional lineage verification CLI (verify + trace) with audit ledger span checking"
    verification:
      kind: "pytest"
      ref: "tests/test_lineage/test_lineage_cli.py"
      status: "pass"
    human_judgment: false
---

# Phase 01 Plan 03: Startup Attestation & Deliverable Lineage Packaging Summary

## One-Liner
Ed25519-signed startup attestation with two-tier integrity checks, W3C PROV-O lineage metadata engine with format-native injection across Office/PNG/code files, and bidirectional CLI verification and forward provenance tracing.

## Accomplishments

### Task 01-03-01: Startup Attestation Engine & CLI
1. **Ed25519 Manifest Signer:** Implemented `generate_manifest`, `sign_manifest`, and `verify_manifest_signature` in `src/sovereign/attestation/signer.py` using `cryptography` Ed25519 over RFC 8785 canonical bytes.
2. **Two-Tier Hasher:** Implemented `hash_full_file` and `hash_sparse_chunks` in `src/sovereign/attestation/hasher.py`. For files >64MB, independently hashes the first and last 64MB chunks with SHA-256, completing in <200ms on standard drives.
3. **Fail-Closed Attestation Guard:** Implemented `AttestationGuard` in `src/sovereign/attestation/verifier.py` executing full byte-by-byte SHA-256 on cold boot and sparse 64MB chunk checks on warm restarts. Halts with exit code 1 on any tamper unless `--dev-mode` or `--mock-models` is explicitly set.
4. **CLI Commands:** Extended `src/sovereign/cli.py` with `sovereign attest generate`, `sovereign attest sign`, and `sovereign attest verify` subcommands.

### Task 01-03-02: W3C PROV-O Lineage Models & Format Injectors
5. **Lineage Schema:** Implemented `LineageMetadata`, `DeliverableInfo`, `ModelInfo`, `SourceDocumentCitation`, and `ToolExecutionRecord` in `src/sovereign/lineage/models.py` with full W3C PROV-O export (`to_prov_o()`) covering Entities, Activities, Agents, wasGeneratedBy, wasAttributedTo, used, and wasDerivedFrom relations. Includes `audit_start_seq`..`audit_end_seq` and `audit_tip_hash` binding.
6. **OOXML Injector:** Implemented `inject_ooxml_lineage` and `extract_ooxml_lineage` in `src/sovereign/lineage/injectors/ooxml.py` using pure stdlib `zipfile` and `xml.etree.ElementTree`. Constructs well-formed `docProps/custom.xml` with proper namespace, `fmtid`, and sequential `pid`, updates `[Content_Types].xml` and `_rels/.rels`.
7. **PNG Injector:** Implemented `inject_png_lineage` and `extract_png_lineage` in `src/sovereign/lineage/injectors/png.py` using Pillow `PngInfo` to embed `sovereign_lineage` tEXt chunks.
8. **Code Injector:** Implemented `inject_code_lineage` and `extract_code_lineage` in `src/sovereign/lineage/injectors/code.py` embedding standardized docstring headers (Python `"""..."""`) and comment blocks (Shell `# --- ... ---`) with lineage key-value pairs.
9. **Packaging Engine:** Implemented `LineageEngine.package_deliverable` in `src/sovereign/lineage/engine.py` which injects format-native metadata, computes final SHA-256, and writes sibling `<file>.lineage.json` sidecar manifests.

### Task 01-03-03: Lineage Verifier & CLI Commands
10. **Bidirectional Verifier:** Implemented `LineageVerifier` in `src/sovereign/lineage/verifier.py` with `verify_lineage` (reverse: deliverable SHA-256 + sidecar + embedded metadata + audit span) and `trace_provenance` (forward: find all downstream deliverables derived from a source hash).
11. **CLI Commands:** Extended `src/sovereign/cli.py` with `sovereign lineage verify <file>` and `sovereign lineage trace <hash-or-file>` with human-readable output tables and proper exit codes.

## Verification Results
- 23 passed tests across 6 test files:
  - `tests/test_attestation/test_ed25519_signatures.py`: 2 passed
  - `tests/test_attestation/test_sparse_chunk_hashing.py`: 3 passed
  - `tests/test_attestation/test_startup_guard.py`: 4 passed
  - `tests/test_lineage/test_prov_schema.py`: 2 passed
  - `tests/test_lineage/test_format_injectors.py`: 9 passed (7 format injectors + 2 engine)
  - `tests/test_lineage/test_lineage_cli.py`: 5 passed
- Cumulative Phase 1 test suite: **66 passed** tests in 5.75s.

## Deviations from Plan
None — plan executed exactly as written across all three tasks.

## Self-Check: PASSED
- Ed25519 manifest signing over RFC 8785 canonical bytes: Verified
- Two-tier 64MB sparse chunk hashing under 200ms: Verified
- Fail-closed startup halt on tamper detection: Verified
- W3C PROV-O lineage schema with PROV-JSON export: Verified
- OOXML custom property round-trip injection (.docx/.xlsx/.pptx): Verified
- PNG tEXt chunk round-trip injection: Verified
- Python and Shell docstring header round-trip injection: Verified
- Lineage packaging engine with sidecar and native injection: Verified
- Bidirectional CLI verification (verify + trace): Verified
- Audit ledger sequence span verification: Verified
