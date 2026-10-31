"""Multi-Turn Conversational Memory & State Persistence Tests.
Verifies the 7 required conversational memory specifications:
1. University memory
2. Year of study memory
3. Follow-up comparison (earliest deadline)
4. Pending question resolution (e.g. 'Both')
5. Conversation isolation (RBAC & multi-tenant user isolation)
6. State and message persistence
7. Conversation deletion
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.agent.orchestrator import AgentOrchestrator
from app.agent.memory import (
    get_or_create_conversation,
    load_conversation_state,
    save_conversation_state
)
from app.agent.intent import IntentType
from app.models.entities import Conversation, ConversationMessage

client = TestClient(app)


def test_memory_1_university_preference_memory():
    """Test 1: When student provides university, assistant persists it in state
    and uses it in subsequent searches.
    """
    orchestrator = AgentOrchestrator()
    conv_id = f"test-uni-{uuid.uuid4().hex[:8]}"

    with SessionLocal() as db:
        res1 = orchestrator.process_turn(
            message="I study at University of Nairobi",
            conversation_id=conv_id,
            db=db
        )
        assert res1["state"]["student_profile"].get("university") == "University of Nairobi"
        assert "University of Nairobi" in res1["response"]

        res2 = orchestrator.process_turn(
            message="Find scholarships for my course",
            conversation_id=conv_id,
            db=db
        )
        assert res2["state"]["student_profile"].get("university") == "University of Nairobi"


def test_memory_2_year_of_study_memory_and_eligibility():
    """Test 2: Student says 'I am in my third year'; subsequent eligibility check uses year 3."""
    orchestrator = AgentOrchestrator()
    conv_id = f"test-yr-{uuid.uuid4().hex[:8]}"

    with SessionLocal() as db:
        res1 = orchestrator.process_turn(
            message="I am in my third year of study",
            conversation_id=conv_id,
            db=db
        )
        assert res1["state"]["student_profile"].get("year_of_study") == 3

        res2 = orchestrator.process_turn(
            message="Am I eligible for the Safaricom industrial attachment?",
            conversation_id=conv_id,
            db=db
        )
        assert res2["state"]["student_profile"].get("year_of_study") == 3
        assert "eligible" in res2["response"].lower()


def test_memory_3_followup_earliest_deadline_comparison():
    """Test 3: Search returns opportunities; student asks 'Which one has the earliest deadline?';
    assistant compares discussed opportunities without re-asking.
    """
    orchestrator = AgentOrchestrator()
    conv_id = f"test-comp-{uuid.uuid4().hex[:8]}"

    with SessionLocal() as db:
        res1 = orchestrator.process_turn(
            message="Find scholarships in Kenya",
            conversation_id=conv_id,
            db=db
        )
        assert len(res1["state"]["discussed_opportunities"]) > 0

        res2 = orchestrator.process_turn(
            message="Which one has the earliest deadline?",
            conversation_id=conv_id,
            db=db
        )
        assert res2["intent"] == IntentType.OPPORTUNITY_COMPARISON.value
        assert "earliest deadline" in res2["response"].lower() or "deadline" in res2["response"].lower()
        assert len(res2["response"]) > 50


def test_memory_4_pending_question_contextual_resolution():
    """Test 4: Assistant asks Kenya or abroad, student replies 'Both';
    system records preference and resolves pending question.
    """
    orchestrator = AgentOrchestrator()
    conv_id = f"test-pending-{uuid.uuid4().hex[:8]}"

    with SessionLocal() as db:
        conv = get_or_create_conversation(db, conv_id)
        state = load_conversation_state(db, conv)
        state.pending_question = {
            "question": "Are you looking for opportunities in Kenya or abroad?",
            "topic": "clarify_destination",
            "context": {"target_category": "scholarship"}
        }
        save_conversation_state(db, conv, state)

        res = orchestrator.process_turn(
            message="Both",
            conversation_id=conv_id,
            db=db
        )
        assert res["state"]["pending_question"] is None
        assert res["state"]["student_memory"].get("destination") == "both"
        assert res["intent"] in [IntentType.SCHOLARSHIP_SEARCH.value, IntentType.OPPORTUNITY_DISCOVERY.value]


def test_memory_5_conversation_isolation_between_users():
    """Test 5: Two different users have separate conversations;
    neither can access the other's messages via API (HTTP 403).
    """
    user1_email = f"u1_{uuid.uuid4().hex[:8]}@uonbi.ac.ke"
    r1 = client.post("/api/v1/auth/register", json={
        "email": user1_email,
        "password": "Password123!",
        "full_name": "User One",
        "role": "student"
    })
    token1 = r1.json()["access_token"]

    chat1 = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token1}"},
        json={"message": "Show me engineering scholarships"}
    )
    assert chat1.status_code == 200
    conv1_id = chat1.json()["conversation_id"]

    user2_email = f"u2_{uuid.uuid4().hex[:8]}@ku.ac.ke"
    r2 = client.post("/api/v1/auth/register", json={
        "email": user2_email,
        "password": "Password123!",
        "full_name": "User Two",
        "role": "student"
    })
    token2 = r2.json()["access_token"]

    access_attempt = client.get(
        f"/api/v1/conversations/{conv1_id}",
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert access_attempt.status_code == 403
    assert "Cannot access another user's conversation" in access_attempt.json()["detail"]


def test_memory_6_state_and_message_persistence():
    """Test 6: Reload conversation messages from DB using conversation_id;
    verifies messages, summary, and state persist across reloads.
    """
    resp1 = client.post("/api/v1/chat", json={
        "message": "Hello, I am a 2nd year student at Kenyatta University"
    })
    assert resp1.status_code == 200
    conv_id = resp1.json()["conversation_id"]
    assert conv_id is not None

    resp2 = client.post("/api/v1/chat", json={
        "message": "Find internships in tech",
        "conversation_id": conv_id
    })
    assert resp2.status_code == 200

    hist_resp = client.get(f"/api/v1/conversations/{conv_id}")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()

    assert hist_data["id"] == conv_id
    assert len(hist_data["messages"]) >= 4
    assert hist_data["state"]["student_profile"].get("year_of_study") == 2
    assert "Kenyatta University" in hist_data["state"]["student_profile"].get("university", "")
    assert hist_data["summary"] is not None


def test_memory_7_conversation_deletion():
    """Test 7: Delete conversation via DELETE /api/v1/conversations/{id};
    verifies record and messages are removed from database.
    """
    init_resp = client.post("/api/v1/chat", json={
        "message": "Hello there"
    })
    assert init_resp.status_code == 200
    conv_id = init_resp.json()["conversation_id"]

    check_resp = client.get(f"/api/v1/conversations/{conv_id}")
    assert check_resp.status_code == 200

    del_resp = client.delete(f"/api/v1/conversations/{conv_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"

    after_del = client.get(f"/api/v1/conversations/{conv_id}")
    assert after_del.status_code == 404
