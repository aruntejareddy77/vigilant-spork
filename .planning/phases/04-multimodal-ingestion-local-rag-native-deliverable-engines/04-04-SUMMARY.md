---
phase: "04-multimodal-ingestion-local-rag-native-deliverable-engines"
plan: "04-04"
subsystem: "vision"
tags:
  - "engineering-drawings"
  - "pid-comparison"
  - "pixel-differencing"
  - "contour-clustering"
  - "visual-annotation-overlay"
  - "change-register"
  - "vlm-reasoning"
  - "png-lineage"
requires:
  - "04-01"
  - "04-02"
  - "04-03"
  - "01-02"
  - "02-02"
provides:
  - "src/sovereign/vision/__init__.py"
  - "src/sovereign/vision/diff.py"
  - "src/sovereign/vision/overlay.py"
  - "src/sovereign/vision/register.py"
  - "src/sovereign/vision/tools.py"
affects: []
tech-stack:
  added: []
  patterns:
    - "Dual-layer engineering drawing comparison (Layer 1 Pillow pixel diff + morphological clustering; Layer 2 local VLM semantic inference)"
    - "Pure Pillow image operations avoiding external OpenCV or proprietary CAD binaries"
    - "Industrial visual drafting overlay conventions: desaturated base (#808080), Green (#00C853) for Added, Red (#D50000) for Removed, Amber (#FFD600) for Modified, with 15% translucent color wash"
    - "Drafting title block with legend and numbered circular callout badges"
    - "Structured Change Register table export (.docx, .md, .json)"
    - "Cryptographic lineage embedding via LineageEngine into PNG tEXt chunks and .lineage.json manifests"
    - "Strict memory bounds (< 250MB) via MAX_IMAGE_PIXELS=50M and auto-scaling drawings > 4096px"
    - "Path fencing preventing directory traversal (PathSecurityViolation)"
key-files:
  created:
    - "src/sovereign/vision/__init__.py"
    - "src/sovereign/vision/diff.py"
    - "src/sovereign/vision/overlay.py"
    - "src/sovereign/vision/register.py"
    - "src/sovereign/vision/tools.py"
    - "tests/test_vision/__init__.py"
    - "tests/test_vision/test_drawing_diff.py"
    - "tests/test_vision/test_change_register.py"
  modified: []
key-decisions:
  - "Implemented dual-layer differencing architecture combining deterministic pure-Pillow pixel difference with local vision-language model reasoning via BaseModelAdapter.vision_infer()."
  - "Enforced 50M pixel ceiling (Image.MAX_IMAGE_PIXELS = 50_000_000) and automatic bilinear downsampling for images exceeding 4096px, bounding memory consumption under 250MB (Threat T-04-03)."
  - "Applied industrial drafting color standards: desaturated base image, Green (#00C853) for Added, Red (#D50000) for Removed, and Amber (#FFD600) for Modified, with solid circular badges."
  - "Packaged output overlay deliverables with format-native PNG lineage chunks (inject_png_lineage) and sibling .lineage.json manifests."
  - "Implemented diff_drawings tool in ToolRegistry under UserRole.ENGINEER clearance with workspace path fencing."
requirements-completed:
  - "MMOD-03"
duration: "20 min"
completed: "2026-09-14T15:46:00Z"
coverage:
  - deliverable: "Drawing Revision Differencing & Overlay Engine"
    verification: "tests/test_vision/test_drawing_diff.py (11 passing)"
  - deliverable: "Semantic Change Register Generator & diff_drawings Tool"
    verification: "tests/test_vision/test_change_register.py (9 passing)"
---

# Plan 04-04: Engineering Drawing / P&ID Revision Comparison & Visual Annotation Overlay Generator Summary

## Overview

Plan 04-04 delivers the sovereign computer vision and engineering drawing revision comparison engine for the Sovereign AI Workbench. Operating completely offline without external OpenCV (`cv2`) dependencies or cloud vision APIs, this subsystem executes a dual-layer differencing architecture:
1. **Layer 1 (Physical / Spatial Differencing):** Pure-Python pixel differencing, luminance polarity analysis (paper drawings vs blueprint CAD), and morphological connected component clustering via Pillow. Detects added, removed, and modified regions while enforcing strict memory and dimension bounds (< 250MB, max 4096px downsampling, 50MB file size ceiling).
2. **Layer 2 (Semantic Vision Reasoning):** Local Vision-Language Model reasoning via `BaseModelAdapter.vision_infer()` to analyze differences, extract equipment tags (e.g. `CV-103`, `P-101`, `V-102`), evaluate baseline vs revised states, and categorize safety risks.
3. **Visual Revision Overlay Deliverable:** High-contrast visual rendering adhering to industrial drafting conventions: desaturated base background, Green (`#00C853`) for Added, Red (`#D50000`) for Removed, Amber (`#FFD600`) for Modified, numbered circular callouts, and an engineering title block with legend. Cryptographic W3C PROV-O lineage is embedded directly into the output PNG tEXt chunks and sibling `.lineage.json` manifests.
4. **Structured Change Register & Tool Integration:** Tabular change register exported to Markdown, JSON, and native Microsoft Word (`.docx`) tables with zebra striping and risk indicators. Registered into `ToolRegistry` as `diff_drawings` under `UserRole.ENGINEER` clearance with workspace path fencing.

---

## Deliverables & Modules Implemented

### 1. Drawing Differencing Engine (`src/sovereign/vision/diff.py`)
- **Requirement:** `MMOD-03`
- **Classes:** `DiffChangeType`, `DiffBoundingBox`, `DrawingDiffEngine`
- **Key Features:**
  - Memory bounds enforcement: `Image.MAX_IMAGE_PIXELS = 50_000_000` and proportional bilinear downsampling for images exceeding 4096px (Threat T-04-03).
  - Dimension normalization: Resizes Rev B to Rev A if minor scanner variances exist.
  - Grayscale pixel differencing via `ImageChops.difference(im_a, im_b)`.
  - Background-adaptive polarity analysis: Distinguishes Added vs Removed ink on both white paper drawings and dark CAD blueprints.
  - Grid-based connected component clustering and bounding box merging.
  - Normalized $[0.0, 1.0]$ spatial coordinates (`[ymin, xmin, ymax, xmax]`).
  - Region cropping helper: `DrawingDiffEngine.crop_diff_region` for visual inspection and VLM inference.

### 2. Visual Annotation Overlay Renderer (`src/sovereign/vision/overlay.py`)
- **Requirement:** `MMOD-03`
- **Class:** `VisualOverlayRenderer`
- **Key Features:**
  - Desaturates Rev B base image and blends with `#808080` (alpha=0.35) for medium contrast.
  - 3-pixel colored bounding boxes with 15% translucent color wash.
  - Industrial drafting palette: Green (`#00C853`) for ADDED, Red (`#D50000`) for REMOVED, Amber (`#FFD600`) for MODIFIED.
  - Numbered circular badges at top-left of each bounding box matching `box_id`.
  - Drafting title block in bottom-right corner with Drawing Title, change statistics, and color legend swatches.
  - Mandatory LineageEngine integration: Injects PNG `sovereign_lineage` tEXt chunks and writes `<output>.lineage.json` sidecar.
  - Workspace boundary path traversal fencing (Threat T-04-04).

### 3. Structured Change Register Generator (`src/sovereign/vision/register.py`)
- **Requirement:** `MMOD-03`, `DELV-01`
- **Classes:** `ChangeRegisterItem`, `ChangeRegister`, `ChangeRegisterGenerator`
- **Key Features:**
  - Semantic inference: Queries `model_adapter.vision_infer()` on image crops to extract equipment tags and physical modifications.
  - Automatic fallback mode when no VLM adapter is present.
  - Multi-format exports:
    - `export_markdown`: Tabular Markdown summary.
    - `export_word_table`: Native Microsoft Word (`.docx`) table with Navy headers (`#1E3A8A`), zebra striping (`#F8FAFC`), status badges, and risk highlights.
  - Lineage packaging: Attaches W3C PROV-O sidecars to generated documents.

### 4. Agentic Vision Tool (`src/sovereign/vision/tools.py`)
- **Requirement:** `MMOD-03`
- **Components:** `DIFF_DRAWINGS_TOOL_DEF`, `handle_diff_drawings`, `register_vision_tools`
- **Key Features:**
  - Registered under `UserRole.ENGINEER` in `ToolRegistry`.
  - Rigid JSON Schema parameter validation (`rev_a_path`, `rev_b_path`, `output_overlay_path`, optional `output_report_path`).
  - End-to-end execution: Runs pixel differencing, renders overlay deliverable, runs VLM change register, and saves reports (.docx, .md, .json).
  - Strict path traversal defense: Blocks targets outside workspace boundary with `PathSecurityViolation`.

---

## Verification & Test Results

All 20 tests in `tests/test_vision/` pass 100% offline in 1.73 seconds. Full Phase 4 test suite (multimodal, rag, deliverables, vision) passes 93/93 tests in 5.00 seconds.

```
tests/test_vision/test_drawing_diff.py:
  TestDrawingDiffEngine:
    ✓ test_diff_models_serialization
    ✓ test_identical_drawings_yield_zero_diff
    ✓ test_missing_file_raises_not_found
    ✓ test_invalid_image_format_raises_value_error
    ✓ test_file_size_exceeding_ceiling_raises_value_error
    ✓ test_dimension_mismatch_resizes_gracefully
    ✓ test_large_drawing_auto_scaled
    ✓ test_revision_diff_detects_added_and_removed_regions
    ✓ test_crop_diff_region
  TestVisualOverlayRenderer:
    ✓ test_render_diff_overlay_success
    ✓ test_path_traversal_fencing

tests/test_vision/test_change_register.py:
  TestChangeRegisterModels:
    ✓ test_item_and_register_serialization
  TestChangeRegisterGenerator:
    ✓ test_generate_register_with_vlm_adapter
    ✓ test_generate_register_fallback_without_vlm
    ✓ test_export_markdown
    ✓ test_export_word_table
  TestVisionTools:
    ✓ test_tool_definition_and_clearance
    ✓ test_diff_drawings_tool_execution
    ✓ test_diff_drawings_rbac_enforcement
    ✓ test_diff_drawings_path_traversal_fencing

Result: 20 passed in 1.73s
Full Phase 4 Suite: 93 passed in 5.00s
```

---

## Threat Model Compliance

| Threat ID | Mitigation Implemented | Verified By |
|:---|:---|:---|
| **T-04-03 (Denial of Service / Memory Bounds)** | Configured `Image.MAX_IMAGE_PIXELS = 50_000_000`, 50MB file size ceiling, and proportional bilinear downsampling for images $> 4096\text{px}$, guaranteeing differencing memory allocation $< 250\text{MB}$. | `test_file_size_exceeding_ceiling_raises_value_error`, `test_large_drawing_auto_scaled` |
| **T-04-04 (Path Traversal / Tampering)** | Enforced path fencing via `validate_output_path(target, workspace_root)` raising `PathSecurityViolation` when destination escapes boundary. | `test_path_traversal_fencing`, `test_diff_drawings_path_traversal_fencing` |
