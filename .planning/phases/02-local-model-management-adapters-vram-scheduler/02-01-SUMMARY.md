---
phase: "02-local-model-management-adapters-vram-scheduler"
plan: "02-01"
subsystem: "models"
tags:
  - "model-manifest"
  - "pluggable-adapters"
  - "model-registry"
  - "hot-registration"
  - "cli"
requires:
  - "01-01"
  - "01-02"
  - "01-03"
provides:
  - "src/sovereign/models/manifest.py"
  - "src/sovereign/models/types.py"
  - "src/sovereign/models/adapter.py"
  - "src/sovereign/models/registry.py"
affects:
  - "02-02-PLAN.md"
  - "02-03-PLAN.md"
tech-stack:
  added:
    - "pydantic"
    - "PyYAML"
  patterns:
    - "Declarative YAML/JSON model manifests with capabilities and VRAM estimation"
    - "Uniform BaseModelAdapter abstract base class decoupling engines from orchestrator"
    - "In-memory ModelRegistry with recursive discovery and runtime hot-registration (FR-MM-4)"
    - "Strict localhost/127.0.0.1 loopback endpoint validation enforcing zero external egress"
key-files:
  created:
    - "src/sovereign/models/__init__.py"
    - "src/sovereign/models/manifest.py"
    - "src/sovereign/models/types.py"
    - "src/sovereign/models/adapter.py"
    - "src/sovereign/models/registry.py"
    - "tests/fixtures/models/qwen_reasoning.yaml"
    - "tests/fixtures/models/qwen_coder.yaml"
    - "tests/fixtures/models/florence_vision.yaml"
    - "tests/fixtures/models/bge_embedding.yaml"
    - "tests/fixtures/models/mock_default.yaml"
    - "tests/test_models/test_model_manifest.py"
    - "tests/test_models/test_model_registry.py"
    - "tests/test_models/test_model_cli.py"
  modified:
    - "src/sovereign/cli.py"
key-decisions:
  - "D-17: Declarative YAML/JSON Model Manifest with Capabilities, VRAM Estimates & Weights SHA-256"
  - "D-18: Abstract BaseModelAdapter Uniform Interface decoupling orchestrator from engine implementations"
  - "D-19: Dynamic In-Memory ModelRegistry with Runtime Hot-Add (FR-MM-4) and Capability-Based Filtering"
  - "D-20: Built-in Model CLI Subcommands (sovereign model list / inspect / register)"
requirements-completed:
  - "MODL-01"
duration: "15 min"
completed: "2026-09-10T14:44:00Z"
coverage:
  - deliverable: "Declarative ModelManifest schema with loopback-only validation"
    verification:
      kind: "pytest"
      ref: "tests/test_models/test_model_manifest.py"
      status: "pass"
    human_judgment: false
  - deliverable: "BaseModelAdapter abstract interface and ModelRegistry catalog"
    verification:
      kind: "pytest"
      ref: "tests/test_models/test_model_registry.py"
      status: "pass"
    human_judgment: false
  - deliverable: "sovereign model list, inspect, and register CLI commands"
    verification:
      kind: "pytest"
      ref: "tests/test_models/test_model_cli.py"
      status: "pass"
    human_judgment: false
---

# Phase 02 Plan 01: Uniform Model Manager Interface & Model Registry Summary

## One-Liner
Declarative YAML/JSON model manifest schema with loopback-only validation, abstract `BaseModelAdapter` uniform interface, dynamic `ModelRegistry` catalog supporting runtime hot-adding without orchestrator restart, and administrative model CLI commands.

## Accomplishments

### Task 02-01-01: Declarative Model Manifest Schema & Validators
1. **Manifest Schema:** Implemented `ModelCapability` enum (`text_drafting`, `reasoning`, `code_generation`, `vision_multimodal`, `embedding`, `calculation`), `EngineConfig`, `IntegrityConfig`, and `ModelManifest` in `src/sovereign/models/manifest.py`.
2. **Security & Zero-Egress Validation:** Enforced strict loopback checks (`127.0.0.1`, `localhost`, `::1`) on `endpoint_url` to reject any public or external IP addresses per SOVG-04. Validated numerical bounds on `context_window` and `vram_estimate_mb` (> 0), and 64-character hex checksums for `weights_sha256`.
3. **Manifest Fixtures:** Created 5 sample model manifests in `tests/fixtures/models/` for reasoning, coding, vision, embedding, and mock testing.

### Task 02-01-02: BaseModelAdapter & Dynamic ModelRegistry
4. **Exchange Types:** Implemented `ChatMessage`, `ModelResponse`, and `VisionRegion` (normalized spatial coordinates `[ymin, xmin, ymax, xmax]`) in `src/sovereign/models/types.py`.
5. **Uniform Adapter Interface:** Implemented `BaseModelAdapter` in `src/sovereign/models/adapter.py` defining standardized lifecycle (`load`, `unload`, `health_check`) and inference (`generate`, `generate_chat`, `embed`, `vision_infer`) methods.
6. **Dynamic Model Registry:** Implemented `ModelRegistry` in `src/sovereign/models/registry.py` with capability-based filtering, recursive directory model discovery, and runtime hot-adding (`register_from_file`) without service restart.

### Task 02-01-03: Model Management CLI Commands
7. **CLI Integration:** Extended `src/sovereign/cli.py` with `sovereign model` subcommands:
   - `sovereign model list [--dir <path>]`: Renders formatted table of registered models, engine types, quantization, VRAM, and capabilities.
   - `sovereign model inspect <model_id> [--dir <path>]`: Displays full JSON configuration and integrity hashes.
   - `sovereign model register <manifest_path>`: Validates and hot-registers a new manifest.

## Verification Results
- 16 passed tests in `tests/test_models/`:
  - `tests/test_models/test_model_manifest.py`: 6 passed
  - `tests/test_models/test_model_registry.py`: 5 passed
  - `tests/test_models/test_model_cli.py`: 5 passed
- Cumulative Phase 1 + Phase 2 test suite: **82 passed** tests in 4.75s.

## Deviations from Plan
None — plan executed exactly as written.

## Self-Check: PASSED
- Declarative model manifest schema with loopback-only check: Verified
- Abstract BaseModelAdapter uniform interface: Verified
- ModelRegistry capability filtering and hot-registration: Verified
- CLI commands (`sovereign model list`, `inspect`, `register`): Verified
- Zero regressions against Phase 1 cryptographic audit & network egress tests: Verified
