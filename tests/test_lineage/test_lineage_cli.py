"""
tests/test_lineage/test_lineage_cli.py
Integration tests for CLI commands 'sovereign lineage verify' and 'sovereign lineage trace'
"""
import shutil
from pathlib import Path
from click.testing import CliRunner

from sovereign.audit.ledger import AuditLedger
from sovereign.cli import cli
from sovereign.lineage.engine import LineageEngine
from sovereign.lineage.models import (
    DeliverableInfo,
    LineageMetadata,
    ModelInfo,
    SourceDocumentCitation,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "minimal_templates"


def test_cli_lineage_verify_valid(tmp_path):
    runner = CliRunner()

    # 1. Create audit ledger with span
    ledger_path = tmp_path / "audit_ledger.jsonl"
    ledger = AuditLedger(ledger_path)
    ev0 = ledger.append_event("session_test", "TASK_START", "system", {"task": "report"})
    ev1 = ledger.append_event("session_test", "MODEL_INFERENCE", "model", {"prompt": "analyze"})
    ev2 = ledger.append_event("session_test", "TASK_COMPLETE", "system", {"status": "ok"})

    # 2. Prepare deliverable
    src_docx = FIXTURES_DIR / "template.docx"
    doc_path = tmp_path / "quarterly_audit.docx"
    shutil.copy(src_docx, doc_path)

    metadata = LineageMetadata(
        deliverable=DeliverableInfo(file_name="quarterly_audit.docx"),
        session_id="session_test",
        user_id="auditor_01",
        user_role="Lead Auditor",
        model=ModelInfo(model_id="qwen-2.5", weights_sha256="deadbeef01"),
        audit_start_seq=0,
        audit_end_seq=2,
        audit_tip_hash=ev2.entry_hash,
    )

    LineageEngine.package_deliverable(doc_path, metadata)

    # 3. Verify via CLI
    res = runner.invoke(cli, ["lineage", "verify", str(doc_path), "--ledger", str(ledger_path)])
    assert res.exit_code == 0, res.output
    assert "Lineage verification PASSED" in res.output
    assert "Audit Ledger Span    : PASS (0..2)" in res.output


def test_cli_lineage_verify_tampered_bytes(tmp_path):
    runner = CliRunner()

    py_script = tmp_path / "calc.py"
    py_script.write_text("print('original code')\n", encoding="utf-8")

    metadata = LineageMetadata(
        deliverable=DeliverableInfo(file_name="calc.py"),
        session_id="tamper_session",
        user_id="dev",
        user_role="eng",
        model=ModelInfo(model_id="coder", weights_sha256="abc"),
        audit_start_seq=0,
        audit_end_seq=0,
        audit_tip_hash="tip",
    )

    LineageEngine.package_deliverable(py_script, metadata)

    # Tamper with file
    content = py_script.read_text(encoding="utf-8")
    py_script.write_text(content + "\n# malicious injected line\n", encoding="utf-8")

    res = runner.invoke(cli, ["lineage", "verify", str(py_script)])
    assert res.exit_code == 1
    assert "Lineage verification FAILED" in res.output
    assert "Deliverable SHA-256 mismatch" in res.output


def test_cli_lineage_verify_missing_sidecar(tmp_path):
    runner = CliRunner()

    py_script = tmp_path / "plain.py"
    py_script.write_text("print('no sidecar')\n", encoding="utf-8")

    res = runner.invoke(cli, ["lineage", "verify", str(py_script)])
    assert res.exit_code == 1
    assert "Lineage sidecar manifest not found" in res.output


def test_cli_lineage_verify_broken_audit_span(tmp_path):
    runner = CliRunner()

    # Create ledger with event from a different session
    ledger_path = tmp_path / "mismatch_ledger.jsonl"
    ledger = AuditLedger(ledger_path)
    ledger.append_event("other_session", "EVENT_A", "user", {})
    ev1 = ledger.append_event("other_session", "EVENT_B", "user", {})

    doc_path = tmp_path / "script.py"
    doc_path.write_text("def test(): pass\n", encoding="utf-8")

    metadata = LineageMetadata(
        deliverable=DeliverableInfo(file_name="script.py"),
        session_id="target_session",
        user_id="dev",
        user_role="eng",
        model=ModelInfo(model_id="coder", weights_sha256="abc"),
        audit_start_seq=0,
        audit_end_seq=1,
        audit_tip_hash=ev1.entry_hash,
    )

    LineageEngine.package_deliverable(doc_path, metadata)

    res = runner.invoke(cli, ["lineage", "verify", str(doc_path), "--ledger", str(ledger_path)])
    assert res.exit_code == 1
    assert "Audit ledger span verification failed" in res.output


def test_cli_lineage_trace(tmp_path):
    runner = CliRunner()

    source_doc_hash = "1111222233334444555566667777888811112222333344445555666677778888"
    unrelated_hash = "9999888877776666555544443333222211110000999988887777666655554444"

    # Deliverable 1 cites source_doc_hash
    f1 = tmp_path / "deliv1.py"
    f1.write_text("print(1)\n", encoding="utf-8")
    meta1 = LineageMetadata(
        deliverable=DeliverableInfo(file_name="deliv1.py"),
        session_id="sess-1",
        user_id="user1",
        user_role="eng",
        model=ModelInfo(model_id="m1", weights_sha256="w1"),
        source_documents=[
            SourceDocumentCitation(
                document_id="doc-ref-1",
                file_name="specs.pdf",
                file_sha256=source_doc_hash,
            )
        ],
        audit_start_seq=0,
        audit_end_seq=1,
        audit_tip_hash="tip1",
    )
    LineageEngine.package_deliverable(f1, meta1)

    # Deliverable 2 cites unrelated_hash
    f2 = tmp_path / "deliv2.py"
    f2.write_text("print(2)\n", encoding="utf-8")
    meta2 = LineageMetadata(
        deliverable=DeliverableInfo(file_name="deliv2.py"),
        session_id="sess-2",
        user_id="user2",
        user_role="eng",
        model=ModelInfo(model_id="m2", weights_sha256="w2"),
        source_documents=[
            SourceDocumentCitation(
                document_id="doc-ref-2",
                file_name="other.pdf",
                file_sha256=unrelated_hash,
            )
        ],
        audit_start_seq=0,
        audit_end_seq=1,
        audit_tip_hash="tip2",
    )
    LineageEngine.package_deliverable(f2, meta2)

    # Deliverable 3 cites source_doc_hash
    f3 = tmp_path / "deliv3.py"
    f3.write_text("print(3)\n", encoding="utf-8")
    meta3 = LineageMetadata(
        deliverable=DeliverableInfo(file_name="deliv3.py"),
        session_id="sess-3",
        user_id="user3",
        user_role="eng",
        model=ModelInfo(model_id="m3", weights_sha256="w3"),
        source_documents=[
            SourceDocumentCitation(
                document_id="doc-ref-1-b",
                file_name="specs.pdf",
                file_sha256=source_doc_hash,
            )
        ],
        audit_start_seq=0,
        audit_end_seq=1,
        audit_tip_hash="tip3",
    )
    LineageEngine.package_deliverable(f3, meta3)

    # Trace by SHA-256 string
    res_trace = runner.invoke(cli, ["lineage", "trace", source_doc_hash, "--dir", str(tmp_path)])
    assert res_trace.exit_code == 0
    assert "Matching Deliverables: 2" in res_trace.output
    assert "deliv1.py" in res_trace.output
    assert "deliv3.py" in res_trace.output
    assert "deliv2.py" not in res_trace.output

    # Trace using actual source file
    source_file = tmp_path / "specs_input.pdf"
    source_file.write_bytes(b"content for specs input")
    source_computed_hash = LineageEngine.compute_sha256(source_file)

    # Package deliverable citing source_computed_hash
    f4 = tmp_path / "deliv4.py"
    f4.write_text("print(4)\n", encoding="utf-8")
    meta4 = LineageMetadata(
        deliverable=DeliverableInfo(file_name="deliv4.py"),
        session_id="sess-4",
        user_id="user4",
        user_role="eng",
        model=ModelInfo(model_id="m4", weights_sha256="w4"),
        source_documents=[
            SourceDocumentCitation(
                document_id="doc-source-file",
                file_name="specs_input.pdf",
                file_sha256=source_computed_hash,
            )
        ],
        audit_start_seq=0,
        audit_end_seq=1,
        audit_tip_hash="tip4",
    )
    LineageEngine.package_deliverable(f4, meta4)

    res_file_trace = runner.invoke(cli, ["lineage", "trace", str(source_file), "--dir", str(tmp_path)])
    assert res_file_trace.exit_code == 0
    assert "Matching Deliverables: 1" in res_file_trace.output
    assert "deliv4.py" in res_file_trace.output
