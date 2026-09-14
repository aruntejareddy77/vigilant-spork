"""
src/sovereign/sdk/client.py
Lightweight, zero-heavy-dependency client for the Sovereign AI Workbench.
Built strictly on Python standard library modules (urllib.request, json, time, dataclasses).
"""
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Union
import urllib.error
import urllib.parse
import urllib.request

from sovereign.tools.schemas import UserRole
from sovereign.sdk.exceptions import (
    SovereignError,
    SovereignAPIError,
    RBACPermissionError,
    SovereignConnectionError,
)
from sovereign.sdk.models import (
    TaskStatus,
    TaskResult,
    VRAMStatus,
    AuditVerificationResult,
    NetworkTelemetryResult,
)


class _BaseNamespace:
    """Base helper for SDK namespace operations."""

    def __init__(self, client: "SovereignClient"):
        self.client = client


class TaskNamespace(_BaseNamespace):
    """Namespace for agent task lifecycle operations."""

    def submit(
        self,
        prompt: str,
        files: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> TaskResult:
        """
        Submit a new task to the agentic runtime.
        Immediately enforces least-privilege RBAC: raises RBACPermissionError if role is Auditor.
        """
        if self.client.role == UserRole.AUDITOR:
            raise RBACPermissionError(
                "Auditor role is restricted from submitting tasks per least-privilege policy (UI-05)"
            )

        payload = {
            "prompt": prompt,
            "files": files or [],
            "model_override": model,
        }
        res = self.client._request("POST", "/api/tasks", payload=payload)

        status_str = res.get("status", "SUBMITTED")
        try:
            status_enum = TaskStatus(status_str.upper())
        except ValueError:
            status_enum = TaskStatus.SUBMITTED

        return TaskResult(
            task_id=res["task_id"],
            thread_id=res.get("thread_id"),
            status=status_enum,
            raw=res,
        )

    def get_status(self, task_id: str) -> TaskResult:
        """Fetch current execution status, steps, and pending approvals for a task."""
        res = self.client._request("GET", f"/api/tasks/{task_id}")

        status_str = res.get("status", "UNKNOWN")
        try:
            status_enum = TaskStatus(status_str.upper())
        except ValueError:
            status_enum = TaskStatus.SUBMITTED

        output_val = None
        for step in reversed(res.get("steps", [])):
            if step.get("thought"):
                output_val = step["thought"]
                break

        return TaskResult(
            task_id=res.get("task_id", task_id),
            thread_id=res.get("thread_id"),
            status=status_enum,
            output=output_val,
            pending_approval=res.get("pending_approval"),
            artifacts=res.get("artifacts", []),
            steps=res.get("steps", []),
            raw=res,
        )

    def wait_for_completion(
        self,
        task_id: str,
        timeout_sec: int = 60,
        poll_interval: float = 1.0,
    ) -> TaskResult:
        """Poll task status until reaching a terminal state or timeout."""
        start_time = time.time()
        last_result = None

        while time.time() - start_time < timeout_sec:
            last_result = self.get_status(task_id)
            if last_result.status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.SUSPENDED,
                TaskStatus.REJECTED,
            ):
                return last_result
            time.sleep(poll_interval)

        if last_result:
            return last_result
        raise TimeoutError(f"Task '{task_id}' did not complete within {timeout_sec}s")

    def approve(self, task_id: str, notes: Optional[str] = None) -> TaskResult:
        """
        Submit HITL sign-off approval for a paused task deliverable.
        Immediately enforces least-privilege RBAC: raises RBACPermissionError if role is Auditor.
        """
        if self.client.role == UserRole.AUDITOR:
            raise RBACPermissionError(
                "Auditor role is restricted from approving tasks per least-privilege policy (UI-05)"
            )

        payload = {"decision": "approve", "notes": notes or "Operator approved via SDK"}
        res = self.client._request("POST", f"/api/tasks/{task_id}/resume", payload=payload)

        status_str = res.get("status", "RESUMED")
        try:
            status_enum = TaskStatus(status_str.upper())
        except ValueError:
            status_enum = TaskStatus.COMPLETED

        return TaskResult(
            task_id=task_id,
            status=status_enum,
            raw=res,
        )

    def reject(self, task_id: str, reason: Optional[str] = None) -> TaskResult:
        """
        Submit HITL rejection for a paused task deliverable.
        Immediately enforces least-privilege RBAC: raises RBACPermissionError if role is Auditor.
        """
        if self.client.role == UserRole.AUDITOR:
            raise RBACPermissionError(
                "Auditor role is restricted from rejecting tasks per least-privilege policy (UI-05)"
            )

        payload = {"decision": "reject", "notes": reason or "Operator rejected via SDK"}
        res = self.client._request("POST", f"/api/tasks/{task_id}/resume", payload=payload)

        status_str = res.get("status", "REJECTED")
        try:
            status_enum = TaskStatus(status_str.upper())
        except ValueError:
            status_enum = TaskStatus.REJECTED

        return TaskResult(
            task_id=task_id,
            status=status_enum,
            raw=res,
        )

    def download_artifact(
        self,
        task_id: str,
        filename: str,
        output_dir: Union[str, Path],
    ) -> Path:
        """
        Download a task deliverable artifact with strict path traversal verification (T-05-08).
        """
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        target_file = (out_dir / filename).resolve()
        # Enforce destination path stays strictly inside output_dir
        try:
            if not target_file.is_relative_to(out_dir):
                raise ValueError(
                    f"Path traversal detected: '{filename}' escapes target directory '{out_dir}'"
                )
        except AttributeError:
            if not str(target_file).startswith(str(out_dir)):
                raise ValueError(
                    f"Path traversal detected: '{filename}' escapes target directory '{out_dir}'"
                )

        data = self.client._request("GET", f"/api/tasks/{task_id}/artifacts/{filename}")
        if isinstance(data, dict):
            target_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        elif isinstance(data, bytes):
            target_file.write_bytes(data)
        elif isinstance(data, str):
            target_file.write_text(data, encoding="utf-8")

        return target_file


class ModelNamespace(_BaseNamespace):
    """Namespace for model catalog and VRAM scheduling inspection."""

    def list_models(self) -> List[Dict[str, Any]]:
        """List registered local models and capabilities."""
        res = self.client._request("GET", "/api/models")
        if isinstance(res, dict):
            return res.get("models", [])
        return res if isinstance(res, list) else []

    def vram_status(self) -> VRAMStatus:
        """Query current GPU VRAM allocation, headroom, and active models."""
        res = self.client._request("GET", "/api/models/vram")
        return VRAMStatus(
            total_mb=res.get("total_mb", 24576),
            usable_mb=res.get("usable_mb", 22528),
            allocated_mb=res.get("allocated_mb", 0),
            available_mb=res.get("available_mb", 22528),
            loaded_models=res.get("loaded_models", []),
        )


class NetworkNamespace(_BaseNamespace):
    """Namespace for network policy inspection, socket telemetry, and egress testing."""

    def get_status(self) -> Dict[str, Any]:
        """Fetch current network isolation policy and allowed CIDRs."""
        return self.client._request("GET", "/api/network/status")

    def get_telemetry(self, limit: int = 50) -> List[NetworkTelemetryResult]:
        """Fetch recent socket telemetry records captured by the NetworkMonitor."""
        res = self.client._request("GET", "/api/network/telemetry")
        events = res.get("recent_events", []) if isinstance(res, dict) else []
        results: List[NetworkTelemetryResult] = []
        for e in events[:limit]:
            results.append(
                NetworkTelemetryResult(
                    timestamp_iso=e.get("timestamp_iso", ""),
                    protocol=e.get("protocol", "tcp"),
                    local_address=e.get("local_address", ""),
                    remote_address=e.get("remote_address"),
                    pid=e.get("pid"),
                    process_name=e.get("process_name"),
                    verdict=e.get("verdict", "BLOCKED"),
                    reason=e.get("reason"),
                )
            )
        return results

    def run_egress_test(self) -> Dict[str, Any]:
        """Execute synthetic egress probe suite and return isolation verification."""
        return self.client._request("POST", "/api/network/test-egress")


class AuditNamespace(_BaseNamespace):
    """Namespace for cryptographic audit ledger inspection and verification."""

    def inspect(self) -> Dict[str, Any]:
        """Inspect audit ledger statistics and session counts."""
        return self.client._request("GET", "/api/audit/inspect")

    def verify(self) -> AuditVerificationResult:
        """Execute SHA-256 hash-chain verification across the audit ledger."""
        res = self.client._request("GET", "/api/audit/verify")
        return AuditVerificationResult(
            is_valid=res.get("is_valid", True),
            records_checked=res.get("records_checked", 0),
            tip_hash=res.get("tip_hash"),
            error_message=res.get("error_message"),
        )

    def export_session(self, session_id: str, output_file: Union[str, Path]) -> Path:
        """Export session audit records to an output file."""
        out_path = Path(output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        res = self.client._request("GET", f"/api/audit/export?session_id={urllib.parse.quote(session_id)}")
        if isinstance(res, (dict, list)):
            out_path.write_text(json.dumps(res, indent=2), encoding="utf-8")
        elif isinstance(res, bytes):
            out_path.write_bytes(res)
        elif isinstance(res, str):
            out_path.write_text(res, encoding="utf-8")

        return out_path


class SovereignClient:
    """
    Sovereign AI Workbench Client.
    Zero-heavy-dependency Python SDK communicating with the Sovereign REST API.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        role: Union[UserRole, str] = UserRole.ENGINEER,
        token: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        if isinstance(role, str):
            self.role = UserRole(role.lower())
        else:
            self.role = role
        self.token = token
        self.timeout = timeout

        # Namespaces
        self.tasks = TaskNamespace(self)
        self.models = ModelNamespace(self)
        self.network = NetworkNamespace(self)
        self.audit = AuditNamespace(self)

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            if query:
                url = f"{url}?{query}"

        headers = {
            "Accept": "application/json",
            "User-Agent": "Sovereign-SDK/0.1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.role:
            headers["X-Sovereign-Role"] = self.role.value

        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_bytes = resp.read()
                if not resp_bytes:
                    return {}
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    return json.loads(resp_bytes.decode("utf-8"))
                return resp_bytes
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                err_bytes = exc.read()
                err_body = err_bytes.decode("utf-8")
                err_json = json.loads(err_body)
                detail = err_json.get("detail", err_body)
            except Exception:
                detail = exc.reason

            if exc.code == 403:
                raise RBACPermissionError(
                    f"Access denied (403 Forbidden): {detail or 'Role ' + self.role.value + ' lacks clearance'}"
                ) from exc
            raise SovereignAPIError(status_code=exc.code, message=str(detail), detail=detail) from exc
        except urllib.error.URLError as exc:
            raise SovereignConnectionError(f"Failed to connect to {self.base_url}: {exc.reason}") from exc
        except Exception as exc:
            raise SovereignError(f"Request failed: {exc}") from exc
