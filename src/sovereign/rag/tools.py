"""
src/sovereign/rag/tools.py
Tool definitions and execution handlers for local vector search and RAG knowledge retrieval.
Complies with RAG-01, RAG-03, and ToolRegistry RBAC dispatch.
"""
from typing import Any, Dict, List, Optional, Union

from sovereign.models.adapter import BaseModelAdapter
from sovereign.rag.vector_store import SQLiteVectorStore
from sovereign.tools.registry import ToolRegistry
from sovereign.tools.schemas import ToolDefinition, UserRole


RAG_SEARCH_TOOL = ToolDefinition(
    name="rag_search",
    description=(
        "Search the local engineering knowledge base and technical documents using semantic "
        "similarity with strict SQL-level RBAC pre-filtering."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language query or keywords describing required engineering information",
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of candidate chunks to retrieve",
                "default": 5,
                "minimum": 1,
                "maximum": 50,
            },
            "classification_filter": {
                "type": "string",
                "description": "Optional sensitivity level filter: PUBLIC, INTERNAL, RESTRICTED, SECRET",
            },
        },
        "required": ["query"],
    },
    required_role=UserRole.ENGINEER,
)


def execute_rag_search(
    query: str,
    vector_store: SQLiteVectorStore,
    model_adapter: BaseModelAdapter,
    top_k: int = 5,
    classification_filter: Optional[str] = None,
    user_role: Union[UserRole, str] = UserRole.ENGINEER,
) -> Dict[str, Any]:
    """
    Executes semantic RAG retrieval: embeds query, pre-filters candidates by caller role in SQL,
    ranks by cosine similarity, and formats results with inline citation tokens.
    """
    clean_query = query.strip()
    if not clean_query:
        return {
            "query": query,
            "total_retrieved": 0,
            "user_role": user_role.value if isinstance(user_role, UserRole) else str(user_role),
            "results": [],
        }

    # Embed query vector using local model adapter
    embeddings = model_adapter.embed([clean_query])
    if not embeddings or not embeddings[0]:
        raise RuntimeError("Failed to compute embedding vector for search query")
    query_vector = embeddings[0]

    # Execute RBAC pre-filtered vector search
    search_matches = vector_store.search(
        query_vector=query_vector,
        top_k=top_k,
        user_role=user_role,
        classification_filter=classification_filter,
    )

    formatted_results: List[Dict[str, Any]] = []
    for chunk, sim in search_matches:
        citation_token = (
            f"[Doc: {chunk.doc_id}, p.{chunk.page_number}#{chunk.region_id}]"
            if chunk.region_id
            else f"[Doc: {chunk.doc_id}, p.{chunk.page_number}]"
        )
        formatted_results.append({
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "file_sha256": chunk.file_sha256,
            "page_number": chunk.page_number,
            "region_id": chunk.region_id,
            "citation_token": citation_token,
            "text": chunk.text_content,
            "classification": chunk.classification,
            "similarity_score": round(sim, 4),
            "metadata": chunk.metadata,
        })

    return {
        "query": clean_query,
        "total_retrieved": len(formatted_results),
        "user_role": user_role.value if isinstance(user_role, UserRole) else str(user_role),
        "results": formatted_results,
    }


def register_rag_tools(
    registry: ToolRegistry,
    vector_store: SQLiteVectorStore,
    model_adapter: BaseModelAdapter,
    default_role: UserRole = UserRole.ENGINEER,
) -> ToolRegistry:
    """
    Registers rag_search tool into ToolRegistry.
    """
    registry.register_tool(
        RAG_SEARCH_TOOL,
        lambda query, top_k=5, classification_filter=None: execute_rag_search(
            query=query,
            vector_store=vector_store,
            model_adapter=model_adapter,
            top_k=top_k,
            classification_filter=classification_filter,
            user_role=default_role,
        ),
    )
    return registry
