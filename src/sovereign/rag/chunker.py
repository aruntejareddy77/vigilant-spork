"""
src/sovereign/rag/chunker.py
Local offline document chunking preserving physical page numbers and spatial region IDs.
Complies with RAG-01 and MMOD-04.
"""
import hashlib
import re
from typing import Any, Callable, Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field, field_validator

from sovereign.multimodal.models import NormalizedDocument


VALID_CLASSIFICATIONS: Set[str] = {"PUBLIC", "INTERNAL", "RESTRICTED", "SECRET"}


class DocumentChunk(BaseModel):
    """
    Atomic text chunk with classification, RBAC roles, and provenance coordinates.
    """
    model_config = ConfigDict(extra="allow")

    chunk_id: str = Field(description="Unique identifier for chunk, e.g. doc-sha-p1-r001 or doc-sha-c0001")
    doc_id: str = Field(description="Parent document identifier, e.g. doc-3f8a91b2")
    file_sha256: str = Field(description="Cryptographic SHA-256 hash of parent document")
    page_number: int = Field(default=1, ge=1, description="1-indexed physical page number")
    region_id: Optional[str] = Field(default=None, description="Spatial region identifier if extracted from NormalizedDocument")
    text_content: str = Field(description="Chunk textual payload")
    classification: str = Field(default="INTERNAL", description="Classification level: PUBLIC, INTERNAL, RESTRICTED, SECRET")
    allowed_roles: List[str] = Field(default_factory=lambda: ["admin", "engineer"], description="RBAC roles permitted to retrieve this chunk")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary provenance or spatial attributes")

    @field_validator("classification")
    @classmethod
    def validate_classification(cls, v: str) -> str:
        v_upper = v.strip().upper()
        if v_upper not in VALID_CLASSIFICATIONS:
            raise ValueError(f"Invalid classification '{v}'. Must be one of {sorted(VALID_CLASSIFICATIONS)}")
        return v_upper

    @field_validator("allowed_roles")
    @classmethod
    def normalize_roles(cls, v: List[str]) -> List[str]:
        return [r.strip().lower() for r in v if r.strip()]


class DocumentChunker:
    """
    Splits plain text, markdown, and NormalizedDocument representations into chunks
    while preserving page numbers, spatial region IDs, and metadata boundaries.
    """

    def __init__(
        self,
        chunk_size: int = 2000,
        chunk_overlap: int = 200,
        length_function: Callable[[str], int] = len,
    ):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.length_function = length_function
        self.separators = ["\n\n", "\n", ". ", " ", ""]

    def _split_text_recursive(self, text: str, separators: List[str]) -> List[str]:
        """Recursively splits text on hierarchical separators until chunks fit within chunk_size."""
        final_chunks: List[str] = []
        separator = separators[-1]
        new_separators: List[str] = []

        for i, sep in enumerate(separators):
            if sep == "":
                separator = ""
                break
            if sep in text:
                separator = sep
                new_separators = separators[i + 1:]
                break

        splits = text.split(separator) if separator != "" else list(text)

        good_splits: List[str] = []
        for s in splits:
            if self.length_function(s) < self.chunk_size:
                good_splits.append(s)
            else:
                if good_splits:
                    merged = self._merge_splits(good_splits, separator)
                    final_chunks.extend(merged)
                    good_splits = []
                if not new_separators:
                    final_chunks.append(s)
                else:
                    other_chunks = self._split_text_recursive(s, new_separators)
                    final_chunks.extend(other_chunks)

        if good_splits:
            merged = self._merge_splits(good_splits, separator)
            final_chunks.extend(merged)

        return final_chunks

    def _merge_splits(self, splits: List[str], separator: str) -> List[str]:
        """Merges smaller splits up to chunk_size with chunk_overlap."""
        docs: List[str] = []
        current_doc: List[str] = []
        total = 0

        for split in splits:
            len_split = self.length_function(split)
            sep_len = self.length_function(separator) if current_doc else 0

            if total + len_split + sep_len > self.chunk_size:
                if current_doc:
                    doc = separator.join(current_doc)
                    if doc.strip():
                        docs.append(doc)
                    # Backtrack for overlap
                    while current_doc and total > self.chunk_overlap:
                        popped = current_doc.pop(0)
                        total -= self.length_function(popped)
                        if current_doc:
                            total -= self.length_function(separator)
                current_doc.append(split)
                total += len_split
            else:
                current_doc.append(split)
                total += len_split + sep_len

        if current_doc:
            doc = separator.join(current_doc)
            if doc.strip():
                docs.append(doc)

        return docs

    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        doc_id: Optional[str] = None,
        file_sha256: Optional[str] = None,
        classification: str = "INTERNAL",
        allowed_roles: Optional[List[str]] = None,
        page_number: int = 1,
    ) -> List[DocumentChunk]:
        """
        Splits plain text or markdown string into DocumentChunks.
        """
        clean_text = text.strip()
        if not clean_text:
            return []

        meta = dict(metadata or {})
        effective_sha = file_sha256 or meta.get("file_sha256") or hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
        effective_doc_id = doc_id or meta.get("doc_id") or f"doc-{effective_sha[:12]}"
        effective_roles = allowed_roles or meta.get("allowed_roles") or ["admin", "engineer"]
        effective_cls = classification or meta.get("classification") or "INTERNAL"

        raw_chunks = self._split_text_recursive(clean_text, self.separators)
        chunks: List[DocumentChunk] = []

        for idx, chunk_str in enumerate(raw_chunks, start=1):
            c_text = chunk_str.strip()
            if not c_text:
                continue
            chunk_id = f"{effective_doc_id}-p{page_number}-c{idx:04d}" if page_number > 1 else f"{effective_doc_id}-c{idx:04d}"
            chunk = DocumentChunk(
                chunk_id=chunk_id,
                doc_id=effective_doc_id,
                file_sha256=effective_sha,
                page_number=page_number,
                region_id=meta.get("region_id"),
                text_content=c_text,
                classification=effective_cls,
                allowed_roles=effective_roles,
                metadata=meta,
            )
            chunks.append(chunk)

        return chunks

    def chunk_normalized_document(
        self,
        doc: NormalizedDocument,
        classification: str = "INTERNAL",
        allowed_roles: Optional[List[str]] = None,
    ) -> List[DocumentChunk]:
        """
        Splits a NormalizedDocument into chunks, strictly preserving page_number and region_id provenance.
        """
        effective_roles = allowed_roles if allowed_roles is not None else ["admin", "engineer"]
        chunks: List[DocumentChunk] = []

        for page in doc.pages:
            page_num = page.page_number

            # If page has extracted regions, chunk each region preserving its region_id
            for region in page.regions:
                reg_text = region.text.strip()
                if not reg_text:
                    continue

                reg_meta = {
                    "box_2d": region.box_2d,
                    "confidence": region.confidence,
                    "modality": region.modality.value if hasattr(region.modality, "value") else str(region.modality),
                    "file_name": doc.file_name,
                }

                if self.length_function(reg_text) <= self.chunk_size:
                    chunk = DocumentChunk(
                        chunk_id=f"{doc.doc_id}-p{page_num}-{region.region_id}",
                        doc_id=doc.doc_id,
                        file_sha256=doc.file_sha256,
                        page_number=page_num,
                        region_id=region.region_id,
                        text_content=reg_text,
                        classification=classification,
                        allowed_roles=effective_roles,
                        metadata=reg_meta,
                    )
                    chunks.append(chunk)
                else:
                    # Region exceeds chunk_size: sub-chunk while keeping region_id & page_number
                    sub_pieces = self._split_text_recursive(reg_text, self.separators)
                    for s_idx, piece in enumerate(sub_pieces, start=1):
                        piece_clean = piece.strip()
                        if not piece_clean:
                            continue
                        chunk = DocumentChunk(
                            chunk_id=f"{doc.doc_id}-p{page_num}-{region.region_id}-c{s_idx:03d}",
                            doc_id=doc.doc_id,
                            file_sha256=doc.file_sha256,
                            page_number=page_num,
                            region_id=region.region_id,
                            text_content=piece_clean,
                            classification=classification,
                            allowed_roles=effective_roles,
                            metadata=reg_meta,
                        )
                        chunks.append(chunk)

            # If page has no regions but has form fields or tables, capture them as fallback
            if not page.regions:
                fallback_parts: List[str] = []
                if page.form_fields:
                    fallback_parts.append("\n".join(f"{f.key}: {f.value}" for f in page.form_fields))
                if page.tables:
                    for t in page.tables:
                        if t.headers:
                            fallback_parts.append(" | ".join(t.headers))
                        for row in t.rows:
                            fallback_parts.append(" | ".join(row))

                if fallback_parts:
                    combined_text = "\n\n".join(fallback_parts)
                    fallback_chunks = self.chunk_text(
                        combined_text,
                        metadata={"file_name": doc.file_name, "page_fallback": True},
                        doc_id=doc.doc_id,
                        file_sha256=doc.file_sha256,
                        classification=classification,
                        allowed_roles=effective_roles,
                        page_number=page_num,
                    )
                    chunks.extend(fallback_chunks)

        return chunks
