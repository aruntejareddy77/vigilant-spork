"""
tests/test_lineage/test_prov_schema.py
Unit tests for W3C PROV-O inspired lineage metadata schema
"""
import json
from sovereign.lineage.models import (
    DeliverableInfo,
    LineageMetadata,
    ModelInfo,
    SourceDocumentCitation,
    ToolExecutionRecord,
)


def test_lineage_metadata_serialization():
    metadata = LineageMetadata(
        deliverable=DeliverableInfo(
            file_name="reactor_report.docx",
            file_sha256="abc12345def67890",
            file_size_bytes=1048576,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        session_id="session-42",
        user_id="operator_01",
        user_role="Senior Plant Engineer",
        model=ModelInfo(
            model_id="qwen-2.5-72b-instruct",
            weights_sha256="fedcba9876543210",
            context_window=32768,
            inference_engine="vLLM-offline",
        ),
        source_documents=[
            SourceDocumentCitation(
                document_id="doc-001",
                file_name="pfd_schematic.pdf",
                file_sha256="1122334455667788",
                page_number=3,
                bounding_box=[0.1, 0.2, 0.8, 0.9],
                snippet="Reactor vessel R-101 design pressure 45 bar",
            )
        ],
        tools=[
            ToolExecutionRecord(
                tool_name="thermodynamic_calculator",
                parameters_hash="paramshash123",
                execution_time_ms=45.2,
                output_hash="out123",
            )
        ],
        audit_start_seq=10,
        audit_end_seq=15,
        audit_tip_hash="tiphash999",
        custom_attributes={"plant_unit": "FCCU-2"},
    )

    json_str = metadata.model_dump_json()
    parsed = LineageMetadata.model_validate_json(json_str)

    assert parsed.session_id == "session-42"
    assert parsed.deliverable.file_name == "reactor_report.docx"
    assert parsed.model.model_id == "qwen-2.5-72b-instruct"
    assert len(parsed.source_documents) == 1
    assert parsed.source_documents[0].page_number == 3
    assert len(parsed.tools) == 1
    assert parsed.audit_start_seq == 10
    assert parsed.audit_end_seq == 15
    assert parsed.custom_attributes["plant_unit"] == "FCCU-2"


def test_w3c_prov_o_export():
    metadata = LineageMetadata(
        deliverable=DeliverableInfo(
            file_name="safety_analysis.xlsx",
            file_sha256="aaabbbccc111222",
            file_size_bytes=4096,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        session_id="sess-99",
        user_id="user_admin",
        user_role="Compliance Officer",
        model=ModelInfo(
            model_id="deepseek-r1-distill",
            weights_sha256="999888777666",
        ),
        source_documents=[
            SourceDocumentCitation(
                document_id="doc_std_101",
                file_name="osha_standard.pdf",
                file_sha256="ffeeddccbbaa",
                page_number=12,
                snippet="Pressure safety valve relief capacity requirements",
            )
        ],
        tools=[
            ToolExecutionRecord(
                tool_name="code_interpreter",
                parameters_hash="codehash123",
            )
        ],
        audit_start_seq=1,
        audit_end_seq=5,
        audit_tip_hash="chain_tip_001",
    )

    prov_json = metadata.to_prov_o()

    assert "prefix" in prov_json
    assert prov_json["prefix"]["prov"] == "http://www.w3.org/ns/prov#"
    assert "entity" in prov_json
    assert "sovg:safety_analysis.xlsx" in prov_json["entity"]
    assert "sovg:doc_std_101" in prov_json["entity"]

    assert "activity" in prov_json
    assert "sovg:activity-sess-99" in prov_json["activity"]

    assert "agent" in prov_json
    assert "sovg:user-user_admin" in prov_json["agent"]
    assert "sovg:model-deepseek-r1-distill" in prov_json["agent"]

    assert "wasGeneratedBy" in prov_json
    assert "wasAttributedTo" in prov_json
    assert "used" in prov_json
    assert "wasDerivedFrom" in prov_json
