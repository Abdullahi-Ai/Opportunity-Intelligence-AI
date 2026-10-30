import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.agent.orchestrator import agent_orchestrator, SESSION_CONTEXT_CACHE

client = TestClient(app)

def test_tool_dispatch_execution():
    # 1. Test search tool execution
    search_res = agent_orchestrator.execute_tool(
        "search_opportunities",
        {"query": "Safaricom attachment", "top_k": 2}
    )
    assert search_res["status"] == "success"
    assert search_res["count"] > 0

    # 2. Test deadline countdown tool execution
    date_res = agent_orchestrator.execute_tool(
        "calculate_deadline_countdown",
        {"deadline_date_str": "2026-11-30"}
    )
    assert date_res["status"] in ["open", "expired", "closing_today"]
    assert "deadline" in date_res

    # 3. Test eligibility assessment tool execution
    elig_res = agent_orchestrator.execute_tool(
        "assess_eligibility",
        {
            "opportunity_id": "opp-safaricom-attachment-2026",
            "student_degree_level": "Undergraduate",
            "student_field_of_study": "Computer Science",
            "student_year_of_study": 3
        }
    )
    assert elig_res["status"] == "success"
    assert "Likely Eligible" in elig_res["overall_assessment"]

    # 4. Test checklist tool execution
    chk_res = agent_orchestrator.execute_tool(
        "generate_application_checklist",
        {"opportunity_id": "opp-hef-undergraduate-2026"}
    )
    assert chk_res["status"] == "success"
    assert len(chk_res["tasks"]) > 0

def test_agent_fallback_checklist_query():
    session_id = "test_checklist_session"
    res = agent_orchestrator.chat(
        message="What is the application checklist and required documents for HEF government scholarship?",
        session_id=session_id
    )
    assert res["grounded"] is True
    assert len(res["citations"]) > 0
    assert "hef" in res["response"].lower() or "checklist" in res["response"].lower()
    assert "- [ ]" in res["response"]

def test_agent_fallback_eligibility_query_with_student_profile():
    student_profile = {
        "full_name": "Faith Chebet",
        "university": "Kenyatta University",
        "field_of_study": "Computer Science",
        "degree_level": "Undergraduate",
        "year_of_study": 3
    }
    session_id = "test_elig_session"
    res = agent_orchestrator.chat(
        message="Am I eligible for Safaricom industrial attachment?",
        session_id=session_id,
        student_profile=student_profile
    )
    assert res["grounded"] is True
    assert "Eligibility Assessment" in res["response"] or "Eligible" in res["response"]
    assert "safaricom" in res["response"].lower()

def test_agent_multi_turn_context_memory():
    session_id = "test_multi_turn_memory"
    # Turn 1
    agent_orchestrator.chat(
        message="Tell me about Chevening scholarship in Kenya.",
        session_id=session_id
    )
    assert session_id in SESSION_CONTEXT_CACHE
    assert len(SESSION_CONTEXT_CACHE[session_id]) >= 2

    # Turn 2
    agent_orchestrator.chat(
        message="What are the work experience requirements?",
        session_id=session_id
    )
    assert len(SESSION_CONTEXT_CACHE[session_id]) >= 4

def test_chat_api_endpoint():
    payload = {
        "message": "What opportunities exist for undergraduate tech students in Kenya?",
        "session_id": "api_test_session"
    }
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert len(data["response"]) > 50
    assert data["session_id"] == "api_test_session"
    assert "timestamp" in data
