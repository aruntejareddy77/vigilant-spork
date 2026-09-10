"""
tests/test_models/test_model_manifest.py
Unit tests for ModelManifest schema validation and parsing.
"""
from pathlib import Path
import pytest
from pydantic import ValidationError

from sovereign.models.manifest import (
    EngineConfig,
    EngineType,
    ModelCapability,
    ModelManifest,
    load_manifest,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "models"


def test_load_valid_fixture_manifests():
    """Verify all static model manifest fixtures parse cleanly."""
    fixtures = [
        "qwen_reasoning.yaml",
        "qwen_coder.yaml",
        "florence_vision.yaml",
        "bge_embedding.yaml",
        "mock_default.yaml",
    ]

    for fname in fixtures:
        fpath = FIXTURES_DIR / fname
        assert fpath.exists(), f"Fixture missing: {fpath}"
        manifest = load_manifest(fpath)
        assert manifest.model_id
        assert manifest.name
        assert manifest.vram_estimate_mb > 0
        assert manifest.context_window > 0
        assert len(manifest.capabilities) > 0


def test_has_capability_helper():
    """Verify has_capability works with enum and string values."""
    qwen = load_manifest(FIXTURES_DIR / "qwen_reasoning.yaml")
    assert qwen.has_capability(ModelCapability.REASONING)
    assert qwen.has_capability("text_drafting")
    assert not qwen.has_capability(ModelCapability.VISION_MULTIMODAL)
    assert not qwen.has_capability("non_existent_capability")


def test_reject_non_loopback_endpoint():
    """Verify endpoint_url is strictly restricted to localhost/127.0.0.1 (zero-egress rule)."""
    with pytest.raises(ValidationError) as exc_info:
        EngineConfig(
            type=EngineType.VLLM,
            endpoint_url="http://api.openai.com/v1",
        )
    assert "not permitted" in str(exc_info.value)

    # Intranet or public IPs must also be rejected for model engines (must be local server)
    with pytest.raises(ValidationError):
        EngineConfig(
            type=EngineType.SGLANG,
            endpoint_url="http://192.168.1.100:8000/v1",
        )

    # Loopback addresses must pass
    c1 = EngineConfig(type=EngineType.SGLANG, endpoint_url="http://127.0.0.1:30000/v1")
    assert c1.endpoint_url == "http://127.0.0.1:30000/v1"
    c2 = EngineConfig(type=EngineType.VLLM, endpoint_url="http://localhost:8000/v1")
    assert c2.endpoint_url == "http://localhost:8000/v1"


def test_reject_invalid_vram_and_context_window():
    """Verify numerical boundaries on VRAM and context window."""
    valid_engine = EngineConfig(type=EngineType.MOCK)

    with pytest.raises(ValidationError):
        ModelManifest(
            model_id="test",
            name="Test",
            family="test",
            capabilities=[ModelCapability.REASONING],
            context_window=0,  # Invalid: must be > 0
            vram_estimate_mb=1024,
            engine=valid_engine,
        )

    with pytest.raises(ValidationError):
        ModelManifest(
            model_id="test",
            name="Test",
            family="test",
            capabilities=[ModelCapability.REASONING],
            context_window=4096,
            vram_estimate_mb=-500,  # Invalid: must be > 0
            engine=valid_engine,
        )


def test_reject_invalid_sha256_format():
    """Verify weights_sha256 validation."""
    from sovereign.models.manifest import IntegrityConfig

    with pytest.raises(ValidationError):
        IntegrityConfig(weights_sha256="not_a_64_char_hash")

    with pytest.raises(ValidationError):
        IntegrityConfig(weights_sha256="z" * 64)  # Invalid hex char

    # Valid hex passes
    valid_hash = "a" * 64
    cfg = IntegrityConfig(weights_sha256=valid_hash)
    assert cfg.weights_sha256 == valid_hash


def test_load_manifest_json(tmp_path):
    """Verify load_manifest works with JSON format."""
    json_data = {
        "schema_version": "1.0.0",
        "model_id": "json-model",
        "name": "JSON Model",
        "family": "custom",
        "capabilities": ["code_generation"],
        "context_window": 8192,
        "vram_estimate_mb": 4096,
        "engine": {
            "type": "mock"
        }
    }
    p = tmp_path / "model.json"
    import json
    p.write_text(json.dumps(json_data), encoding="utf-8")

    manifest = load_manifest(p)
    assert manifest.model_id == "json-model"
    assert manifest.has_capability(ModelCapability.CODE_GENERATION)
