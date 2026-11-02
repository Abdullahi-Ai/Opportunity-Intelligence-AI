import json
import pytest
from pathlib import Path

from app.rag.vector_store import vector_store
from app.rag.pgvector_store import pgvector_store, PgVectorStore
from app.rag.document_loader import OpportunityChunk

@pytest.fixture(scope="module")
def populated_pgvector():
    export_path = Path("backend/data/backup_chromadb_export.json")
    assert export_path.exists(), "Backup JSON export not found."
    with open(export_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    pgvector_store.upsert_raw_records(data["chunks"])
    return pgvector_store

def test_pgvector_record_count(populated_pgvector):
    stats = populated_pgvector.get_stats()
    assert stats["total_chunks"] == 57
    assert stats["embedding_dimensions"] == 384

def test_pgvector_duplicate_handling_idempotency(populated_pgvector):
    initial_count = populated_pgvector.get_stats()["total_chunks"]
    export_path = Path("backend/data/backup_chromadb_export.json")
    with open(export_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Re-upsert the first 5 records
    re_upserted = populated_pgvector.upsert_raw_records(data["chunks"][:5])
    assert re_upserted == 5

    # Count must remain exactly the same
    after_count = populated_pgvector.get_stats()["total_chunks"]
    assert after_count == initial_count

def test_pgvector_metadata_filtering(populated_pgvector):
    results = populated_pgvector.search(query="financial support grant", top_k=5, category="Scholarship")
    assert len(results) > 0
    for hit in results:
        assert hit["metadata"].get("category") == "Scholarship"

def test_pgvector_status_filtering(populated_pgvector):
    results = populated_pgvector.search(query="technology attachment", top_k=5, status="open")
    assert len(results) > 0
    for hit in results:
        assert hit["metadata"].get("status") == "open"

def test_pgvector_source_attribution(populated_pgvector):
    results = populated_pgvector.search(query="Safaricom industrial attachment eligibility", top_k=3)
    assert len(results) > 0
    top = results[0]
    assert top["metadata"].get("official_url") == "https://www.safaricom.co.ke/careers"
    assert top["metadata"].get("opportunity_id") == "opp-safaricom-attachment-2026"
    assert top["similarity_score"] > 0.4

def test_side_by_side_retrieval_parity_with_chroma(populated_pgvector):
    test_queries = [
        "What are the eligibility requirements for Chevening scholarship?",
        "HEF undergraduate scholarship and HELB loan application",
        "KRA internship programme requirements and duration",
        "Mastercard Foundation scholars program at USIU Africa",
        "Presidential Digital Talent Programme PDTP entry criteria"
    ]

    for query in test_queries:
        chroma_res = vector_store.search(query=query, top_k=3)
        pg_res = populated_pgvector.search(query=query, top_k=3)

        assert len(chroma_res) == len(pg_res)

        chroma_top_id = chroma_res[0]["metadata"].get("opportunity_id")
        pg_top_id = pg_res[0]["metadata"].get("opportunity_id")

        assert chroma_top_id == pg_top_id, f"Top match mismatch for query '{query}': Chroma={chroma_top_id}, PgVector={pg_top_id}"

        # Compare similarity scores (should be close within rounding precision)
        diff = abs(chroma_res[0]["similarity_score"] - pg_res[0]["similarity_score"])
        assert diff < 0.05, f"Score difference {diff} too high for query '{query}'"
