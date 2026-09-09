<!-- GSD:project-start source:PROJECT.md -->

## Project

**Sovereign AI Workbench**

The Sovereign AI Workbench is a self-hosted, air-gapped, model-agnostic agentic AI platform engineered for refineries, public sector undertakings (PSUs), defense-linked manufacturing units, and regulated government enclaves. It delivers cloud-assistant-grade engineering and executive productivity—multi-step task execution, multimodal document understanding, native Office deliverable generation, and sandboxed code execution—while providing continuous, mathematically and empirically verifiable proof that zero data ever leaves the on-premises environment.

**Core Value:** Verifiable sovereign agentic productivity: autonomous multimodal task execution and auditable deliverable generation running 100% offline with continuously observable zero-network egress.

### Constraints

- **Security & Network**: Must enforce default-deny egress; 0 external outbound network packets during operation.
- **Deployment**: Self-contained on a single Linux host (with Windows/local development and demonstration flexibility), running entirely offline.
- **Hardware Profile**: Must accommodate mid-range GPU (24GB VRAM class) or provide deterministic graceful degradation / mock adapters for lightweight test environments without GPU hardware.
- **Auditability**: 100% of agent actions must be captured in an immutable hash-chained audit log.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->

## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.agents/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
