"""
src/sovereign/tools/builtin/files.py
Fenced filesystem tools strictly confined to a workspace directory per D-32 and TOOL-03.
"""
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Union


class PathSecurityViolation(Exception):
    """Raised when an operation attempts to escape the designated workspace boundary."""
    pass


def _resolve_fenced_path(workspace_root: Union[str, Path], target_path: Union[str, Path]) -> Path:
    """
    Resolve target_path within workspace_root and ensure it does not escape.
    Fails closed if the path attempts traversal out of the workspace.
    """
    root = Path(workspace_root).resolve()
    
    # Check for null bytes
    target_str = str(target_path)
    if "\x00" in target_str:
        raise PathSecurityViolation("Null byte detected in path argument")

    # Combine with root if relative; if absolute, verify it sits inside root
    target = Path(target_str)
    if not target.is_absolute():
        resolved = (root / target).resolve()
    else:
        resolved = target.resolve()

    try:
        resolved.relative_to(root)
    except ValueError:
        raise PathSecurityViolation(
            f"Access denied: Target path '{target_path}' is outside workspace root '{root}'"
        )

    return resolved


def read_file(path: str, workspace_root: Union[str, Path], max_bytes: int = 65536) -> str:
    """
    Read the contents of a file within the workspace boundary up to max_bytes.
    """
    resolved = _resolve_fenced_path(workspace_root, path)
    if not resolved.exists():
        raise FileNotFoundError(f"File not found: '{path}'")
    if not resolved.is_file():
        raise IsADirectoryError(f"Target is a directory, not a file: '{path}'")

    with open(resolved, "r", encoding="utf-8", errors="replace") as f:
        return f.read(max_bytes)


def write_file(
    path: str,
    content: str,
    workspace_root: Union[str, Path],
    overwrite: bool = True,
) -> Dict[str, Any]:
    """
    Write content to a file inside the workspace boundary.
    Creates parent directories if necessary and computes SHA-256 integrity hash.
    """
    resolved = _resolve_fenced_path(workspace_root, path)
    if resolved.exists() and not overwrite:
        raise FileExistsError(f"File already exists and overwrite is disabled: '{path}'")

    resolved.parent.mkdir(parents=True, exist_ok=True)
    encoded = content.encode("utf-8")
    with open(resolved, "w", encoding="utf-8") as f:
        f.write(content)

    content_hash = hashlib.sha256(encoded).hexdigest()
    root = Path(workspace_root).resolve()
    rel_path = str(resolved.relative_to(root)).replace("\\", "/")

    return {
        "path": rel_path,
        "bytes_written": len(encoded),
        "sha256": content_hash,
    }


def list_directory(
    path: str = ".",
    workspace_root: Union[str, Path] = ".",
    recursive: bool = False,
) -> List[Dict[str, Any]]:
    """
    List files and directories within a workspace subfolder.
    """
    resolved = _resolve_fenced_path(workspace_root, path)
    if not resolved.exists():
        raise FileNotFoundError(f"Directory not found: '{path}'")
    if not resolved.is_dir():
        raise NotADirectoryError(f"Target is not a directory: '{path}'")

    root = Path(workspace_root).resolve()
    results = []

    pattern = "**/*" if recursive else "*"
    for item in resolved.glob(pattern):
        # Prevent listing outside symlink traps
        try:
            item_resolved = item.resolve()
            item_resolved.relative_to(root)
        except (ValueError, RuntimeError):
            continue

        rel_path = str(item_resolved.relative_to(root)).replace("\\", "/")
        is_file = item_resolved.is_file()
        results.append({
            "path": rel_path,
            "type": "file" if is_file else "directory",
            "size_bytes": item_resolved.stat().st_size if is_file else 0,
        })

    return sorted(results, key=lambda x: x["path"])
