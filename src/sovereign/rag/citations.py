"""
src/sovereign/rag/citations.py
Inline citation engine for parsing, validating, and formatting document citations.
Binds retrieved context directly to deliverable lineage sidecars.
Complies with RAG-02 and Phase 1 LineageEngine integration.
"""
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

from sovereign.lineage.models import SourceDocumentCitation
from sovereign.rag.chunker import DocumentChunk


class Citation(BaseModel):
    """
    Structured document citation with spatial and cryptographic provenance.
    """
    model_config = ConfigDict(extra="allow")

    document_id: str = Field(description="Referenced document identifier")
    file_sha256: str = Field(default="", description="Cryptographic SHA-256 of referenced document")
    page_number: Optional[int] = Field(default=None, description="1-indexed page number")
    region_id: Optional[str] = Field(default=None, description="Spatial region identifier")
    excerpt: Optional[str] = Field(default=None, description="Verbatim text snippet supporting claim")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")
    file_name: Optional[str] = Field(default=None, description="Human-readable file name")
    bounding_box: Optional[List[float]] = Field(default=None, description="Normalized coordinates [ymin, xmin, ymax, xmax]")


class CitationEngine:
    """
    Parses bracketed citations, verifies citations against retrieved chunk context,
    formats reference tables, and exports SourceDocumentCitation models for deliverable lineage.
    """

    CITATION_PATTERN = re.compile(r"\[Doc:\s*([^,\]]+),\s*p\.(\d+)(?:#([^\]]+))?\]")

    @classmethod
    def parse_inline_citations(cls, text: str) -> List[Tuple[str, str, int, Optional[str]]]:
        """
        Parses all inline citations from text matching `[Doc: <doc_id>, p.<num>#<reg>]`
        or `[Doc: <doc_id>, p.<num>]`.

        Returns:
            List of (raw_token, document_id, page_number, region_id) tuples.
        """
        matches = cls.CITATION_PATTERN.finditer(text)
        results: List[Tuple[str, str, int, Optional[str]]] = []
        for m in matches:
            raw_token = m.group(0)
            doc_id = m.group(1).strip()
            page_num = int(m.group(2))
            reg_id = m.group(3).strip() if m.group(3) else None
            results.append((raw_token, doc_id, page_num, reg_id))
        return results

    @classmethod
    def validate_citations(
        cls,
        text: str,
        retrieved_chunks: List[DocumentChunk],
    ) -> Dict[str, Any]:
        """
        Validates whether all inline citations parsed from text exist within the
        retrieved document chunks passed into the prompt context.
        Flags any hallucinatory or ungrounded citations.
        """
        parsed = cls.parse_inline_citations(text)
        if not parsed:
            return {
                "valid": True,
                "total_citations": 0,
                "valid_citations": [],
                "hallucinated_citations": [],
                "citation_coverage": 1.0,
            }

        valid_citations: List[Citation] = []
        hallucinated_citations: List[Dict[str, Any]] = []

        for raw_token, doc_id, page_num, reg_id in parsed:
            matched_chunk: Optional[DocumentChunk] = None

            for chunk in retrieved_chunks:
                # Document ID and page number must match
                if chunk.doc_id == doc_id and chunk.page_number == page_num:
                    # If region_id is specified in citation, verify chunk matches or includes region
                    if reg_id is not None:
                        if chunk.region_id == reg_id:
                            matched_chunk = chunk
                            break
                    else:
                        matched_chunk = chunk
                        break

            if matched_chunk:
                citation = Citation(
                    document_id=matched_chunk.doc_id,
                    file_sha256=matched_chunk.file_sha256,
                    page_number=matched_chunk.page_number,
                    region_id=reg_id or matched_chunk.region_id,
                    excerpt=matched_chunk.text_content[:250],
                    confidence=float(matched_chunk.metadata.get("confidence", 1.0)),
                    file_name=matched_chunk.metadata.get("file_name", matched_chunk.doc_id),
                    bounding_box=matched_chunk.metadata.get("box_2d"),
                )
                valid_citations.append(citation)
            else:
                hallucinated_citations.append({
                    "raw_token": raw_token,
                    "document_id": doc_id,
                    "page_number": page_num,
                    "region_id": reg_id,
                    "reason": f"Citation '{raw_token}' not present in retrieved context",
                })

        total = len(parsed)
        valid_count = len(valid_citations)
        coverage = valid_count / total if total > 0 else 1.0

        return {
            "valid": len(hallucinated_citations) == 0,
            "total_citations": total,
            "valid_citations": valid_citations,
            "hallucinated_citations": hallucinated_citations,
            "citation_coverage": round(coverage, 4),
        }

    @classmethod
    def format_reference_table(
        cls,
        citations: List[Citation],
        format_type: str = "markdown",
    ) -> str:
        """
        Formats a structured reference appendix table from valid citations.
        Supports 'markdown' and 'text' formats.
        """
        if not citations:
            return "No citations referenced."

        if format_type.lower() == "markdown":
            lines = [
                "| Citation Tag | Document Name | SHA-256 | Page | Excerpt |",
                "|:---|:---|:---|:---|:---|",
            ]
            for c in citations:
                tag = f"[Doc: {c.document_id}, p.{c.page_number}#{c.region_id}]" if c.region_id else f"[Doc: {c.document_id}, p.{c.page_number}]"
                doc_name = (c.file_name or c.document_id).replace("|", "-")
                sha_display = f"`{c.file_sha256[:12]}...`" if c.file_sha256 else "N/A"
                page_str = f"p.{c.page_number}" if c.page_number else "N/A"
                snippet = (c.excerpt or "").replace("\n", " ").replace("|", "/").strip()
                if len(snippet) > 80:
                    snippet = snippet[:77] + "..."
                lines.append(f"| {tag} | {doc_name} | {sha_display} | {page_str} | {snippet} |")
            return "\n".join(lines)

        elif format_type.lower() in ("text", "plain"):
            lines = ["SOURCE REFERENCES:"]
            for idx, c in enumerate(citations, start=1):
                tag = f"[Doc: {c.document_id}, p.{c.page_number}#{c.region_id}]" if c.region_id else f"[Doc: {c.document_id}, p.{c.page_number}]"
                doc_name = c.file_name or c.document_id
                sha = c.file_sha256[:12] if c.file_sha256 else "N/A"
                snippet = (c.excerpt or "").replace("\n", " ").strip()
                lines.append(f"[{idx}] {tag} - {doc_name} (SHA: {sha}) Page {c.page_number}: \"{snippet}\"")
            return "\n".join(lines)

        else:
            raise ValueError(f"Unsupported format_type '{format_type}'. Use 'markdown' or 'text'.")

    @classmethod
    def to_lineage_citations(cls, citations: List[Citation]) -> List[SourceDocumentCitation]:
        """
        Converts internal Citation models to Phase 1 SourceDocumentCitation objects
        for cryptographic deliverable lineage sidecars.
        """
        lineage_list: List[SourceDocumentCitation] = []
        for c in citations:
            lineage_list.append(
                SourceDocumentCitation(
                    document_id=c.document_id,
                    file_name=c.file_name or c.document_id,
                    file_sha256=c.file_sha256,
                    page_number=c.page_number,
                    bounding_box=c.bounding_box,
                    snippet=c.excerpt,
                )
            )
        return lineage_list
