"""Tests for Intent Understanding and Ambiguity Resolution in Opportunity Intelligence AI."""

import pytest
from app.agent.intent import classify_intent, IntentType, extract_entities
from app.agent.orchestrator import AgentOrchestrator


def test_classify_ambiguous_queries():
    """Single-word or underspecified queries must be classified as AMBIGUOUS_INCOMPLETE."""
    ambiguous_examples = [
        "academic",
        "scholarships",
        "internship",
        "opportunities",
        "bursaries",
        "help",
    ]
    for text in ambiguous_examples:
        intent, meta = classify_intent(text)
        assert intent == IntentType.AMBIGUOUS_INCOMPLETE, f"Expected AMBIGUOUS_INCOMPLETE for '{text}', got {intent}"
        assert "ambiguous_term" in meta or "academic" in text


def test_classify_clear_discovery_queries():
    """Specific queries with field, degree, or location must route to domain search/discovery."""
    clear_examples = [
        ("Find computer science scholarships for undergraduate students in Kenya", IntentType.SCHOLARSHIP_SEARCH),
        ("Show me tech internships in Nairobi for software engineers", IntentType.INTERNSHIP_SEARCH),
        ("Look for graduate trainee programs in Kenya", IntentType.GRADUATE_PROGRAMME_SEARCH),
    ]
    for text, expected_intent in clear_examples:
        intent, _ = classify_intent(text)
        assert intent == expected_intent, f"Expected {expected_intent} for '{text}', got {intent}"


def test_classify_comparison_queries():
    """Queries asking which opportunity has earliest deadline or comparing must route to OPPORTUNITY_COMPARISON."""
    queries = [
        "Which one has the earliest deadline?",
        "Compare these opportunities",
        "Which of them is closing soonest?",
        "Which one should I apply to first?",
    ]
    for text in queries:
        intent, meta = classify_intent(text)
        assert intent == IntentType.OPPORTUNITY_COMPARISON, f"Expected OPPORTUNITY_COMPARISON for '{text}', got {intent}"


def test_classify_greeting_and_social():
    """Greetings and social introductions must route to GREETING_SOCIAL."""
    greetings = [
        "Hello there",
        "Hi",
        "Habari",
        "Who are you",
        "Good morning",
    ]
    for text in greetings:
        intent, _ = classify_intent(text)
        assert intent == IntentType.GREETING_SOCIAL, f"Expected GREETING_SOCIAL for '{text}', got {intent}"


def test_classify_out_of_scope():
    """Queries unrelated to Kenya educational and early career opportunities must route to OUT_OF_SCOPE."""
    out_of_scope = [
        "Write a poem about the ocean",
        "How do I cook pilau?",
        "Can you hack this password?",
        "What is the rocket launch trajectory to mars?",
    ]
    for text in out_of_scope:
        intent, _ = classify_intent(text)
        assert intent == IntentType.OUT_OF_SCOPE, f"Expected OUT_OF_SCOPE for '{text}', got {intent}"


def test_classify_eligibility_and_checklist():
    """Questions asking about eligibility or application documents route appropriately."""
    intent_eligibility, _ = classify_intent("Am I eligible for Safaricom attachment?")
    assert intent_eligibility == IntentType.ELIGIBILITY_ASSESSMENT

    intent_checklist, _ = classify_intent("What documents do I need to apply for Equity Leaders Program?")
    assert intent_checklist == IntentType.CHECKLIST_GENERATION


def test_ambiguous_query_orchestrator_returns_clarification_not_dump():
    """When a student enters 'academic', assistant must ask a clarification question
    and NOT return a specific opportunity record (e.g. Equity Leaders Program).
    """
    orchestrator = AgentOrchestrator()
    response = orchestrator.process_turn(message="academic", conversation_id="test-academic-conv")

    assert response["intent"] == IntentType.AMBIGUOUS_INCOMPLETE.value
    msg = response["response"]
    assert "are you looking for" in msg.lower() or "which area" in msg.lower() or "explore" in msg.lower()
    assert "Equity Leaders Program" not in msg
    assert "Safaricom" not in msg
    assert "1." in msg and "2." in msg
