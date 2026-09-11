"""
src/sovereign/rag/vector_store.py
Zero-dependency embedded vector database backed by SQLite in WAL mode.
Stores float embeddings as packed binary IEEE-754 blobs and strictly enforces
SQL-level RBAC pre-filtering before candidate evaluation.
Complies with RAG-01, RAG-03, and ASVS V1.4 / Threat T-04-01.
"""
import json
import math
from pathlib import Path
import sqlite3
import struct
from typing import Any, Dict, List, Optional, Tuple, Union

from sovereign.rag.chunker import DocumentChunk
from sovereign.tools.schemas import UserRole

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class SQLiteVectorStore:
    """
    Embedded SQLite vector store operating in Write-Ahead Log (WAL) mode.
    Stores dense vector embeddings as binary float blobs. Enforces dynamic
    SQL-level RBAC pre-filtering to eliminate unauthorized vector retrieval.
    """

    def __init__(self, db_path: Union[str, Path] = "sovereign_knowledge.sqlite"):
        self.db_path = str(db_path)
        self._force_pure_python = False
        self._init_db()

    def _init_db(self) -> None:
        """Initialize table schema and indexes with WAL mode enabled."""
        if self.db_path != ":memory:":
            path_obj = Path(self.db_path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # Enable WAL mode for concurrent reads/writes and performance
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    file_sha256 TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    region_id TEXT,
                    text_content TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    allowed_roles_json TEXT NOT NULL,
                    metadata_json TEXT,
                    embedding BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_classification ON chunks(classification);")

    def insert_chunk(self, chunk: DocumentChunk, embedding: List[float]) -> None:
        """
        Store a single document chunk and its dense embedding blob.
        """
        if not embedding:
            raise ValueError("Embedding vector cannot be empty")

        blob = struct.pack(f"{len(embedding)}f", *embedding)
        roles_json = json.dumps(chunk.allowed_roles)
        meta_json = json.dumps(chunk.metadata)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO chunks (
                    chunk_id, doc_id, file_sha256, page_number, region_id,
                    text_content, classification, allowed_roles_json, metadata_json, embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    chunk.doc_id,
                    chunk.file_sha256,
                    chunk.page_number,
                    chunk.region_id,
                    chunk.text_content,
                    chunk.classification.upper(),
                    roles_json,
                    meta_json,
                    blob,
                ),
            )

    def batch_insert(self, items: List[Tuple[DocumentChunk, List[float]]]) -> None:
        """
        Atomically insert a batch of (DocumentChunk, embedding) tuples.
        """
        if not items:
            return

        records = []
        for chunk, embedding in items:
            if not embedding:
                raise ValueError(f"Empty embedding for chunk {chunk.chunk_id}")
            blob = struct.pack(f"{len(embedding)}f", *embedding)
            roles_json = json.dumps(chunk.allowed_roles)
            meta_json = json.dumps(chunk.metadata)
            records.append((
                chunk.chunk_id,
                chunk.doc_id,
                chunk.file_sha256,
                chunk.page_number,
                chunk.region_id,
                chunk.text_content,
                chunk.classification.upper(),
                roles_json,
                meta_json,
                blob,
            ))

        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO chunks (
                    chunk_id, doc_id, file_sha256, page_number, region_id,
                    text_content, classification, allowed_roles_json, metadata_json, embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                records,
            )

    def get_chunk(self, chunk_id: str) -> Optional[DocumentChunk]:
        """Look up a chunk by its unique chunk_id."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT chunk_id, doc_id, file_sha256, page_number, region_id,
                       text_content, classification, allowed_roles_json, metadata_json
                FROM chunks WHERE chunk_id = ?
                """,
                (chunk_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            c_id, d_id, sha, p_num, r_id, txt, cls_str, roles_j, meta_j = row
            roles = json.loads(roles_j) if roles_j else ["admin", "engineer"]
            meta = json.loads(meta_j) if meta_j else {}
            return DocumentChunk(
                chunk_id=c_id,
                doc_id=d_id,
                file_sha256=sha,
                page_number=p_num,
                region_id=r_id,
                text_content=txt,
                classification=cls_str,
                allowed_roles=roles,
                metadata=meta,
            )

    def count_chunks(self) -> int:
        """Returns total number of chunks stored."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM chunks")
            return cursor.fetchone()[0]

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        user_role: Union[UserRole, str] = UserRole.ENGINEER,
        classification_filter: Optional[str] = None,
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Executes semantic vector similarity search with strict SQL-level RBAC pre-filtering.

        Pre-filtering rules:
        - ADMIN: Full visibility across all classifications (PUBLIC, INTERNAL, RESTRICTED, SECRET).
        - ENGINEER: Clearance strictly for PUBLIC and INTERNAL. Never retrieves RESTRICTED or SECRET.
                    Allowed if classification is PUBLIC, or role list contains 'engineer' or 'admin'.
        - AUDITOR: Strict read-only clearance. Chunks must be classification='PUBLIC' or
                   have 'auditor' explicitly present in allowed_roles.
        - Zero unauthorized vectors are loaded into memory, evaluated, or ranked.
        """
        if not query_vector:
            return []
        dim = len(query_vector)

        # Normalize user role
        if isinstance(user_role, str):
            try:
                role_enum = UserRole(user_role.strip().lower())
            except ValueError:
                role_enum = UserRole.AUDITOR
        else:
            role_enum = user_role

        # Construct SQL Pre-Filtering WHERE clause
        where_conditions: List[str] = []
        sql_params: List[Any] = []

        if role_enum == UserRole.ADMIN:
            # Full visibility across all sensitivity tiers
            pass
        elif role_enum == UserRole.ENGINEER:
            # Engineer clearance: strictly PUBLIC or INTERNAL; never RESTRICTED or SECRET.
            # Within allowed classification, either PUBLIC or allowed_roles includes engineer/admin.
            where_conditions.append(
                """(
                    classification = 'PUBLIC'
                    OR (
                        classification = 'INTERNAL'
                        AND (
                            allowed_roles_json IS NULL
                            OR EXISTS (
                                SELECT 1 FROM json_each(chunks.allowed_roles_json)
                                WHERE json_each.value IN ('engineer', 'admin')
                            )
                        )
                    )
                )"""
            )
        elif role_enum == UserRole.AUDITOR:
            # Auditor clearance: strictly audit-cleared or public documents
            where_conditions.append(
                """(
                    classification = 'PUBLIC'
                    OR EXISTS (
                        SELECT 1 FROM json_each(chunks.allowed_roles_json)
                        WHERE json_each.value = 'auditor'
                    )
                )"""
            )
        else:
            # Default deny for unrecognised roles
            where_conditions.append("1 = 0")

        # Optional caller classification filter
        if classification_filter:
            where_conditions.append("classification = ?")
            sql_params.append(classification_filter.strip().upper())

        where_sql = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        query_sql = f"""
            SELECT chunk_id, doc_id, file_sha256, page_number, region_id,
                   text_content, classification, allowed_roles_json, metadata_json, embedding
            FROM chunks
            {where_sql}
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query_sql, sql_params)
            rows = cursor.fetchall()

        if not rows:
            return []

        # Parse chunks and calculate cosine similarity
        results: List[Tuple[DocumentChunk, float]] = []

        if HAS_NUMPY and not self._force_pure_python:
            # Accelerated NumPy vectorized similarity
            blobs = [r[9] for r in rows]
            raw_bytes = b"".join(blobs)
            cand_mat = np.frombuffer(raw_bytes, dtype=np.float32).reshape(len(rows), dim)

            q = np.array(query_vector, dtype=np.float32)
            q_norm = float(np.linalg.norm(q))
            if q_norm > 1e-12:
                q = q / q_norm

            cand_norms = np.linalg.norm(cand_mat, axis=1)
            cand_norms[cand_norms == 0] = 1.0
            cand_mat_norm = cand_mat / cand_norms[:, np.newaxis]

            sims = np.dot(cand_mat_norm, q)

            for idx, row in enumerate(rows):
                c_id, d_id, sha, p_num, r_id, txt, cls_str, roles_j, meta_j, _ = row
                chunk = DocumentChunk(
                    chunk_id=c_id,
                    doc_id=d_id,
                    file_sha256=sha,
                    page_number=p_num,
                    region_id=r_id,
                    text_content=txt,
                    classification=cls_str,
                    allowed_roles=json.loads(roles_j) if roles_j else ["admin", "engineer"],
                    metadata=json.loads(meta_j) if meta_j else {},
                )
                results.append((chunk, float(sims[idx])))
        else:
            # Pure Python fallback dot product over normalized hypersphere
            q_sq = sum(x * x for x in query_vector)
            q_norm = math.sqrt(q_sq) if q_sq > 1e-12 else 1.0

            for row in rows:
                c_id, d_id, sha, p_num, r_id, txt, cls_str, roles_j, meta_j, blob = row
                vec = struct.unpack(f"{dim}f", blob)

                dot = 0.0
                v_sq = 0.0
                for a, b in zip(query_vector, vec):
                    dot += a * b
                    v_sq += b * b

                v_norm = math.sqrt(v_sq) if v_sq > 1e-12 else 1.0
                sim = dot / (q_norm * v_norm)

                chunk = DocumentChunk(
                    chunk_id=c_id,
                    doc_id=d_id,
                    file_sha256=sha,
                    page_number=p_num,
                    region_id=r_id,
                    text_content=txt,
                    classification=cls_str,
                    allowed_roles=json.loads(roles_j) if roles_j else ["admin", "engineer"],
                    metadata=json.loads(meta_j) if meta_j else {},
                )
                results.append((chunk, float(sim)))

        # Sort strictly descending by similarity
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
