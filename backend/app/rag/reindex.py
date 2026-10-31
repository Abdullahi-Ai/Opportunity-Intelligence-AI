import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from app.config import settings
from app.rag.document_loader import load_and_chunk_all_opportunities
from app.rag.vector_store import vector_store
from app.rag.embeddings import embedding_function

logger = logging.getLogger(__name__)

def backup_chroma_db(destination_dir: Optional[str] = None) -> str:
    source_path = Path(settings.CHROMA_PERSIST_DIRECTORY)
    if not source_path.exists():
        raise FileNotFoundError(f"Chroma persist directory not found: {source_path}")

    if not destination_dir:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_parent = source_path.parent / "backups"
        backup_parent.mkdir(parents=True, exist_ok=True)
        dest_path = backup_parent / f"chroma_backup_{timestamp}"
    else:
        dest_path = Path(destination_dir)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

    if dest_path.exists():
        shutil.rmtree(dest_path)

    shutil.copytree(source_path, dest_path)
    logger.info(f"ChromaDB backup created successfully at: {dest_path}")
    return str(dest_path)

def reindex_all_opportunities(force_clear: bool = False, skip_if_populated: bool = True) -> Dict[str, Any]:
    stats = vector_store.get_stats()
    if skip_if_populated and not force_clear and stats.get("total_chunks", 0) > 0:
        return {
            "status": "skipped",
            "message": "Vector store already populated with persistent records",
            "chunks_indexed": 0,
            "total_chunks_in_store": stats["total_chunks"],
            "collection_name": stats["collection_name"],
            "persist_directory": stats["persist_directory"],
            "timestamp": datetime.utcnow().isoformat()
        }

    raw_dir = Path(settings.RAW_DATA_DIRECTORY)
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw opportunities directory not found: {raw_dir}")

    chunks = load_and_chunk_all_opportunities(str(raw_dir))
    if not chunks:
        raise ValueError(f"No opportunity chunks generated from: {raw_dir}")

    test_embed = embedding_function(["Verification test chunk"])
    expected_dim = len(test_embed[0]) if test_embed else 384

    if force_clear:
        vector_store.clear()

    total_upserted = vector_store.upsert_chunks(chunks)
    new_stats = vector_store.get_stats()

    return {
        "status": "success",
        "chunks_indexed": total_upserted,
        "total_chunks_in_store": new_stats["total_chunks"],
        "embedding_dimensions": expected_dim,
        "collection_name": new_stats["collection_name"],
        "persist_directory": new_stats["persist_directory"],
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    result = reindex_all_opportunities(force_clear=False, skip_if_populated=True)
    print(result)
