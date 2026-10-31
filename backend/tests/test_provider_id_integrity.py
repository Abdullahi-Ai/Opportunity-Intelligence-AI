"""
Provider ID Integrity & Verification Suite.
Verifies authoritative opportunity identifier mappings for all eight corrected providers:
1. KRA (opp-kra-internship-2026)
2. Chevening (opp-chevening-kenya-2027)
3. DAAD (opp-daad-region-kenya-2027)
4. Equity (opp-equity-leaders-elp-2026)
5. KCB (opp-kcb-foundation-tertiary-2026)
6. Mawazo (opp-mawazo-fellowship-2027)
7. PDTP (opp-pdtp-digika-2026)
8. PSIP (opp-psc-psip-internship-2026)

Tests:
- Entity extraction maps provider keyword to the exact authoritative ID in DB & ChromaDB.
- tool_assess_eligibility successfully evaluates criteria with the authoritative ID.
- Follow-up questions resolve to the correct provider and ID.
- Unknown providers are handled gracefully without exceptions or unrendered None.
"""

import pytest
from app.agent.intent import extract_entities, classify_intent, KNOWN_PROVIDERS, IntentType
from app.agent.tools import tool_assess_eligibility, AssessEligibilityInput
from app.agent.orchestrator import agent_orchestrator
from app.db.session import SessionLocal

PROVIDERS_TEST_MATRIX = [
    ("kra", "opp-kra-internship-2026", "Kenya Revenue Authority"),
    ("chevening", "opp-chevening-kenya-2027", "Chevening"),
    ("daad", "opp-daad-region-kenya-2027", "DAAD"),
    ("equity", "opp-equity-leaders-elp-2026", "Equity Leaders Program"),
    ("kcb", "opp-kcb-foundation-tertiary-2026", "KCB Foundation"),
    ("mawazo", "opp-mawazo-fellowship-2027", "Mawazo"),
    ("pdtp", "opp-pdtp-digika-2026", "Presidential Digital Talent"),
    ("psip", "opp-psc-psip-internship-2026", "Public Service Commission"),
]

@pytest.mark.parametrize("keyword,expected_id,expected_name", PROVIDERS_TEST_MATRIX)
def test_provider_entity_extraction_authoritative_id(keyword, expected_id, expected_name):
    """Verifies that keyword extracts the exact authoritative opportunity ID."""
    entities = extract_entities(f"Tell me about {keyword} opportunities in Kenya")
    assert entities["opportunity_id"] == expected_id, f"Keyword '{keyword}' mapped to {entities['opportunity_id']}, expected {expected_id}"

@pytest.mark.parametrize("keyword,expected_id,expected_name", PROVIDERS_TEST_MATRIX)
def test_tool_assess_eligibility_succeeds_for_all_providers(keyword, expected_id, expected_name):
    """Verifies that eligibility tool successfully finds criteria in ChromaDB using the authoritative ID."""
    input_data = AssessEligibilityInput(
        opportunity_id=expected_id,
        student_degree_level="Undergraduate",
        student_field_of_study="Computer Science",
        student_year_of_study=3
    )
    result = tool_assess_eligibility(input_data)
    assert result["status"] == "success", f"Eligibility check failed for {expected_id}: {result}"
    assert result["opportunity_id"] == expected_id
    assert len(result["criteria_breakdown"]) >= 2
    assert result["overall_assessment"] is not None

@pytest.mark.parametrize("keyword,expected_id,expected_name", PROVIDERS_TEST_MATRIX)
def test_orchestrator_eligibility_query_for_all_providers(keyword, expected_id, expected_name):
    """Verifies that user querying 'Am I eligible for <provider>?' receives a well-formed breakdown, not None."""
    with SessionLocal() as db:
        res = agent_orchestrator.process_turn(
            message=f"Am I eligible for {keyword}?",
            conversation_id=f"test-prov-{keyword}",
            db=db,
            student_profile={
                "university": "University of Nairobi",
                "field_of_study": "Computer Science",
                "degree_level": "Undergraduate",
                "year_of_study": 3
            }
        )
        assert res["intent"] == IntentType.ELIGIBILITY_ASSESSMENT.value
        assert "Overall Result:" in res["response"]
        assert "**None**" not in res["response"]
        assert expected_id in [tc.get("opportunity_id") for tc in res["tool_calls"]]

def test_unknown_provider_handled_gracefully():
    """An unknown provider must not crash or output unrendered None."""
    with SessionLocal() as db:
        res = agent_orchestrator.process_turn(
            message="Am I eligible for NonExistentOrganization123?",
            conversation_id="test-unknown-provider",
            db=db
        )
        assert "**None**" not in res["response"]
        assert "Which opportunity" in res["response"] or "verified" in res["response"].lower()
