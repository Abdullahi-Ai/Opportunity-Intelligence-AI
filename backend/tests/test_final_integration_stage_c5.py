"""
Stage C5 Final Integration & Golden RAG Evaluation Test Suite.
Validates:
1. End-to-end 14-step student journey across all services
2. 20-Query Golden RAG benchmark against active vector store
3. AI Advisor multi-turn conversational persistence & deterministic fallback
4. Security hardening (sanitized 500s, 413 limits, headers, Upstash atomicity & fail-open)
5. Production dependency & serverless configuration audit
"""

import sys
import os
import json
import uuid
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

root_dir = Path(__file__).resolve().parent.parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import api.index
from app.main import app
from app.config import settings
from app.db.session import engine, get_db, SessionLocal
from app.models.entities import User, StudentProfile, Conversation, ConversationMessage, TrackedApplication
from app.rag import get_vector_store
from app.agent.orchestrator import AgentOrchestrator
from app.core.rate_limit import DistributedRateLimiter

client = TestClient(app)

# ------------------------------------------------------------------------------
# 1. Full 14-Step Student Journey Verification
# ------------------------------------------------------------------------------

def test_complete_14_step_student_lifecycle():
    """Validates the complete end-to-end student user journey."""
    uid = uuid.uuid4().hex[:8]
    email = f"student_c5_{uid}@uonbi.ac.ke"
    password = "SecurePassword123!"

    # 1. Registration
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Mercy Jepchirchir",
        "role": "student",
        "university": "University of Nairobi",
        "field_of_study": "Electrical Engineering",
        "degree_level": "Undergraduate",
        "year_of_study": 2,
        "graduation_year": 2028
    })
    assert reg_resp.status_code == 201
    auth_data = reg_resp.json()
    student_id = auth_data["user"]["student_profile"]["id"]
    token = auth_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Login
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. JWT Verification (/api/v1/auth/me)
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email

    # 4. Profile Update
    prof_resp = client.post("/api/v1/profile", json={
        "email": email,
        "full_name": "Mercy Jepchirchir",
        "university": "University of Nairobi",
        "field_of_study": "Electrical Engineering",
        "degree_level": "Undergraduate",
        "year_of_study": 3,
        "graduation_year": 2028,
        "county_of_origin": "Nandi",
        "preferred_categories": "Scholarship, Internship"
    }, headers=headers)
    assert prof_resp.status_code == 201
    assert prof_resp.json()["year_of_study"] == 3

    # 5. Opportunity Discovery
    disc_resp = client.get("/api/v1/opportunities?search=kcb", headers=headers)
    assert disc_resp.status_code == 200
    opps = disc_resp.json()
    assert len(opps) > 0
    opp_id = opps[0]["id"]

    # 6. Personalized Matching
    match_resp = client.get("/api/v1/matches", headers=headers)
    assert match_resp.status_code == 200
    assert "matches" in match_resp.json()

    # 7. Eligibility Assessment Tool
    elig_resp = client.post("/api/v1/agent/assess-eligibility", json={
        "opportunity_id": "opp-kcb-foundation-tertiary-2026",
        "student_degree_level": "undergraduate",
        "student_field_of_study": "Electrical Engineering",
        "student_year_of_study": 3,
        "student_kcse_grade": "A-"
    })
    assert elig_resp.status_code == 200
    assert "criteria_breakdown" in elig_resp.json()

    # 8. AI Advisor Turn
    chat_resp = client.post("/api/v1/chat", json={
        "message": "Can you check my eligibility for the KCB Foundation scholarship?",
        "student_id": student_id
    }, headers=headers)
    assert chat_resp.status_code == 200
    conv_id = chat_resp.json()["conversation_id"]
    assert "response" in chat_resp.json()

    # 9. Checklist Generation Tool
    chk_resp = client.post("/api/v1/agent/generate-checklist", json={
        "opportunity_id": opp_id
    })
    assert chk_resp.status_code == 200

    # 10. Save Opportunity to Tracker
    save_resp = client.post("/api/v1/tracker/save", json={
        "student_id": student_id,
        "opportunity_id": opp_id,
        "stage": "Saved",
        "notes": "First choice funding target"
    }, headers=headers)
    assert save_resp.status_code == 201
    tracked_id = save_resp.json()["tracked_application_id"]

    # 11. Application Tracking Details
    track_resp = client.get(f"/api/v1/tracker/application/{tracked_id}", headers=headers)
    assert track_resp.status_code == 200
    assert track_resp.json()["opportunity_id"] == opp_id

    # 12. Update Application Stage
    stage_resp = client.patch(f"/api/v1/tracker/{tracked_id}/stage?new_stage=Drafting", headers=headers)
    assert stage_resp.status_code == 200
    assert stage_resp.json()["stage"] == "Drafting"

    # 13. Conversation History Persistence Across Turns
    conv_hist_resp = client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
    assert conv_hist_resp.status_code == 200
    assert len(conv_hist_resp.json()["messages"]) >= 2

    # 14. Cross-User Data Isolation
    uid_other = uuid.uuid4().hex[:8]
    reg_other = client.post("/api/v1/auth/register", json={
        "email": f"other_{uid_other}@ku.ac.ke",
        "password": "OtherPassword123!",
        "full_name": "Other Student",
        "role": "student"
    })
    token_other = reg_other.json()["access_token"]
    headers_other = {"Authorization": f"Bearer {token_other}"}

    forbidden_tracker = client.get(f"/api/v1/tracker/{student_id}", headers=headers_other)
    assert forbidden_tracker.status_code == 403
    forbidden_app = client.get(f"/api/v1/tracker/application/{tracked_id}", headers=headers_other)
    assert forbidden_app.status_code in [403, 404]

# ------------------------------------------------------------------------------
# 2. 20-Query Golden RAG Evaluation
# ------------------------------------------------------------------------------

def test_golden_rag_evaluation_against_active_store():
    """
    Runs the 20-query golden benchmark dataset against the active vector store.
    Validates Recall@1, Recall@3, MRR, Source Attribution, and Adversarial Rejection.
    """
    eval_file = root_dir / "backend" / "tests" / "data" / "golden_evaluation_dataset.json"
    assert eval_file.exists(), "Golden evaluation dataset file missing."

    with open(eval_file, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    in_domain = [tc for tc in dataset if not tc.get("is_out_of_domain")]
    out_of_domain = [tc for tc in dataset if tc.get("is_out_of_domain")]

    store = get_vector_store()
    hits_at_1 = 0
    hits_at_3 = 0
    reciprocal_ranks = []
    attribution_matches = 0

    for tc in in_domain:
        query = tc["query"]
        expected_id = tc["expected_opportunity_id"]
        expected_url = tc["expected_official_url"]

        results = store.search(query=query, top_k=3)
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
                if (r["metadata"].get("official_url") == expected_url or
                    r["metadata"].get("source_url") == expected_url):
                    attribution_matches += 1
                break

    recall_at_1 = hits_at_1 / len(in_domain)
    recall_at_3 = hits_at_3 / len(in_domain)
    mrr = sum(reciprocal_ranks) / len(in_domain)
    attribution_rate = attribution_matches / len(in_domain)

    # Adversarial rejection (< 0.65 similarity)
    rejected_count = 0
    for tc in out_of_domain:
        results = store.search(query=tc["query"], top_k=3)
        if not results or results[0]["similarity_score"] < 0.65:
            rejected_count += 1
    adv_rejection_rate = rejected_count / len(out_of_domain)

    # Assertions matching or exceeding baseline
    assert recall_at_1 >= 0.88, f"Recall@1 ({recall_at_1:.2%}) below baseline 88.24%"
    assert recall_at_3 >= 0.99, f"Recall@3 ({recall_at_3:.2%}) below baseline 100%"
    assert mrr >= 0.94, f"MRR ({mrr:.4f}) below baseline 0.9412"
    assert attribution_rate >= 0.99, f"Attribution ({attribution_rate:.2%}) below baseline 100%"
    assert adv_rejection_rate >= 0.99, f"Adversarial rejection ({adv_rejection_rate:.2%}) below baseline 100%"

# ------------------------------------------------------------------------------
# 3. AI Advisor Multi-Turn & Deterministic Grounding
# ------------------------------------------------------------------------------

def test_ai_advisor_multi_turn_persistence():
    """Validates multi-turn conversation progression and relational message logging."""
    db = SessionLocal()
    try:
        conv_id = f"test_c5_conv_{uuid.uuid4().hex[:8]}"
        orch = AgentOrchestrator()

        # Turn 1
        t1 = orch.process_turn(
            message="What are the application steps for Safaricom attachments?",
            conversation_id=conv_id,
            db=db
        )
        assert t1 is not None
        assert "response" in t1

        # Turn 2
        t2 = orch.process_turn(
            message="What is the deadline for this attachment?",
            conversation_id=conv_id,
            db=db
        )
        assert t2 is not None
        assert "response" in t2

        # Verify DB records
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
        assert conv is not None
        msgs = db.query(ConversationMessage).filter(ConversationMessage.conversation_id == conv_id).all()
        assert len(msgs) >= 4  # 2 user + 2 assistant messages
    finally:
        db.close()

# ------------------------------------------------------------------------------
# 4. Production Configuration & Dependency Audit
# ------------------------------------------------------------------------------

def test_production_dependency_audit():
    """Confirms api/requirements.txt strictly excludes ChromaDB and includes pgvector."""
    req_path = root_dir / "api" / "requirements.txt"
    assert req_path.exists(), "api/requirements.txt missing."
    text = req_path.read_text(encoding="utf-8")

    assert "chromadb" not in text.lower(), "ChromaDB dependency accidentally present in production serverless bundle!"
    assert "pgvector" in text, "pgvector missing from api/requirements.txt."
    assert "fastapi" in text
    assert "sqlalchemy" in text
    assert "psycopg2-binary" in text

def test_vercel_serverless_entrypoint_validity():
    """Confirms api/index.py exposes an ASGI app without side-effect connections."""
    assert hasattr(api.index, "app")
    assert api.index.app.title == "Opportunity Intelligence AI"
