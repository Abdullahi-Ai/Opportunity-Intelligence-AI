import json
import pytest
from pathlib import Path
from app.rag.ingest import run_ingestion
from app.rag.vector_store import vector_store

@pytest.fixture(scope="module")
def initialized_store():
    run_ingestion()
    return vector_store

def test_golden_evaluation_dataset_retrieval(initialized_store):
    """
    Evaluates Hit Rate@3, Mean Reciprocal Rank (MRR), and Source Attribution
    against the Golden Evaluation Dataset of realistic Kenyan student queries.
    """
    eval_file = Path(__file__).parent / "data" / "golden_evaluation_dataset.json"
    assert eval_file.exists(), f"Evaluation dataset {eval_file} not found."

    with open(eval_file, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    in_domain_cases = [tc for tc in test_cases if not tc.get("is_out_of_domain")]
    
    hits_at_1 = 0
    hits_at_3 = 0
    reciprocal_ranks = []
    attribution_matches = 0

    print(f"\nEvaluating {len(in_domain_cases)} in-domain golden queries...")

    for tc in in_domain_cases:
        query = tc["query"]
        expected_id = tc["expected_opportunity_id"]
        expected_url = tc["expected_official_url"]

        results = initialized_store.search(query=query, top_k=3)
        retrieved_ids = [r["metadata"].get("opportunity_id") for r in results]

        if retrieved_ids and retrieved_ids[0] == expected_id:
            hits_at_1 += 1

        if expected_id in retrieved_ids:
            hits_at_3 += 1
            rank = retrieved_ids.index(expected_id) + 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

        for r in results:
            if r["metadata"].get("opportunity_id") == expected_id:
                if r["metadata"].get("official_url") == expected_url:
                    attribution_matches += 1
                break

    hit_rate_at_1 = hits_at_1 / len(in_domain_cases)
    hit_rate_at_3 = hits_at_3 / len(in_domain_cases)
    mrr = sum(reciprocal_ranks) / len(in_domain_cases)
    attribution_rate = attribution_matches / len(in_domain_cases)

    print(f"\n--- RAG RETRIEVAL EVALUATION REPORT ---")
    print(f"Total In-Domain Test Queries: {len(in_domain_cases)}")
    print(f"Hit Rate @ 1: {hit_rate_at_1:.2%}")
    print(f"Hit Rate @ 3: {hit_rate_at_3:.2%}")
    print(f"Mean Reciprocal Rank (MRR): {mrr:.4f}")
    print(f"Source Attribution Rate: {attribution_rate:.2%}")
    print("---------------------------------------")

    assert hit_rate_at_3 >= 0.85, f"Hit Rate@3 ({hit_rate_at_3:.2%}) below required 85% threshold."
    assert mrr >= 0.70, f"MRR ({mrr:.4f}) below required 0.70 threshold."
    assert attribution_rate >= 0.90, f"Attribution Rate ({attribution_rate:.2%}) below 90% threshold."

def test_out_of_domain_handling(initialized_store):
    """
    Tests that out-of-domain queries produce low similarity scores,
    enabling the agent to recognize insufficient evidence and avoid hallucinations.
    """
    ood_query = "How to apply for junior ice hockey club scholarship in Canada?"
    results = initialized_store.search(query=ood_query, top_k=3)

    if results:
        top_score = results[0]["similarity_score"]
        print(f"Out of domain query top similarity score: {top_score}")
        assert top_score < 0.50, f"Expected low similarity score for out-of-domain query, got {top_score}"
