---
phase: "02-local-model-management-adapters-vram-scheduler"
plan: "02-03"
subsystem: "models"
tags:
  - "task-classifier"
  - "task-router"
  - "vram-scheduler"
  - "lru-swapping"
  - "audit-logging"
  - "cli"
requires:
  - "02-01"
  - "02-02"
provides:
  - "src/sovereign/models/router.py"
  - "src/sovereign/models/scheduler.py"
affects:
  - "Phase 3 (Agentic State Machine & Tool Registry)"
tech-stack:
  added:
    - "threading (stdlib)"
    - "re (stdlib)"
  patterns:
    - "Deterministic multi-modal task classification with keyword & data modality heuristics"
    - "Capability scoring and specialized model auto-routing with manual override support (FR-MM-6)"
    - "VRAM memory budget scheduler with 2GB safety headroom and atomic LRU eviction swapping"
    - "Cryptographic audit trail integration logging MODEL_ROUTED, MODEL_LOADED, MODEL_UNLOADED, and MODEL_SWAPPED"
key-files:
  created:
    - "src/sovereign/models/router.py"
    - "src/sovereign/models/scheduler.py"
    - "tests/test_models/test_task_router.py"
    - "tests/test_models/test_vram_scheduler.py"
  modified:
    - "src/sovereign/cli.py"
    - "tests/test_models/test_model_cli.py"
key-decisions:
  - "D-24: Multi-Tier Task Classification Router with Deterministic Rule Heuristics and Manual Override (--model <id>)"
  - "D-25: VRAM-Aware Scheduler with Safety Headroom Reserve (2GB) and LRU Eviction Swapping on Single 24GB GPU"
  - "D-26: Comprehensive Audit Logging for Routing and Memory Transitions (MODEL_ROUTED, MODEL_SWAPPED)"
  - "D-27: Built-in Routing CLI (sovereign model route \"<prompt>\")"
requirements-completed:
  - "MODL-02"
  - "MODL-03"
duration: "20 min"
completed: "2026-09-10T15:09:00Z"
coverage:
  - deliverable: "TaskClassifier and TaskRouter with audit logging"
    verification:
      kind: "pytest"
      ref: "tests/test_models/test_task_router.py"
      status: "pass"
    human_judgment: false
  - deliverable: "VRAMScheduler memory budget and LRU eviction swapping"
    verification:
      kind: "pytest"
      ref: "tests/test_models/test_vram_scheduler.py"
      status: "pass"
    human_judgment: false
  - deliverable: "sovereign model route CLI command"
    verification:
      kind: "pytest"
      ref: "tests/test_models/test_model_cli.py"
      status: "pass"
    human_judgment: false
---

# Phase 02 Plan 03: Task Classification Router & VRAM Scheduler Summary

## One-Liner
Deterministic task classification and capability-based auto-router with manual `--model` override, GPU VRAM-aware scheduler enforcing 24GB budgets with atomic LRU model swapping, and complete audit trail emission (`MODEL_ROUTED`, `MODEL_SWAPPED`).

## Accomplishments

### Task 02-03-01: TaskClassifier & TaskRouter
1. **Deterministic Intent Classifier:** Implemented `TaskClassifier` in `src/sovereign/models/router.py` categorizing incoming requests across `vision_multimodal`, `code_generation`, `calculation`, `text_drafting`, `embedding`, and `reasoning`.
2. **Capability Scoring & Auto-Routing:** Implemented `TaskRouter` matching declared model capabilities with multi-attribute ranking (real vs mock, name affinity, specialization degree, and VRAM footprint).
3. **Manual Override (FR-MM-6):** Supports `--model <id>` to bypass classification and directly pin execution to an operator-specified model.
4. **Audit Trail Logging:** Automatically writes `MODEL_ROUTED` events to `AuditLedger` capturing prompt preview, classified capability, target model, and selection rationale.

### Task 02-03-02: VRAM-Aware Scheduler & Dynamic Swapping
5. **Memory Budget Accounting:** Implemented `VRAMScheduler` in `src/sovereign/models/scheduler.py` tracking total budget (24,576 MB) and safety reserve (2,048 MB), yielding 22,528 MB usable VRAM.
6. **LRU Dynamic Swapping:** Evicts inactive models in Least-Recently-Used order when a new model load would otherwise cause a GPU Out-Of-Memory condition.
7. **Hard Budget Guard:** Rejects models that individually exceed the usable budget with `VRAMExceededError`.
8. **Audit Events:** Emits `MODEL_LOADED`, `MODEL_UNLOADED`, and `MODEL_SWAPPED` to `AuditLedger`.

### Task 02-03-03: Model Routing CLI
9. **Interactive Routing Command:** Added `sovereign model route "<prompt>"` CLI command supporting `--dir`, `--image`, and `--model` override flags.

## Verification Results
- 15 passed tests across 3 test files in `tests/test_models/`:
  - `tests/test_models/test_task_router.py`: 4 passed
  - `tests/test_models/test_vram_scheduler.py`: 3 passed
  - `tests/test_models/test_model_cli.py`: 8 passed
- Full suite (Phase 1 + Phase 2): **106 passed** tests in 4.96s.

## Deviations from Plan
None — plan executed exactly as written.

## Self-Check: PASSED
- TaskClassifier and TaskRouter auto-routing: Verified
- Manual model override (`--model`): Verified
- VRAM budget tracking and LRU eviction: Verified
- Audit trail event logging: Verified
- 100% offline air-gapped test suite passing with zero regressions: Verified
