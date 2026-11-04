"""
Opportunity Intelligence AI - RAG Ingestion Pipeline.
Loads markdown documents, chunks them by section, and indexes them into ChromaDB.
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any

from app.config import settings
from app.db.session import SessionLocal, Base, engine
from app.models.entities import Opportunity, VerificationStatus
from app.rag.document_loader import parse_markdown_with_frontmatter, chunk_opportunity_document
from app.rag.vector_store import vector_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def sync_relational_opportunities(raw_path: Path) -> int:
    """Synchronizes structured master opportunity records in the relational database."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    count = 0
    try:
        for file_path in sorted(raw_path.glob("*.md")):
            doc = parse_markdown_with_frontmatter(file_path)
            existing = db.query(Opportunity).filter(Opportunity.id == doc.id).first()
            if not existing:
                opp = Opportunity(
                    id=doc.id,
                    title=doc.title,
                    provider=doc.provider,
                    category=doc.category,
                    target_audience=doc.target_audience,
                    fields_of_study=", ".join(doc.field_of_study),
                    degree_levels=", ".join(doc.degree_level),
                    official_url=doc.official_url,
                    application_deadline=doc.application_deadline,
                    status=doc.status,
                    # Safe defaults: Imported metadata cannot self-certify as VERIFIED
                    is_verified=False,
                    verification_status=VerificationStatus.PENDING_REVIEW.value,
                    verification_date=None,
                    source_notes=doc.source_notes
                )
                db.add(opp)
            else:
                existing.title = doc.title
                existing.provider = doc.provider
                existing.category = doc.category
                existing.target_audience = doc.target_audience
                existing.fields_of_study = ", ".join(doc.field_of_study)
                existing.degree_levels = ", ".join(doc.degree_level)
                existing.application_deadline = doc.application_deadline
                existing.status = doc.status

                # CRIT-03: Protect administrator decisions and audited evidence from re-ingestion clobbering.
                # Decisions in VERIFIED, NEEDS_REVIEW, or REJECTED statuses are authoritative and immutable
                # to automated re-ingestion, preserving administrator notes and corrected URLs.
                audited_statuses = {
                    VerificationStatus.VERIFIED.value,
                    VerificationStatus.NEEDS_REVIEW.value,
                    VerificationStatus.REJECTED.value,
                }
                curr_status = getattr(existing, "verification_status", None)

                if curr_status not in audited_statuses:
                    existing.is_verified = False
                    existing.verification_status = VerificationStatus.PENDING_REVIEW.value
                    existing.verification_date = None
                    existing.official_url = doc.official_url
                    existing.source_notes = doc.source_notes
            count += 1
        db.commit()
    finally:
        db.close()
    return count

def run_ingestion(raw_dir: str = settings.RAW_DATA_DIRECTORY) -> Dict[str, Any]:
    """
    Executes the end-to-end ingestion pipeline:
    1. Synchronizes structured master records into the relational database.
    2. Chunks documents semantically by section.
    3. Generates vector embeddings and upserts into ChromaDB.
    4. Reports indexing statistics.
    """
    raw_path = Path(raw_dir)
    logger.info(f"Starting ingestion from directory: {raw_path}")
    
    if not raw_path.exists():
        logger.warning(f"Raw opportunities directory {raw_path} does not exist.")
        return {"status": "error", "message": f"Directory {raw_path} not found"}

    relational_synced = sync_relational_opportunities(raw_path)
    logger.info(f"Synchronized {relational_synced} master records into relational database.")

    all_chunks = []
    for file_path in sorted(raw_path.glob("*.md")):
        doc = parse_markdown_with_frontmatter(file_path)
        chunks = chunk_opportunity_document(doc)
        all_chunks.extend(chunks)

    logger.info(f"Parsed {len(all_chunks)} semantic chunks from raw documents.")

    if not all_chunks:
        logger.warning("No chunks found to ingest.")
        return {"status": "empty", "total_chunks": 0}

    upserted_count = vector_store.upsert_chunks(all_chunks)
    logger.info(f"Successfully upserted {upserted_count} chunks into ChromaDB.")

    stats = vector_store.get_stats()
    logger.info(f"Vector Store Status: {stats}")

    return {
        "status": "success",
        "relational_records_synced": relational_synced,
        "chunks_indexed": upserted_count,
        "total_collection_chunks": stats["total_chunks"],
        "collection_name": stats["collection_name"]
    }

if __name__ == "__main__":
    result = run_ingestion()
    print(f"Ingestion result: {result}")
