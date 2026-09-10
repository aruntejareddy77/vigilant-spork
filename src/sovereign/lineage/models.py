"""
src/sovereign/lineage/models.py
W3C PROV-O Inspired Lineage Metadata Models
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DeliverableInfo(BaseModel):
    file_name: str
    file_sha256: str = ""
    file_size_bytes: int = 0
    media_type: str = "application/octet-stream"


class ModelInfo(BaseModel):
    model_id: str
    weights_sha256: str
    context_window: Optional[int] = None
    inference_engine: Optional[str] = None


class SourceDocumentCitation(BaseModel):
    document_id: str
    file_name: str
    file_sha256: str
    page_number: Optional[int] = None
    bounding_box: Optional[List[float]] = None  # Normalized [x0, y0, x1, y1]
    snippet: Optional[str] = None


class ToolExecutionRecord(BaseModel):
    tool_name: str
    parameters_hash: str
    execution_time_ms: Optional[float] = None
    output_hash: Optional[str] = None


class LineageMetadata(BaseModel):
    schema_version: str = "1.0.0"
    generated_iso: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    deliverable: DeliverableInfo
    session_id: str
    user_id: str
    user_role: str
    model: ModelInfo
    source_documents: List[SourceDocumentCitation] = Field(default_factory=list)
    tools: List[ToolExecutionRecord] = Field(default_factory=list)
    audit_start_seq: int
    audit_end_seq: int
    audit_tip_hash: str
    custom_attributes: Dict[str, Any] = Field(default_factory=dict)

    def to_prov_o(self) -> Dict[str, Any]:
        """
        Exports a W3C PROV-O aligned JSON structure (PROV-JSON)
        explicitly detailing Entities, Activities, Agents, and relations.
        """
        prefix = {
            "prov": "http://www.w3.org/ns/prov#",
            "sovg": "https://sovereign.local/lineage/v1#"
        }
        entity = {
            f"sovg:{self.deliverable.file_name}": {
                "prov:type": "sovg:Deliverable",
                "sovg:sha256": self.deliverable.file_sha256,
                "sovg:sizeBytes": self.deliverable.file_size_bytes,
                "sovg:mediaType": self.deliverable.media_type,
            }
        }
        for doc in self.source_documents:
            entity[f"sovg:{doc.document_id}"] = {
                "prov:type": "sovg:SourceDocument",
                "sovg:fileName": doc.file_name,
                "sovg:sha256": doc.file_sha256,
                "sovg:page": doc.page_number,
                "sovg:snippet": doc.snippet,
            }

        activity = {
            f"sovg:activity-{self.session_id}": {
                "prov:type": "sovg:GenerationTask",
                "prov:startTime": self.generated_iso,
                "sovg:auditStartSeq": self.audit_start_seq,
                "sovg:auditEndSeq": self.audit_end_seq,
                "sovg:auditTipHash": self.audit_tip_hash,
            }
        }
        for i, tool in enumerate(self.tools):
            activity[f"sovg:tool-{tool.tool_name}-{i}"] = {
                "prov:type": "sovg:ToolExecution",
                "sovg:toolName": tool.tool_name,
                "sovg:parametersHash": tool.parameters_hash,
                "sovg:outputHash": tool.output_hash,
                "sovg:executionTimeMs": tool.execution_time_ms,
            }

        agent = {
            f"sovg:user-{self.user_id}": {
                "prov:type": "prov:Person",
                "sovg:role": self.user_role,
            },
            f"sovg:model-{self.model.model_id}": {
                "prov:type": "prov:SoftwareAgent",
                "sovg:weightsSha256": self.model.weights_sha256,
            }
        }

        wasGeneratedBy = {
            "_:gen1": {
                "prov:entity": f"sovg:{self.deliverable.file_name}",
                "prov:activity": f"sovg:activity-{self.session_id}",
            }
        }

        wasAttributedTo = {
            "_:attr1": {
                "prov:entity": f"sovg:{self.deliverable.file_name}",
                "prov:agent": f"sovg:user-{self.user_id}",
            },
            "_:attr2": {
                "prov:entity": f"sovg:{self.deliverable.file_name}",
                "prov:agent": f"sovg:model-{self.model.model_id}",
            }
        }

        used = {}
        wasDerivedFrom = {}
        for i, doc in enumerate(self.source_documents):
            used[f"_:used{i}"] = {
                "prov:activity": f"sovg:activity-{self.session_id}",
                "prov:entity": f"sovg:{doc.document_id}",
            }
            wasDerivedFrom[f"_:der{i}"] = {
                "prov:generatedEntity": f"sovg:{self.deliverable.file_name}",
                "prov:usedEntity": f"sovg:{doc.document_id}",
            }

        return {
            "prefix": prefix,
            "entity": entity,
            "activity": activity,
            "agent": agent,
            "wasGeneratedBy": wasGeneratedBy,
            "wasAttributedTo": wasAttributedTo,
            "used": used,
            "wasDerivedFrom": wasDerivedFrom,
        }
