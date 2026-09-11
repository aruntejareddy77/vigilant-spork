"""
src/sovereign/deliverables/code_export.py
Reproducible code artifact exporter bundling runnable Python scripts, execution logs,
sample input data fixtures, and W3C PROV-O lineage sidecars in /local/output.
Complies with DELV-04 and T-04-04 (path fencing).
"""
from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Any, Dict, Optional, Union
import uuid

from sovereign.deliverables.docx import validate_output_path
from sovereign.lineage.engine import LineageEngine
from sovereign.lineage.models import (
    DeliverableInfo,
    LineageMetadata,
    ModelInfo,
)
from sovereign.tools.builtin.files import PathSecurityViolation


class CodeArtifactExporter:
    """
    Packages verified runnable Python scripts with execution traces,
    sample test inputs, and cryptographic lineage into the deliverable output directory.
    """

    def __init__(self, allowed_root: Optional[Union[str, Path]] = None):
        self.allowed_root = Path(allowed_root).resolve() if allowed_root else None

    @classmethod
    def export_reproducible_bundle(
        cls,
        output_dir: Union[str, Path],
        script_name: str,
        script_code: str,
        execution_log: str,
        sample_input_path: Optional[Union[str, Path]] = None,
        lineage_metadata: Optional[LineageMetadata] = None,
        allowed_root: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Path]:
        """
        Exports a reproducible code bundle:
        - `<script_name>.py` with sovereign provenance header
        - `<script_name>.log` containing stdout, stderr, and exit metrics
        - `<input_file>` copied sample fixture (if provided)
        - `<script_name>.py.lineage.json` sidecar manifest

        Returns:
            Dict[str, Path] mapping component names ('script', 'log', 'sidecar', 'input') to paths.
        """
        # Validate output directory against traversal attacks
        resolved_dir = validate_output_path(output_dir, allowed_root)
        resolved_dir.mkdir(parents=True, exist_ok=True)

        # Normalize script base name
        raw_name = Path(script_name).name
        if raw_name.endswith(".py"):
            base_name = raw_name[:-3]
        else:
            base_name = raw_name

        script_path = resolved_dir / f"{base_name}.py"
        log_path = resolved_dir / f"{base_name}.log"

        # Prepare Lineage Metadata
        meta = lineage_metadata
        if meta is None:
            meta = LineageMetadata(
                deliverable=DeliverableInfo(
                    file_name=script_path.name,
                    media_type="text/x-python",
                ),
                session_id=f"session-{uuid.uuid4().hex[:8]}",
                user_id="engineer",
                user_role="Lead Engineer",
                model=ModelInfo(model_id="sovereign-code-v1", weights_sha256="0" * 64),
                audit_start_seq=0,
                audit_end_seq=1,
                audit_tip_hash="0" * 64,
            )

        # 1. Write executable Python script with provenance header
        header = (
            f'"""\n'
            f'Sovereign AI Workbench - Reproducible Code Artifact\n'
            f'Script Name : {base_name}.py\n'
            f'Session ID  : {meta.session_id}\n'
            f'Timestamp   : {datetime.now(timezone.utc).isoformat()}\n'
            f'Model ID    : {meta.model.model_id}\n'
            f'"""\n\n'
        )
        full_code = header + script_code
        script_path.write_text(full_code, encoding="utf-8")

        # 2. Write execution log trace
        log_path.write_text(execution_log, encoding="utf-8")

        # 3. Copy sample input fixture if provided
        copied_input: Optional[Path] = None
        if sample_input_path is not None:
            src_in = Path(sample_input_path).resolve()
            if src_in.exists() and src_in.is_file():
                dest_in = resolved_dir / src_in.name
                shutil.copy2(src_in, dest_in)
                copied_input = dest_in

        # 4. Package script via LineageEngine (injects code lineage & writes sidecar)
        sidecar_path = LineageEngine.package_deliverable(script_path, meta)

        results = {
            "script": script_path,
            "log": log_path,
            "sidecar": sidecar_path,
        }
        if copied_input:
            results["input"] = copied_input

        return results
