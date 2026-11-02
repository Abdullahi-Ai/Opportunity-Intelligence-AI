"""RAG Knowledge Ingestion and Vector Retrieval Module."""

from app.db.session import engine


def get_vector_store():
    """
    Returns the appropriate vector store backend based on the configured database dialect.
    When PostgreSQL is configured (e.g. Neon in production), returns pgvector_store.
    Otherwise, returns local ChromaDB vector_store (if available) or pgvector_store fallback.
    """
    if engine.dialect.name == "postgresql":
        from app.rag.pgvector_store import pgvector_store
        return pgvector_store

    try:
        from app.rag.vector_store import vector_store
        if vector_store is not None:
            return vector_store
    except Exception:
        pass

    from app.rag.pgvector_store import pgvector_store
    return pgvector_store
