---
phase: "03-agentic-state-machine-tool-registry-isolated-sandbox"
plan: "03-02"
subsystem: "tools"
tags:
  - "tool-registry"
  - "json-schema"
  - "rbac"
  - "path-fencing"
  - "tabular-parsing"
  - "ast-calculator"
requires:
  - "03-01"
provides:
  - "src/sovereign/tools/schemas.py"
  - "src/sovereign/tools/registry.py"
  - "src/sovereign/tools/builtin/files.py"
  - "src/sovereign/tools/builtin/parsing.py"
  - "src/sovereign/tools/builtin/calculator.py"
  - "src/sovereign/tools/builtin/__init__.py"
affects:
  - "03-03-PLAN.md"
tech-stack:
  added:
    - "jsonschema"
    - "ast (Python standard library)"
  patterns:
    - "Rigid JSON Schema tool parameter definition and runtime validation"
    - "Hierarchical RBAC clearance enforcement (Admin >= Engineer >= Auditor)"
    - "Workspace path fencing (_resolve_fenced_path) preventing directory traversal"
    - "Safe AST-based arithmetic and math evaluation strictly avoiding eval()/exec()"
key-files:
  created:
    - "src/sovereign/tools/__init__.py"
    - "src/sovereign/tools/schemas.py"
    - "src/sovereign/tools/registry.py"
    - "src/sovereign/tools/builtin/__init__.py"
    - "src/sovereign/tools/builtin/files.py"
    - "src/sovereign/tools/builtin/parsing.py"
    - "src/sovereign/tools/builtin/calculator.py"
    - "tests/test_tools/test_tool_registry.py"
    - "tests/test_tools/test_builtin_tools.py"
key-decisions:
  - "D-32: Rigid JSON Schema Tool Registry with RBAC clearances and workspace path fencing"
  - "D-33: Built-in safe tools: read_file, write_file, list_directory, parse_table, extract_text, execute_calculation"
requirements-completed:
  - "TOOL-01"
  - "TOOL-03"
duration: "15 min"
completed: "2026-09-10T15:35:00Z"
coverage:
  - deliverable: "ToolRegistry with JSON Schema and RBAC enforcement"
    verification: "tests/test_tools/test_tool_registry.py (5 passing)"
  - deliverable: "Path-fenced file operations and traversal protection"
    verification: "tests/test_tools/test_builtin_tools.py (7 passing)"
  - deliverable: "AST-based safe calculation and tabular parsing"
    verification: "tests/test_tools/test_builtin_tools.py (7 passing)"
---

# Plan 03-02: Tool Registry with JSON Schema, RBAC Clearance & Built-in Tools Summary

## Implemented Capabilities
1. **JSON Schema Tool Registry (`src/sovereign/tools/registry.py`)**:
   - Explicit JSON Schemas for tool inputs and outputs.
   - Generates OpenAI/SGLang standard function-calling definitions (`get_tool_schemas_for_model`).
   - Validates parameters at runtime using `jsonschema.validate`.
2. **RBAC Clearance Authorization (`src/sovereign/tools/schemas.py`)**:
   - `UserRole` enum (`ADMIN`, `ENGINEER`, `AUDITOR`) with strict hierarchy checks.
   - Prevents unprivileged callers from invoking engineering or administrative tools.
3. **Workspace Path Fencing (`src/sovereign/tools/builtin/files.py`)**:
   - `_resolve_fenced_path` strictly bounds all read, write, and list operations within `workspace_root`.
   - Rejects traversal attempts (`../`, absolute outside paths, null bytes) with `PathSecurityViolation`.
4. **Structured Tabular Parsing & Text Extraction (`src/sovereign/tools/builtin/parsing.py`)**:
   - `parse_table`: Extracts CSV/TSV data with automatic numeric type conversion.
   - `extract_text`: Strips markup tags and normalizes multi-line whitespace.
5. **Safe AST Mathematical Calculation (`src/sovereign/tools/builtin/calculator.py`)**:
   - Evaluates arithmetic and standard mathematical functions via AST traversal.
   - Provides step-by-step substitution traces while strictly rejecting `eval()`, `exec()`, and imports.
