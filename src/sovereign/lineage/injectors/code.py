"""
src/sovereign/lineage/injectors/code.py
Source Code Comment and Docstring Lineage Metadata Injector and Extractor (.py, .sh)
"""
import re
from typing import Any, Dict, Optional

PY_BLOCK_PATTERN = re.compile(
    r'"""\s*SOVEREIGN DELIVERABLE LINEAGE\s*([\s\S]*?)"""',
    re.MULTILINE
)

SH_BLOCK_PATTERN = re.compile(
    r'# --- SOVEREIGN DELIVERABLE LINEAGE ---\s*([\s\S]*?)# -------------------------------------',
    re.MULTILINE
)


def _get_field(lineage_data: Any, field_name: str, default: str = "") -> str:
    if hasattr(lineage_data, field_name):
        val = getattr(lineage_data, field_name)
        return str(val) if val is not None else default
    elif isinstance(lineage_data, dict):
        return str(lineage_data.get(field_name, default))
    return default


def _extract_fields(lineage_data: Any) -> Dict[str, str]:
    if hasattr(lineage_data, "model") and hasattr(lineage_data.model, "model_id"):
        model_id = lineage_data.model.model_id
        weights_sha256 = lineage_data.model.weights_sha256
    elif isinstance(lineage_data, dict) and "model" in lineage_data:
        m = lineage_data["model"]
        model_id = m.get("model_id", "")
        weights_sha256 = m.get("weights_sha256", "")
    else:
        model_id = _get_field(lineage_data, "model_id")
        weights_sha256 = _get_field(lineage_data, "weights_sha256")

    return {
        "session_id": _get_field(lineage_data, "session_id"),
        "model_id": model_id,
        "weights_sha256": weights_sha256,
        "audit_tip_hash": _get_field(lineage_data, "audit_tip_hash"),
        "audit_start_seq": _get_field(lineage_data, "audit_start_seq"),
        "audit_end_seq": _get_field(lineage_data, "audit_end_seq"),
        "timestamp_iso": _get_field(lineage_data, "generated_iso"),
    }


def inject_code_lineage(code_str: str, file_ext: str, lineage_data: Any) -> str:
    """
    Injects a standardized lineage header docstring into Python or Shell script code.
    Replaces existing sovereign lineage headers if present.
    """
    ext = file_ext.lower().lstrip(".")
    fields = _extract_fields(lineage_data)

    if ext == "py":
        header_lines = [
            '"""',
            "SOVEREIGN DELIVERABLE LINEAGE",
            f"session_id: {fields['session_id']}",
            f"model_id: {fields['model_id']}",
            f"weights_sha256: {fields['weights_sha256']}",
            f"audit_tip_hash: {fields['audit_tip_hash']}",
            f"audit_start_seq: {fields['audit_start_seq']}",
            f"audit_end_seq: {fields['audit_end_seq']}",
            f"timestamp_iso: {fields['timestamp_iso']}",
            '"""',
        ]
        header = "\n".join(header_lines) + "\n"

        # Check if already has a block to replace
        if PY_BLOCK_PATTERN.search(code_str):
            return PY_BLOCK_PATTERN.sub(header.strip(), code_str, count=1)

        # Handle shebang
        if code_str.startswith("#!"):
            lines = code_str.split("\n", 1)
            shebang = lines[0]
            rest = lines[1] if len(lines) > 1 else ""
            return f"{shebang}\n{header}\n{rest.lstrip()}"
        else:
            return f"{header}\n{code_str.lstrip()}"

    elif ext in ("sh", "bash"):
        header_lines = [
            "# --- SOVEREIGN DELIVERABLE LINEAGE ---",
            f"# session_id: {fields['session_id']}",
            f"# model_id: {fields['model_id']}",
            f"# weights_sha256: {fields['weights_sha256']}",
            f"# audit_tip_hash: {fields['audit_tip_hash']}",
            f"# audit_start_seq: {fields['audit_start_seq']}",
            f"# audit_end_seq: {fields['audit_end_seq']}",
            f"# timestamp_iso: {fields['timestamp_iso']}",
            "# -------------------------------------",
        ]
        header = "\n".join(header_lines) + "\n"

        if SH_BLOCK_PATTERN.search(code_str):
            return SH_BLOCK_PATTERN.sub(header.strip(), code_str, count=1)

        if code_str.startswith("#!"):
            lines = code_str.split("\n", 1)
            shebang = lines[0]
            rest = lines[1] if len(lines) > 1 else ""
            return f"{shebang}\n{header}\n{rest.lstrip()}"
        else:
            return f"{header}\n{code_str.lstrip()}"

    # Default: do not modify unsupported code extensions
    return code_str


def extract_code_lineage(code_str: str) -> Optional[Dict[str, str]]:
    """
    Extracts lineage key-value pairs from a Python docstring or Shell comment header.
    """
    body = None
    py_match = PY_BLOCK_PATTERN.search(code_str)
    if py_match:
        body = py_match.group(1)
    else:
        sh_match = SH_BLOCK_PATTERN.search(code_str)
        if sh_match:
            body = sh_match.group(1)

    if not body:
        return None

    results: Dict[str, str] = {}
    for line in body.splitlines():
        clean_line = line.strip().lstrip("#").strip()
        if not clean_line or ":" not in clean_line:
            continue
        key, val = clean_line.split(":", 1)
        results[key.strip()] = val.strip()

    return results if results else None
