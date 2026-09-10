"""
tests/test_models/test_local_adapters.py
Unit tests for LocalHTTPModelAdapter, engine subclasses, and loopback security enforcement.
"""
from io import BytesIO
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from sovereign.models.adapters.http_local import (
    LocalHTTPModelAdapter,
    ModelInferenceError,
    SecurityException,
)
from sovereign.models.adapters.engines import (
    SGLangAdapter,
    VLLMAdapter,
    OllamaAdapter,
    LlamaCppAdapter,
)
from sovereign.models.manifest import (
    EngineConfig,
    EngineType,
    ModelCapability,
    ModelManifest,
    load_manifest,
)
from sovereign.models.types import ChatMessage

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "models"


@pytest.fixture
def sample_http_manifest() -> ModelManifest:
    return load_manifest(FIXTURES_DIR / "qwen_reasoning.yaml")


def test_loopback_security_enforcement():
    """Verify non-loopback endpoints are strictly blocked at initialization."""
    # Manifest schema blocks it, but direct initialization must also fail closed
    manifest = ModelManifest(
        model_id="test",
        name="Test",
        family="test",
        capabilities=[ModelCapability.REASONING],
        context_window=4096,
        vram_estimate_mb=1024,
        engine=EngineConfig(type=EngineType.VLLM, endpoint_url="http://127.0.0.1:8000/v1"),
    )
    # Manually mutate to bypass schema check to test runtime adapter defense
    manifest.engine.endpoint_url = "http://192.168.1.50:8000/v1"
    with pytest.raises(SecurityException) as exc_info:
        LocalHTTPModelAdapter(manifest)
    assert "Security Violation" in str(exc_info.value)


def test_adapter_generate_chat_success(sample_http_manifest):
    """Verify successful parsing of OpenAI-compatible chat response."""
    adapter = LocalHTTPModelAdapter(sample_http_manifest)

    mock_resp_data = {
        "id": "chatcmpl-123",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Inspection completed successfully. No anomalies detected.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 8,
            "total_tokens": 20,
        },
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = adapter.generate("Check unit T-401")
        assert res.text == "Inspection completed successfully. No anomalies detected."
        assert res.usage["total_tokens"] == 20
        assert res.finish_reason == "stop"


def test_adapter_embed_success(sample_http_manifest):
    """Verify successful parsing of embeddings response."""
    adapter = LocalHTTPModelAdapter(sample_http_manifest)

    mock_resp_data = {
        "data": [
            {"index": 0, "embedding": [0.1, 0.2, 0.3]},
            {"index": 1, "embedding": [0.4, 0.5, 0.6]},
        ]
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        vecs = adapter.embed(["Text A", "Text B"])
        assert len(vecs) == 2
        assert vecs[0] == [0.1, 0.2, 0.3]
        assert vecs[1] == [0.4, 0.5, 0.6]


def test_adapter_error_handling(sample_http_manifest):
    """Verify HTTP and connection errors are wrapped in ModelInferenceError."""
    adapter = LocalHTTPModelAdapter(sample_http_manifest)

    # 1. HTTP Error 500
    http_err = urllib.error.HTTPError(
        url="http://127.0.0.1:30000/v1/chat/completions",
        code=500,
        msg="Internal Server Error",
        hdrs={},
        fp=BytesIO(b"Engine Out of Memory"),
    )
    with patch("urllib.request.urlopen", side_effect=http_err):
        with pytest.raises(ModelInferenceError) as exc_info:
            adapter.generate("Test prompt")
        assert "500" in str(exc_info.value)
        assert "Out of Memory" in str(exc_info.value)

    # 2. Connection refused (URLError)
    url_err = urllib.error.URLError(reason="Connection refused")
    with patch("urllib.request.urlopen", side_effect=url_err):
        with pytest.raises(ModelInferenceError) as exc_info:
            adapter.generate("Test prompt")
        assert "Connection failed" in str(exc_info.value)


def test_engine_subclasses_initialization():
    """Verify specialized engine adapters configure default loopback URLs."""
    def create_manifest(etype: EngineType) -> ModelManifest:
        return ModelManifest(
            model_id=f"test-{etype.value}",
            name="Test",
            family="test",
            capabilities=[ModelCapability.REASONING],
            context_window=4096,
            vram_estimate_mb=1024,
            engine=EngineConfig(type=etype),
        )

    sg = SGLangAdapter(create_manifest(EngineType.SGLANG))
    assert sg.base_url == "http://127.0.0.1:30000/v1"

    vl = VLLMAdapter(create_manifest(EngineType.VLLM))
    assert vl.base_url == "http://127.0.0.1:8000/v1"

    ol = OllamaAdapter(create_manifest(EngineType.OLLAMA))
    assert ol.base_url == "http://127.0.0.1:11434/v1"

    lc = LlamaCppAdapter(create_manifest(EngineType.LLAMACPP))
    assert lc.base_url == "http://127.0.0.1:8080/v1"
