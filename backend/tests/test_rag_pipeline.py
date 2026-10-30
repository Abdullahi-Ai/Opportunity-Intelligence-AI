import pytest
from pathlib import Path
from app.rag.ingest import run_ingestion
from app.rag.vector_store import vector_store

@pytest.fixture(scope="module")
def setup_vector_store():
    """Initializes vector store and runs ingestion before RAG tests."""
    result = run_ingestion()
    assert result["status"] == "success"
    assert result["chunks_indexed"] > 0
    return vector_store

def test_vector_store_ingestion(setup_vector_store):
    store = setup_vector_store
    stats = store.get_stats()
    assert stats["total_chunks"] > 0
    assert stats["collection_name"] == "kenya_opportunities"

def test_semantic_retrieval_safaricom(setup_vector_store):
    store = setup_vector_store
    query = "What are the required documents and GPA for Safaricom industrial attachment?"
    results = store.search(query=query, top_k=3)

    assert len(results) > 0
    top_hit = results[0]
    assert "safaricom" in top_hit["content"].lower()
    assert top_hit["similarity_score"] > 0.4
    assert top_hit["metadata"]["official_url"] == "https://www.safaricom.co.ke/careers"
    assert top_hit["metadata"]["opportunity_id"] == "opp-safaricom-attachment-2026"

def test_semantic_retrieval_hef_scholarship(setup_vector_store):
    store = setup_vector_store
    query = "How to apply for HEF government scholarship and HELB loan using KRA PIN?"
    results = store.search(query=query, top_k=3)

    assert len(results) > 0
    top_hit = results[0]
    assert "hef" in top_hit["content"].lower() or "helb" in top_hit["content"].lower()
    assert top_hit["metadata"]["official_url"] == "https://www.hef.co.ke"

def test_metadata_filtering_category(setup_vector_store):
    store = setup_vector_store
    query = "opportunities for students"
    results = store.search(query=query, top_k=5, category="Scholarship")

    assert len(results) > 0
    for hit in results:
        assert hit["metadata"]["category"] == "Scholarship"
