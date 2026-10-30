"""Tests for Natural Language Intent Detection and Opportunity Discovery Experience.
Verifies all 17 natural language student request benchmarks from the user prompt:
1. Greet student ('hello', 'hi there')
2. Opportunity discovery ('I need some of the opportunity', 'Show me opportunities', 'Show me more')
3. Category searches ('Any scholarships available?', 'I need attachment', 'What jobs can I apply for?')
4. Field-specific search ('Anything for computer science students?')
5. Follow-up and context memory ('What about Safaricom?', 'What are the requirements?', 'Am I eligible?', 'When is the deadline?', 'Help me apply')
6. Comparison ('Which one is best for me?')
7. Courteous closing ('Thank you')
"""

import pytest
from app.db.session import SessionLocal
from app.agent.orchestrator import AgentOrchestrator
from app.agent.intent import classify_intent, IntentType


def test_intent_detection_table_benchmarks():
    """Validates intent classification across all prompt benchmark phrases."""
    benchmarks = [
        ("hello", IntentType.GREETING_SOCIAL),
        ("hi there", IntentType.GREETING_SOCIAL),
        ("I need some of the opportunity", IntentType.OPPORTUNITY_DISCOVERY),
        ("I need some opportunities", IntentType.OPPORTUNITY_DISCOVERY),
        ("Show me opportunities", IntentType.OPPORTUNITY_DISCOVERY),
        ("Any scholarships available?", IntentType.SCHOLARSHIP_SEARCH),
        ("I need attachment", IntentType.INTERNSHIP_SEARCH),
        ("What jobs can I apply for?", IntentType.GRADUATE_PROGRAMME_SEARCH),
        ("Anything for computer science students?", IntentType.FIELD_SEARCH),
        ("What about Safaricom?", IntentType.FOLLOW_UP_QUESTION),
        ("What are the requirements?", IntentType.EXPLAIN_REQUIREMENTS),
        ("Am I eligible?", IntentType.ELIGIBILITY_ASSESSMENT),
        ("When is the deadline?", IntentType.DEADLINE_INQUIRY),
        ("Help me apply", IntentType.CHECKLIST_GENERATION),
        ("Show me more", IntentType.OPPORTUNITY_DISCOVERY),
        ("Which one is best for me?", IntentType.OPPORTUNITY_COMPARISON),
        ("Thank you", IntentType.THANK_YOU),
    ]

    for query, expected_intent in benchmarks:
        intent, _ = classify_intent(query)
        assert intent == expected_intent, f"Query '{query}' classified as {intent}, expected {expected_intent}"


def test_opportunity_discovery_for_i_need_some_of_the_opportunity():
    """CRITICAL TEST: When a student types 'I need some of the opportunity',

    the assistant MUST NOT refuse or say 'I could not find verified Kenyan records'.
    It MUST return the category breakdown and verified opportunities with official links.
    """
    orch = AgentOrchestrator()
    with SessionLocal() as db:
        res = orch.process_turn(
            message="I need some of the opportunity",
            conversation_id="test-discovery-fix-session",
            db=db
        )

        assert res["intent"] == IntentType.OPPORTUNITY_DISCOVERY.value
        reply = res["response"]

        # 1. Must NOT be an out-of-scope or not-found refusal
        assert "could not find verified kenyan records" not in reply.lower()
        assert "to prevent misinformation" not in reply.lower()

        # 2. Must introduce the categories
        assert "help you discover opportunities" in reply.lower()
        assert "scholarships" in reply.lower()
        assert "attachments" in reply.lower() or "internships" in reply.lower()
        assert "graduate trainee" in reply.lower()

        # 3. Must contain real verified opportunities
        assert len(res["citations"]) > 0
        assert "http" in reply

        # 4. Must save discussed opportunities in state
        assert len(res["state"]["discussed_opportunities"]) >= 2


def test_contextual_multi_turn_followup_chain():
    """Tests the full multi-turn chain where context flows from discovery -> provider -> requirements -> eligibility -> deadline -> apply -> thank you."""
    orch = AgentOrchestrator()
    conv_id = "test-chain-session-999"
    student = {
        "university": "University of Nairobi",
        "field_of_study": "Computer Science",
        "degree_level": "Undergraduate",
        "year_of_study": 3
    }

    with SessionLocal() as db:
        # Turn 1: Search for internships
        t1 = orch.process_turn("Show me internships for computer science students", conv_id, db=db, student_profile=student)
        assert t1["intent"] == IntentType.FIELD_SEARCH.value

        # Turn 2: Follow up about Safaricom
        t2 = orch.process_turn("Tell me about Safaricom", conv_id, db=db, student_profile=student)
        assert t2["intent"] == IntentType.FOLLOW_UP_QUESTION.value
        assert "safaricom" in t2["response"].lower()

        # Turn 3: Ask for requirements
        t3 = orch.process_turn("What are the requirements?", conv_id, db=db, student_profile=student)
        assert t3["intent"] == IntentType.EXPLAIN_REQUIREMENTS.value
        assert "requirements" in t3["response"].lower()

        # Turn 4: Check eligibility (using student profile in memory)
        t4 = orch.process_turn("Am I eligible?", conv_id, db=db, student_profile=student)
        assert t4["intent"] == IntentType.ELIGIBILITY_ASSESSMENT.value
        assert "eligible" in t4["response"].lower()

        # Turn 5: Check deadline
        t5 = orch.process_turn("What is the deadline?", conv_id, db=db, student_profile=student)
        assert t5["intent"] == IntentType.DEADLINE_INQUIRY.value
        assert "deadline" in t5["response"].lower()

        # Turn 6: Help me apply
        t6 = orch.process_turn("Help me apply", conv_id, db=db, student_profile=student)
        assert t6["intent"] == IntentType.CHECKLIST_GENERATION.value
        assert "- [ ]" in t6["response"]

        # Turn 7: Thank you
        t7 = orch.process_turn("Thank you", conv_id, db=db, student_profile=student)
        assert t7["intent"] == IntentType.THANK_YOU.value
        assert "welcome" in t7["response"].lower()
        # Verify no tools executed on thank you
        assert len(t7["tool_calls"]) == 0
