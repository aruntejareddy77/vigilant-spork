"""
src/sovereign/lineage/engine.py
Deliverable Lineage Packaging Engine
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from sovereign.lineage.models import (
    DeliverableInfo,
    LineageMetadata,
    ModelInfo,
    SourceDocumentCitation,
    ToolExecutionRecord,
)
from sovereign.lineage.injectors.ooxml import inject_ooxml_lineage
from sovereign.lineage.injectors.png import inject_png_lineage
from sovereign.lineage.injectors.code import inject_code_lineage

OOXML_EXTENSIONS = {".docx", ".xlsx", ".pptx"}
PNG_EXTENSIONS = {".png"}
CODE_EXTENSIONS = {".py", ".sh", ".bash"}


class LineageEngine:
    """
    Engine responsible for packaging deliverables with format-native embedded metadata
    and sibling W3C PROV-O JSON sidecar manifests.
    """

    @staticmethod
    def compute_sha256(file_path: Union[str, Path]) -> str:
        """
        Computes SHA-256 hex digest of a file.
        """
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def package_deliverable(
        cls,
        deliverable_path: Union[str, Path],
        metadata: LineageMetadata,
        write_sidecar: bool = True
    ) -> Path:
        """
        Packages a deliverable:
        1. Injects format-native metadata into the file (.docx, .xlsx, .pptx, .png, .py, .sh).
        2. Computes the final file SHA-256 and size on disk.
        3. Updates metadata with the final deliverable hash and size.
        4. Writes the sibling `<deliverable_path>.lineage.json` sidecar file.

        Returns:
            Path to the generated sidecar manifest.
        """
        path = Path(deliverable_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Deliverable file not found: {path}")

        ext = path.suffix.lower()

        # Step 1: Format-native injection
        if ext in OOXML_EXTENSIONS:
            file_bytes = path.read_bytes()
            props = {
                "sovereign_session_id": metadata.session_id,
                "sovereign_model_id": metadata.model.model_id,
                "sovereign_weights_sha256": metadata.model.weights_sha256,
                "sovereign_audit_tip": metadata.audit_tip_hash,
                "sovereign_audit_start_seq": str(metadata.audit_start_seq),
                "sovereign_audit_end_seq": str(metadata.audit_end_seq),
                "sovereign_timestamp": metadata.generated_iso,
            }
            injected_bytes = inject_ooxml_lineage(file_bytes, props)
            path.write_bytes(injected_bytes)

        elif ext in PNG_EXTENSIONS:
            image_bytes = path.read_bytes()
            lineage_summary = metadata.model_dump_json()
            injected_bytes = inject_png_lineage(image_bytes, lineage_summary)
            path.write_bytes(injected_bytes)

        elif ext in CODE_EXTENSIONS:
            code_text = path.read_text(encoding="utf-8")
            injected_text = inject_code_lineage(code_text, ext, metadata)
            path.write_text(injected_text, encoding="utf-8")

        # Step 2: Compute final digest and file attributes on disk
        final_sha256 = cls.compute_sha256(path)
        final_size = path.stat().st_size

        metadata.deliverable.file_sha256 = final_sha256
        metadata.deliverable.file_size_bytes = final_size
        metadata.deliverable.file_name = path.name

        # Step 3: Write sibling sidecar manifest
        sidecar_path = Path(f"{path}.lineage.json")
        if write_sidecar:
            sidecar_path.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")

        return sidecar_path

    @staticmethod
    def load_sidecar(sidecar_path: Union[str, Path]) -> LineageMetadata:
        """
        Loads and parses a lineage sidecar manifest.
        """
        path = Path(sidecar_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Lineage sidecar manifest not found: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))
        return LineageMetadata.model_validate(data)
