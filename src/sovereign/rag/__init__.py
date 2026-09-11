"""
src/sovereign/rag/__init__.py
Package initialization for Sovereign RAG, Vector Store, and Citation engines.
"""
from sovereign.rag.chunker import DocumentChunk, DocumentChunker
from sovereign.rag.vector_store import SQLiteVectorStore
from sovereign.rag.citations import Citation, CitationEngine
from sovereign.rag.tools import RAG_SEARCH_TOOL, execute_rag_search, register_rag_tools

__all__ = [
    "DocumentChunk",
    "DocumentChunker",
    "SQLiteVectorStore",
    "Citation",
    "CitationEngine",
    "RAG_SEARCH_TOOL",
    "execute_rag_search",
    "register_rag_tools",
]
