"""
Opportunity Intelligence AI - RAG Ingestion Pipeline.
Loads markdown documents, chunks them by section, and indexes them into ChromaDB.
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any

from app.config import settings
from app.rag.document_loader import load_all_opportunities
from app.rag.vector_store import vector_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def run_ingestion(raw_dir: str = settings.RAW_DATA_DIRECTORY) -> Dict[str, Any]:
    """
    Executes the end-to-end ingestion pipeline:
    1. Reads markdown documents from raw_opportunities.
    2. Parses frontmatter and extracts semantic section chunks.
    3. Upserts chunks into ChromaDB with embeddings.
    4. Reports indexing statistics.
    """
    raw_path = Path(raw_dir)
    logger.info(f"Starting ingestion from directory: {raw_path}")
    
    if not raw_path.exists():
        logger.warning(f"Raw opportunities directory {raw_path} does not exist.")
        return {"status": "error", "message": f"Directory {raw_path} not found"}

    chunks = load_all_opportunities(raw_path)
    logger.info(f"Parsed {len(chunks)} semantic chunks from raw documents.")

    if not chunks:
        logger.warning("No chunks found to ingest.")
        return {"status": "empty", "total_chunks": 0}

    upserted_count = vector_store.upsert_chunks(chunks)
    logger.info(f"Successfully upserted {upserted_count} chunks into ChromaDB.")

    stats = vector_store.get_stats()
    logger.info(f"Vector Store Status: {stats}")

    return {
        "status": "success",
        "chunks_indexed": upserted_count,
        "total_collection_chunks": stats["total_chunks"],
        "collection_name": stats["collection_name"]
    }

if __name__ == "__main__":
    result = run_ingestion()
    print(f"Ingestion result: {result}")
