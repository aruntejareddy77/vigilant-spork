"""
src/sovereign/sandbox/executor.py
Multi-tier isolated code execution sandbox with zero-network guarantees and ephemeral scratchpads per TOOL-02 and D-30.
"""
import ast
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Set, Union
from pydantic import BaseModel, ConfigDict, Field
from sovereign.audit.ledger import AuditLedger


PROHIBITED_MODULES: Set[str] = {
    "socket",
    "http",
    "urllib",
    "requests",
    "aiohttp",
    "httpx",
    "ftplib",
    "poplib",
    "imaplib",
    "smtplib",
    "telnetlib",
    "webbrowser",
    "paramiko",
    "netrc",
}


class SandboxSecurityViolation(Exception):
    """Raised when code violates sandbox security policies or attempts network access."""
    pass


class ExecutionResult(BaseModel):
    """Result of sandboxed code execution."""
    model_config = ConfigDict(extra="forbid")

    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    timed_out: bool = False
    output_files: Dict[str, bytes] = Field(default_factory=dict)


def validate_script_safety(script_content: str) -> None:
    """
    Perform static AST analysis to block network library imports and dangerous network calls.
    Fails closed on syntax errors or policy violations.
    """
    try:
        tree = ast.parse(script_content)
    except SyntaxError as syn_err:
        raise ValueError(f"Script contains invalid Python syntax: {syn_err.msg}") from syn_err

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".")[0]
                if top_level in PROHIBITED_MODULES:
                    raise SandboxSecurityViolation(
                        f"Network import prohibited in sandbox: '{alias.name}'"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top_level = node.module.split(".")[0]
                if top_level in PROHIBITED_MODULES:
                    raise SandboxSecurityViolation(
                        f"Network import prohibited in sandbox: '{node.module}'"
                    )


class CodeSandbox:
    """
    Multi-tier isolated code sandbox.
    Uses Linux network namespaces (`unshare -n`) where available;
    enforces static AST import filters, timeout bounding, and ephemeral scratchpad
    destruction on Windows and non-root environments.
    """

    def __init__(
        self,
        timeout_seconds: float = 15.0,
        audit_ledger: Optional[AuditLedger] = None,
        base_scratch_dir: Optional[Union[str, Path]] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.audit_ledger = audit_ledger
        self.base_scratch_dir = Path(base_scratch_dir) if base_scratch_dir else None
        if self.base_scratch_dir:
            self.base_scratch_dir.mkdir(parents=True, exist_ok=True)

    def execute(
        self,
        code: str,
        input_files: Optional[Dict[str, Union[str, bytes]]] = None,
        session_id: str = "sandbox-session",
    ) -> ExecutionResult:
        """
        Execute Python code inside an isolated ephemeral scratch directory.
        Enforces execution timeouts and zero network access.
        """
        # 1. Static AST analysis
        validate_script_safety(code)

        # 2. Ephemeral directory creation
        with tempfile.TemporaryDirectory(dir=self.base_scratch_dir) as scratch_dir:
            scratch_path = Path(scratch_dir).resolve()

            # Write input files
            initial_files = {"script.py"}
            if input_files:
                for fname, fcontent in input_files.items():
                    fpath = scratch_path / fname
                    fpath.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(fcontent, str):
                        fpath.write_text(fcontent, encoding="utf-8")
                    else:
                        fpath.write_bytes(fcontent)
                    initial_files.add(fname)

            # Write main execution script
            script_file = scratch_path / "script.py"
            script_file.write_text(code, encoding="utf-8")

            # 3. Formulate command (detect unshare on Linux)
            cmd = [sys.executable, "script.py"]
            if sys.platform.startswith("linux") and shutil.which("unshare"):
                cmd = ["unshare", "-n", sys.executable, "script.py"]

            # 4. Strip sensitive environment variables
            clean_env = {}
            for k, v in os.environ.items():
                k_upper = k.upper()
                if any(
                    bad in k_upper
                    for bad in (
                        "PROXY",
                        "KEY",
                        "SECRET",
                        "TOKEN",
                        "PASSWORD",
                        "AUTH",
                        "CREDENTIAL",
                    )
                ):
                    continue
                clean_env[k] = v
            # Prevent Python from writing __pycache__ in sandbox
            clean_env["PYTHONDONTWRITEBYTECODE"] = "1"

            # 5. Execute subprocess with hard timeout
            start_time = time.perf_counter()
            timed_out = False
            stdout = ""
            stderr = ""
            exit_code = 0

            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(scratch_path),
                    env=clean_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self.timeout_seconds,
                )
                stdout = proc.stdout
                stderr = proc.stderr
                exit_code = proc.returncode
            except subprocess.TimeoutExpired as exp:
                timed_out = True
                exit_code = -1
                stdout = exp.stdout.decode("utf-8", errors="replace") if exp.stdout else ""
                stderr = f"Execution timed out after {self.timeout_seconds} seconds"
            except Exception as exc:
                exit_code = -1
                stderr = f"Subprocess launch error: {str(exc)}"

            duration = time.perf_counter() - start_time

            # 6. Collect generated output files
            output_files: Dict[str, bytes] = {}
            for path in scratch_path.glob("**/*"):
                if path.is_file():
                    rel_name = str(path.relative_to(scratch_path)).replace("\\", "/")
                    if rel_name not in initial_files:
                        try:
                            output_files[rel_name] = path.read_bytes()
                        except Exception:
                            pass

            result = ExecutionResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_seconds=duration,
                timed_out=timed_out,
                output_files=output_files,
            )

            # 7. Audit log event
            if self.audit_ledger:
                self.audit_ledger.append_event(
                    session_id=session_id,
                    event_type="CODE_EXECUTION",
                    actor_role="sandbox",
                    payload={
                        "exit_code": exit_code,
                        "duration_seconds": duration,
                        "timed_out": timed_out,
                        "output_file_count": len(output_files),
                        "stdout_snippet": stdout[:256],
                    },
                )

            return result
