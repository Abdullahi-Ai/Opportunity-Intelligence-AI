"""
Comprehensive Regression Tests for Opportunity Intelligence AI:
1. Academic Profile Preservation (Criteria 1-8)
2. Five-Category Opportunity Discovery (Criteria 9-15)
3. Reliable Deadline & Application-Status Provenance (Criteria 16-20)
"""

import pytest
from datetime import date
from app.agent.intent import classify_intent, extract_entities, IntentType
from app.agent.orchestrator import AgentOrchestrator
from app.agent.memory import ConversationState
from app.agent.prompts import build_student_context_prompt
from app.agent.tools import (
    tool_search_opportunities,
    SearchOpportunitiesInput,
    tool_calculate_deadline_countdown,
    DeadlineCountdownInput,
    tool_assess_eligibility,
    AssessEligibilityInput
)
from app.models.entities import StudentProfile
from app.api.endpoints import StudentProfileCreate, StudentProfileResponse


# -------------------------------------------------------------------------
# Part 1: Academic Profile Preservation (Criteria 1 - 8)
# -------------------------------------------------------------------------

def test_1_academic_profile_preservation():
    """Criterion 1-7: Full academic profile is extracted and preserved."""
    user_prompt = (
        "I am a Kenyan university student pursuing a Bachelor of Arts in Social Sciences, "
        "specialising in Sociology and Psychology at the University of Nairobi. I expect to graduate in December 2026. "
        "Find scholarships, internships, fellowships, research opportunities and career development programmes that are relevant to my academic background."
    )
    entities = extract_entities(user_prompt)
    assert entities.get("university") == "University of Nairobi"
    assert entities.get("degree_level") == "Undergraduate"
    assert entities.get("field_of_study") == "Social Sciences & Humanities"
    assert entities.get("degree_title") == "Bachelor of Arts in Social Sciences"
    assert "Sociology" in entities.get("specialisations", [])
    assert "Psychology" in entities.get("specialisations", [])
    assert entities.get("expected_graduation") == "December 2026"
    assert entities.get("country") == "Kenya"


def test_2_zero_unsolicited_computer_science_substitution():
    """Criterion 8: The English pronoun 'it' must NEVER trigger Computer Science."""
    queries_with_it = [
        "Why it is relevant to my degree.",
        "When was it posted on the official portal?",
        "Is it open right now for Kenyan university applicants?",
        "Can I apply for it as a continuing student?",
        "Tell me more about it."
    ]
    for q in queries_with_it:
        entities = extract_entities(q)
        assert entities.get("field_of_study") is None, f"Query '{q}' erroneously set field_of_study to {entities.get('field_of_study')}"


def test_3_session_multi_turn_profile_retention():
    """Criterion 1-7: Multi-turn conversations retain student profile memory."""
    orchestrator = AgentOrchestrator(model="llama-3.3-70b-versatile")
    turn1_prompt = (
        "I am a Kenyan student pursuing a Bachelor of Arts in Social Sciences, "
        "specialising in Sociology and Psychology at the University of Nairobi. I expect to graduate in December 2026."
    )
    res1 = orchestrator.process_turn(message=turn1_prompt, conversation_id="conv-session-retention")
    state_mem = res1["state"]["student_memory"]

    assert state_mem.get("degree_title") == "Bachelor of Arts in Social Sciences"
    assert "Sociology" in state_mem.get("specialisations", [])
    assert "Psychology" in state_mem.get("specialisations", [])
    assert state_mem.get("university") == "University of Nairobi"
    assert state_mem.get("field_of_study") == "Social Sciences & Humanities"
    assert state_mem.get("expected_graduation") == "December 2026"
    assert state_mem.get("country") == "Kenya"

    # Turn 2: Follow-up question without restating background
    res2 = orchestrator.process_turn(message="What documents are needed for HEF?", conversation_id="conv-session-retention")
    state_mem2 = res2["state"]["student_memory"]
    assert state_mem2.get("degree_title") == "Bachelor of Arts in Social Sciences"
    assert state_mem2.get("university") == "University of Nairobi"
    assert state_mem2.get("field_of_study") == "Social Sciences & Humanities"


def test_4_explicit_correction_overwrites_stale_memory():
    """Criterion 1-7: Explicit in-query student corrections immediately overwrite stale memory."""
    orchestrator = AgentOrchestrator(model="llama-3.3-70b-versatile")
    state = ConversationState(conversation_id="conv-correction-01")
    # Simulate prior contaminated memory
    state.student_memory["field_of_study"] = "Computer Science"
    state.student_memory["university"] = "Kenyatta University"
    state.student_memory["degree_title"] = "BSc Computer Science"

    correction_message = "Actually, I study Sociology and Psychology, not Computer Science at the University of Nairobi"
    entities = extract_entities(correction_message)
    assert entities.get("field_of_study") == "Social Sciences & Humanities"
    assert entities.get("university") == "University of Nairobi"

    # Update state
    if entities.get("field_of_study"):
        state.student_memory["field_of_study"] = entities["field_of_study"]
    if entities.get("university"):
        state.student_memory["university"] = entities["university"]

    assert state.student_memory["field_of_study"] == "Social Sciences & Humanities"
    assert state.student_memory["university"] == "University of Nairobi"


def test_5_student_profile_model_persistence():
    """Criterion 1-7: StudentProfile entity model supports academic profile extension fields."""
    profile = StudentProfile(
        id="sp-test-social-sci",
        user_id="usr-test-01",
        full_name="Amina Odhiambo",
        university="University of Nairobi",
        degree_level="Undergraduate",
        field_of_study="Social Sciences & Humanities",
        degree_title="Bachelor of Arts in Social Sciences",
        specialisations=["Sociology", "Psychology"],
        expected_graduation="December 2026",
        country="Kenya"
    )
    assert profile.degree_title == "Bachelor of Arts in Social Sciences"
    assert profile.specialisations == ["Sociology", "Psychology"]
    assert profile.expected_graduation == "December 2026"
    assert profile.country == "Kenya"


def test_6_auth_and_endpoint_profile_schemas():
    """Criterion 1-7: API schemas carry profile extension fields without hardcoded CS default."""
    create_schema = StudentProfileCreate(
        email="amina@uonbi.ac.ke",
        full_name="Amina Odhiambo",
        university="University of Nairobi",
        degree_level="Undergraduate",
        field_of_study="Social Sciences & Humanities",
        degree_title="Bachelor of Arts in Social Sciences",
        specialisations=["Sociology", "Psychology"],
        expected_graduation="December 2026",
        country="Kenya",
        year_of_study=3
    )
    data = create_schema.model_dump()
    assert data["degree_title"] == "Bachelor of Arts in Social Sciences"
    assert data["specialisations"] == ["Sociology", "Psychology"]
    assert data["field_of_study"] != "Computer Science"


def test_7_prompt_context_builder_includes_full_profile():
    """Criterion 1-7: build_student_context_prompt generates rich student profile instructions."""
    mem = {
        "university": "University of Nairobi",
        "degree_level": "Undergraduate",
        "field_of_study": "Social Sciences & Humanities",
        "degree_title": "Bachelor of Arts in Social Sciences",
        "specialisations": ["Sociology", "Psychology"],
        "expected_graduation": "December 2026",
        "country": "Kenya"
    }
    prompt_text = build_student_context_prompt(mem)
    assert "University of Nairobi" in prompt_text
    assert "Bachelor of Arts in Social Sciences" in prompt_text
    assert "Sociology, Psychology" in prompt_text
    assert "December 2026" in prompt_text
    assert "Kenya" in prompt_text
    assert "Computer Science" not in prompt_text


def test_8_compound_intent_routing_prioritizes_discovery():
    """Criterion 8: Multi-category prompts with secondary eligibility instructions route to OPPORTUNITY_DISCOVERY."""
    prompt = (
        "I am a Kenyan university student pursuing a Bachelor of Arts in Social Sciences, specialising in Sociology and Psychology at the University of Nairobi. "
        "I expect to graduate in December 2026. Find scholarships, internships, fellowships, research opportunities and career development programmes that are relevant to my academic background. "
        "For each opportunity, explain: 1. Why it is relevant to my degree. 2. Its eligibility requirements. 3. Whether I am likely to qualify. "
        "4. The application deadline. 5. The required application documents. 6. The official application website."
    )
    intent, meta = classify_intent(prompt)
    assert intent == IntentType.OPPORTUNITY_DISCOVERY
    assert meta["entities"].get("field_of_study") == "Social Sciences & Humanities"


# -------------------------------------------------------------------------
# Part 2: Five-Category Opportunity Discovery (Criteria 9 - 15)
# -------------------------------------------------------------------------

def test_9_discovery_evaluates_all_five_categories():
    """Criterion 9: Orchestrator evaluates all 5 requested categories."""
    orchestrator = AgentOrchestrator(model="llama-3.3-70b-versatile")
    user_prompt = (
        "I am a Kenyan university student pursuing a Bachelor of Arts in Social Sciences, "
        "specialising in Sociology and Psychology at the University of Nairobi. I expect to graduate in December 2026. "
        "Find scholarships, internships, fellowships, research opportunities and career development programmes that are relevant to my academic background."
    )
    res = orchestrator.process_turn(message=user_prompt, conversation_id="conv-five-cat-01")
    response_text = res["response"]

    assert "1. Scholarships" in response_text
    assert "2. Internships" in response_text
    assert "3. Fellowships" in response_text
    assert "4. Research Opportunities" in response_text
    assert "5. Career Development Programmes" in response_text


def test_10_category_coverage_status_reporting():
    """Criterion 10: Every category reports a clear Category Coverage Status."""
    orchestrator = AgentOrchestrator(model="llama-3.3-70b-versatile")
    user_prompt = (
        "I am a Kenyan university student pursuing a Bachelor of Arts in Social Sciences, "
        "specialising in Sociology and Psychology at the University of Nairobi. I expect to graduate in December 2026. "
        "Find scholarships, internships, fellowships, research opportunities and career development programmes that are relevant to my academic background."
    )
    res = orchestrator.process_turn(message=user_prompt, conversation_id="conv-cat-status-01")
    response_text = res["response"]

    # Each category header must have Category Coverage Status
    assert "Category Coverage Status: `Matches found`" in response_text or "Category Coverage Status: `No matching records found`" in response_text
    assert response_text.count("Category Coverage Status:") == 5


def test_11_point_1_relevance_to_degree():
    """Criterion 11: Point 1 explains why each opportunity is relevant to the degree."""
    orchestrator = AgentOrchestrator(model="llama-3.3-70b-versatile")
    user_prompt = (
        "I am a Kenyan university student pursuing a Bachelor of Arts in Social Sciences, "
        "specialising in Sociology and Psychology at the University of Nairobi. I expect to graduate in December 2026. "
        "Find scholarships, internships, fellowships, research opportunities and career development programmes that are relevant to my academic background."
    )
    res = orchestrator.process_turn(message=user_prompt, conversation_id="conv-rel-01")
    response_text = res["response"]

    assert "Relevance to Degree (Bachelor of Arts in Social Sciences):" in response_text


def test_12_point_2_published_eligibility_requirements():
    """Criterion 12: Point 2 details published eligibility requirements."""
    orchestrator = AgentOrchestrator(model="llama-3.3-70b-versatile")
    user_prompt = (
        "I am a Kenyan university student pursuing a Bachelor of Arts in Social Sciences, "
        "specialising in Sociology and Psychology at the University of Nairobi. I expect to graduate in December 2026. "
        "Find scholarships, internships, fellowships, research opportunities and career development programmes that are relevant to my academic background."
    )
    res = orchestrator.process_turn(message=user_prompt, conversation_id="conv-elig-01")
    response_text = res["response"]

    assert "Eligibility Requirements:" in response_text
    assert "Degree Level:" in response_text


def test_13_point_3_likelihood_of_qualifying():
    """Criterion 13: Point 3 assesses likelihood of qualifying based on current standing."""
    orchestrator = AgentOrchestrator(model="llama-3.3-70b-versatile")
    user_prompt = (
        "I am a Kenyan university student pursuing a Bachelor of Arts in Social Sciences, "
        "specialising in Sociology and Psychology at the University of Nairobi. I expect to graduate in December 2026. "
        "Find scholarships, internships, fellowships, research opportunities and career development programmes that are relevant to my academic background."
    )
    res = orchestrator.process_turn(message=user_prompt, conversation_id="conv-qual-01")
    response_text = res["response"]

    assert "Likelihood of Qualifying:" in response_text
    assert ("Likely to qualify" in response_text) or ("Criteria difference" in response_text)


def test_14_point_4_deadline_with_provenance():
    """Criterion 14: Point 4 provides official deadline and provenance."""
    orchestrator = AgentOrchestrator(model="llama-3.3-70b-versatile")
    user_prompt = (
        "I am a Kenyan university student pursuing a Bachelor of Arts in Social Sciences, "
        "specialising in Sociology and Psychology at the University of Nairobi. I expect to graduate in December 2026. "
        "Find scholarships, internships, fellowships, research opportunities and career development programmes that are relevant to my academic background."
    )
    res = orchestrator.process_turn(message=user_prompt, conversation_id="conv-deadl-01")
    response_text = res["response"]

    assert "Official Deadline & Provenance:" in response_text
    assert "Deadline Provenance:" in response_text


def test_15_point_5_required_documents_and_point_6_official_portal():
    """Criterion 15: Points 5 & 6 provide required application documents and official website."""
    orchestrator = AgentOrchestrator(model="llama-3.3-70b-versatile")
    user_prompt = (
        "I am a Kenyan university student pursuing a Bachelor of Arts in Social Sciences, "
        "specialising in Sociology and Psychology at the University of Nairobi. I expect to graduate in December 2026. "
        "Find scholarships, internships, fellowships, research opportunities and career development programmes that are relevant to my academic background."
    )
    res = orchestrator.process_turn(message=user_prompt, conversation_id="conv-docs-01")
    response_text = res["response"]

    assert "Required Application Documents:" in response_text
    assert "Official Application Website:" in response_text
    assert len(res["citations"]) > 0


# -------------------------------------------------------------------------
# Part 3: Reliable Deadline & Application-Status Provenance (Criteria 16 - 20)
# -------------------------------------------------------------------------

def test_16_officially_verified_provenance():
    """Criterion 16: Officially verified deadline has 'Officially verified' provenance."""
    res = tool_calculate_deadline_countdown(DeadlineCountdownInput(
        deadline_date_str="2026-12-31",
        is_officially_verified=True,
        verification_source="Universities Fund (HEF)",
        verification_date="2026-11-01"
    ))
    assert res.get("deadline_provenance") == "Officially verified"
    assert res.get("application_status_provenance") == "Officially confirmed"
    assert "Officially verified" in res.get("status_label", "")


def test_17_recorded_in_directory_provenance():
    """Criterion 17: Date present but unverified has 'Recorded in directory — requires official verification'."""
    res = tool_calculate_deadline_countdown(DeadlineCountdownInput(
        deadline_date_str="2026-12-31",
        is_officially_verified=False
    ))
    assert res.get("deadline_provenance") == "Recorded in directory — requires official verification"
    assert res.get("application_status_provenance") == "Application status unconfirmed"


def test_18_deadline_unavailable_for_missing_date():
    """Criterion 18: Missing or empty deadline produces 'Deadline unavailable'."""
    res = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=None))
    assert res.get("deadline_provenance") == "Deadline unavailable"
    assert res.get("application_status_provenance") == "Application status unconfirmed"
    assert res.get("deadline") is None


def test_19_no_invented_days_remaining_for_unspecified():
    """Criterion 19: Unspecified or missing deadline returns days_remaining=None (no hallucinated dates)."""
    res = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str="Unspecified"))
    assert res.get("days_remaining") is None
    assert res.get("days_ago") is None
    assert res.get("deadline") is None
    assert "Rolling / Open" in res.get("status_label", "")


def test_20_rolling_intake_provenance():
    """Criterion 20: Rolling admissions are clearly distinguished with rolling intake status."""
    res = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str="rolling"))
    assert res.get("is_open") is True
    assert res.get("days_remaining") is None
    assert res.get("deadline_provenance") == "Recorded in directory — requires official verification"
    assert "Rolling / Continuous intake" in res.get("application_status_provenance")
