"""
tests/test_lineage/test_format_injectors.py
Unit tests for format-native lineage metadata injectors (.docx, .xlsx, .pptx, .png, .py, .sh)
"""
import io
import shutil
from pathlib import Path
from PIL import Image
import pytest

from sovereign.lineage.engine import LineageEngine
from sovereign.lineage.injectors.code import extract_code_lineage, inject_code_lineage
from sovereign.lineage.injectors.ooxml import extract_ooxml_lineage, inject_ooxml_lineage
from sovereign.lineage.injectors.png import extract_png_lineage, inject_png_lineage
from sovereign.lineage.models import DeliverableInfo, LineageMetadata, ModelInfo

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "minimal_templates"


@pytest.mark.parametrize("template_name", ["template.docx", "template.xlsx", "template.pptx"])
def test_ooxml_injector_roundtrip(template_name):
    template_path = FIXTURES_DIR / template_name
    assert template_path.exists(), f"Fixture missing: {template_path}"

    raw_bytes = template_path.read_bytes()
    test_props = {
        "sovereign_session_id": "sess-test-123",
        "sovereign_model_id": "qwen-2.5-72b",
        "sovereign_weights_sha256": "abc111222333",
        "sovereign_audit_tip": "tip-456-hash",
        "sovereign_audit_start_seq": "5",
        "sovereign_audit_end_seq": "10",
        "sovereign_timestamp": "2026-09-10T12:00:00Z",
    }

    injected = inject_ooxml_lineage(raw_bytes, test_props)
    assert len(injected) > 0

    extracted = extract_ooxml_lineage(injected)
    for k, v in test_props.items():
        assert extracted.get(k) == v, f"Failed match on {k}: {extracted.get(k)} != {v}"


def test_png_injector_roundtrip():
    # Create simple PNG in memory
    img = Image.new("RGBA", (32, 32), color=(255, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    summary_text = '{"session_id": "png-sess-1", "model": "test-model"}'
    injected = inject_png_lineage(raw_bytes, summary_text)
    assert len(injected) > len(raw_bytes)

    extracted = extract_png_lineage(injected)
    assert extracted == summary_text


def test_code_injector_python():
    py_code = "#!/usr/bin/env python3\nimport sys\n\ndef main():\n    print('hello')\n"
    metadata = LineageMetadata(
        deliverable=DeliverableInfo(file_name="script.py"),
        session_id="sess-py-99",
        user_id="dev",
        user_role="engineer",
        model=ModelInfo(model_id="qwen-coder", weights_sha256="deadbeef123"),
        audit_start_seq=1,
        audit_end_seq=3,
        audit_tip_hash="tip999",
    )

    injected = inject_code_lineage(py_code, ".py", metadata)
    assert injected.startswith("#!/usr/bin/env python3\n")
    assert "SOVEREIGN DELIVERABLE LINEAGE" in injected
    assert "session_id: sess-py-99" in injected
    assert "model_id: qwen-coder" in injected

    extracted = extract_code_lineage(injected)
    assert extracted is not None
    assert extracted["session_id"] == "sess-py-99"
    assert extracted["model_id"] == "qwen-coder"
    assert extracted["weights_sha256"] == "deadbeef123"
    assert extracted["audit_tip_hash"] == "tip999"
    assert extracted["audit_start_seq"] == "1"
    assert extracted["audit_end_seq"] == "3"


def test_code_injector_shell():
    sh_code = "#!/bin/bash\necho 'running analysis'\n"
    metadata = LineageMetadata(
        deliverable=DeliverableInfo(file_name="deploy.sh"),
        session_id="sess-sh-10",
        user_id="ops",
        user_role="admin",
        model=ModelInfo(model_id="deepseek-coder", weights_sha256="c0ffee456"),
        audit_start_seq=20,
        audit_end_seq=25,
        audit_tip_hash="tipc0ffee",
    )

    injected = inject_code_lineage(sh_code, ".sh", metadata)
    assert injected.startswith("#!/bin/bash\n")
    assert "# --- SOVEREIGN DELIVERABLE LINEAGE ---" in injected

    extracted = extract_code_lineage(injected)
    assert extracted is not None
    assert extracted["session_id"] == "sess-sh-10"
    assert extracted["model_id"] == "deepseek-coder"
    assert extracted["weights_sha256"] == "c0ffee456"
    assert extracted["audit_tip_hash"] == "tipc0ffee"
    assert extracted["audit_start_seq"] == "20"
    assert extracted["audit_end_seq"] == "25"


def test_lineage_engine_package_deliverable(tmp_path):
    # Copy minimal template to tmp_path
    src_docx = FIXTURES_DIR / "template.docx"
    test_docx = tmp_path / "output_report.docx"
    shutil.copy(src_docx, test_docx)

    metadata = LineageMetadata(
        deliverable=DeliverableInfo(file_name="output_report.docx"),
        session_id="engine-sess-1",
        user_id="engineer_01",
        user_role="Engineer",
        model=ModelInfo(model_id="qwen-2.5", weights_sha256="weightshash789"),
        audit_start_seq=50,
        audit_end_seq=55,
        audit_tip_hash="tip789",
    )

    sidecar_path = LineageEngine.package_deliverable(test_docx, metadata)
    assert sidecar_path.exists()
    assert sidecar_path.name == "output_report.docx.lineage.json"

    # Verify deliverable SHA-256 matches actual file on disk
    computed_sha = LineageEngine.compute_sha256(test_docx)
    assert metadata.deliverable.file_sha256 == computed_sha
    assert metadata.deliverable.file_size_bytes == test_docx.stat().st_size

    # Verify embedded properties in packaged docx
    extracted_props = extract_ooxml_lineage(test_docx.read_bytes())
    assert extracted_props["sovereign_session_id"] == "engine-sess-1"
    assert extracted_props["sovereign_model_id"] == "qwen-2.5"

    # Verify sidecar reload
    loaded = LineageEngine.load_sidecar(sidecar_path)
    assert loaded.deliverable.file_sha256 == computed_sha
    assert loaded.session_id == "engine-sess-1"
