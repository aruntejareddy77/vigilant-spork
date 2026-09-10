"""
src/sovereign/models/adapters/http_local.py
Standardized Localhost HTTP Protocol Adapter for local inference runtimes.
"""
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request

from sovereign.models.adapter import BaseModelAdapter
from sovereign.models.manifest import ModelManifest
from sovereign.models.types import ChatMessage, ModelResponse, VisionRegion


class ModelInferenceError(Exception):
    """Raised when an inference call fails, times out, or returns an error."""
    pass


class SecurityException(Exception):
    """Raised when an adapter attempts a non-loopback network connection."""
    pass


class LocalHTTPModelAdapter(BaseModelAdapter):
    """
    HTTP client communicating with local OpenAI-compatible inference servers
    running strictly on loopback (127.0.0.1 / localhost).
    """

    def __init__(self, manifest: ModelManifest, timeout_seconds: float = 30.0):
        super().__init__(manifest)
        self.timeout_seconds = timeout_seconds
        self._is_loaded: bool = False

        endpoint = manifest.engine.endpoint_url or "http://127.0.0.1:8000/v1"
        self._validate_loopback_url(endpoint)
        self.base_url = endpoint.rstrip("/")

    @staticmethod
    def _validate_loopback_url(url: str) -> None:
        parsed = urllib.parse.urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if hostname not in ("127.0.0.1", "localhost", "::1"):
            raise SecurityException(
                f"Security Violation: Non-loopback endpoint '{hostname}' is strictly prohibited. "
                "Air-gapped sovereign operations permit only 127.0.0.1 or localhost endpoints."
            )

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def load(self) -> bool:
        """Verifies server responsiveness and marks adapter as loaded."""
        if self.health_check():
            self._is_loaded = True
            return True
        raise ModelInferenceError(
            f"Failed to connect to local inference engine at {self.base_url}. "
            "Ensure the local engine process is running on loopback."
        )

    def unload(self) -> bool:
        """Marks adapter as unloaded."""
        self._is_loaded = False
        return True

    def health_check(self) -> bool:
        """Probes the local engine endpoint."""
        # Try /models endpoint
        try:
            self._request_json("GET", "/models", timeout=3.0)
            return True
        except Exception:
            # Fall back to root URL probe
            try:
                self._validate_loopback_url(self.base_url)
                req = urllib.request.Request(self.base_url, method="GET")
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    return resp.status in (200, 404)
            except Exception:
                return False

    def _request_json(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Performs an HTTP request against the validated loopback endpoint."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        self._validate_loopback_url(url)

        req_timeout = timeout or self.timeout_seconds
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SovereignAIWorkbench/1.0",
        }
        if self.manifest.engine.api_key:
            headers["Authorization"] = f"Bearer {self.manifest.engine.api_key}"

        body_bytes = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=req_timeout) as resp:
                resp_bytes = resp.read()
                return json.loads(resp_bytes.decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise ModelInferenceError(
                f"Inference HTTP error {e.code} from {url}: {err_body}"
            ) from e
        except urllib.error.URLError as e:
            raise ModelInferenceError(
                f"Connection failed to local engine at {url}: {e.reason}"
            ) from e
        except TimeoutError as e:
            raise ModelInferenceError(
                f"Inference timed out after {req_timeout}s waiting for {url}"
            ) from e
        except Exception as e:
            raise ModelInferenceError(f"Unexpected inference error: {e}") from e

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> ModelResponse:
        """Executes text generation using the chat completions endpoint."""
        messages: List[ChatMessage] = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        messages.append(ChatMessage(role="user", content=prompt))
        return self.generate_chat(messages, **kwargs)

    def generate_chat(
        self,
        messages: List[ChatMessage],
        **kwargs: Any
    ) -> ModelResponse:
        """Executes multi-turn conversation turn via /chat/completions."""
        start_time = time.perf_counter()
        model_name = self.manifest.engine.model_name or self.model_id

        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }

        # Merge manifest engine parameters with call-specific kwargs
        params = dict(self.manifest.engine.parameters)
        params.update(kwargs)
        for key in ("temperature", "top_p", "max_tokens", "presence_penalty", "frequency_penalty"):
            if key in params:
                payload[key] = params[key]

        resp = self._request_json("POST", "/chat/completions", payload)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        try:
            choice = resp["choices"][0]
            text = choice["message"]["content"]
            finish_reason = choice.get("finish_reason", "stop")
            usage = resp.get("usage", {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            })
        except (KeyError, IndexError) as e:
            raise ModelInferenceError(f"Malformed response structure from engine: {resp}") from e

        return ModelResponse(
            text=text,
            usage=usage,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
            vision_regions=[],
            raw_payload=resp,
        )

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Computes embeddings via /embeddings."""
        model_name = self.manifest.engine.model_name or self.model_id
        payload = {
            "model": model_name,
            "input": texts,
        }
        resp = self._request_json("POST", "/embeddings", payload)

        try:
            data = resp["data"]
            # Sort by index to ensure original order
            sorted_data = sorted(data, key=lambda x: x.get("index", 0))
            return [item["embedding"] for item in sorted_data]
        except (KeyError, IndexError) as e:
            raise ModelInferenceError(f"Malformed embeddings response from engine: {resp}") from e

    def vision_infer(
        self,
        image_bytes: bytes,
        prompt: str,
        **kwargs: Any
    ) -> ModelResponse:
        """Executes vision reasoning via multimodal chat completions with base64 image."""
        import base64

        b64_img = base64.b64encode(image_bytes).decode("ascii")
        model_name = self.manifest.engine.model_name or self.model_id

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                    }
                ]
            }
        ]

        payload = {
            "model": model_name,
            "messages": messages,
        }
        payload.update(kwargs)

        start_time = time.perf_counter()
        resp = self._request_json("POST", "/chat/completions", payload)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        try:
            choice = resp["choices"][0]
            text = choice["message"]["content"]
            usage = resp.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        except Exception as e:
            raise ModelInferenceError(f"Malformed vision response from engine: {resp}") from e

        return ModelResponse(
            text=text,
            usage=usage,
            finish_reason="stop",
            latency_ms=latency_ms,
            vision_regions=[],
            raw_payload=resp,
        )
