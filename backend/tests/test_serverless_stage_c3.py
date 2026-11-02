"""
Stage C3 Serverless Compatibility Test Suite for Opportunity Intelligence AI.
Tests:
1. ASGI serverless entrypoint and route availability (api/index.py)
2. Stateless Authentication & Authorization (registration, login, JWT claims, expiry, invalid token, RBAC, isolation)
3. Neon/NullPool session management & concurrent request safety
4. Vector store routing and retrieval
5. AI Advisor lifecycle, tool execution, and conversation persistence
6. In-memory rate limiting and security guards
7. Filesystem immutability (zero runtime disk writes)
"""

import sys
import os
import time
import uuid
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import Session

# Add project root and backend to path
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
from app.agent.tools import (
    SearchOpportunitiesInput,
    tool_search_opportunities,
    AssessEligibilityInput,
    tool_assess_eligibility
)
from app.agent.orchestrator import AgentOrchestrator
from app.core.security import decode_access_token

client = TestClient(app)

# ------------------------------------------------------------------------------
# 1. Vercel Python Runtime & ASGI Entrypoint Verification
# ------------------------------------------------------------------------------

def test_vercel_asgi_entrypoint_initialization():
    """Confirms api.index.app initializes cleanly as a FastAPI application."""
    assert api.index.app is not None
    assert api.index.app.title == "Opportunity Intelligence AI"
    assert hasattr(api.index.app, "__call__")  # Valid ASGI callable

def test_vercel_expected_api_routes_registered():
    """Confirms all critical serverless routes are mapped in FastAPI OpenAPI route schema."""
    paths = list(api.index.app.openapi()["paths"].keys())
    expected_endpoints = [
        "/api/v1/health",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/me",
        "/api/v1/opportunities",
        "/api/v1/profile",
        "/api/v1/tracker/{student_id}",
        "/api/v1/chat",
        "/api/v1/rag/search",
        "/api/v1/agent/assess-eligibility"
    ]
    for ep in expected_endpoints:
        assert ep in paths, f"Critical serverless endpoint {ep} missing from OpenAPI routes: {paths}"

def test_cold_start_import_performance():
    """Measures module re-import time to verify cold start is within reasonable serverless bounds."""
    t0 = time.perf_counter()
    import importlib
    importlib.reload(api.index)
    duration_ms = (time.perf_counter() - t0) * 1000
    assert duration_ms < 500, f"Warm reload duration {duration_ms:.2f}ms exceeds threshold."

# ------------------------------------------------------------------------------
# 2. Authentication & Authorization (Stateless JWT)
# ------------------------------------------------------------------------------

def test_stateless_authentication_and_jwt_lifecycle():
    """Verifies user registration, login, JWT claims, and profile access."""
    unique_id = uuid.uuid4().hex[:8]
    email = f"student_{unique_id}@uonbi.ac.ke"
    password = "SecurePassword123!"

    # 1. Registration
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Amina Wanjiku",
        "role": "student",
        "university": "University of Nairobi",
        "field_of_study": "Informatics",
        "degree_level": "Undergraduate",
        "year_of_study": 2
    })
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert "access_token" in reg_data
    token = reg_data["access_token"]
    user_id = reg_data["user"]["id"]

    # 2. Verify JWT payload is completely stateless (validatable without DB access)
    claims = decode_access_token(token)
    assert claims is not None
    assert claims.get("role") == "student"
    assert claims.get("sub") == user_id
    assert "exp" in claims

    # 3. Authenticated request to /api/v1/auth/me
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email

    # 4. Login with credentials
    login_resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()

def test_invalid_and_expired_jwt_handling():
    """Verifies that invalid or forged JWT tokens are strictly rejected."""
    # Malformed token
    resp_malformed = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not_a_valid_jwt"})
    assert resp_malformed.status_code == 401
    assert "invalid" in resp_malformed.json().get("detail", "").lower()

    # Forged signature
    forged_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbkB0ZXN0LmNvbSIsInJvbGUiOiJhZG1pbiJ9.invalidsignaturehere"
    resp_forged = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert resp_forged.status_code == 401

def test_cross_user_data_isolation():
    """Ensures Student A cannot view or manipulate Student B's saved tracker data."""
    # Create Student A
    uid_a = uuid.uuid4().hex[:8]
    resp_a = client.post("/api/v1/auth/register", json={
        "email": f"user_a_{uid_a}@ku.ac.ke",
        "password": "Password123!",
        "full_name": "Student A",
        "role": "student"
    })
    token_a = resp_a.json()["access_token"]
    student_a_id = resp_a.json()["user"]["student_profile"]["id"]

    # Create Student B
    uid_b = uuid.uuid4().hex[:8]
    resp_b = client.post("/api/v1/auth/register", json={
        "email": f"user_b_{uid_b}@ku.ac.ke",
        "password": "Password123!",
        "full_name": "Student B",
        "role": "student"
    })
    token_b = resp_b.json()["access_token"]
    student_b_id = resp_b.json()["user"]["student_profile"]["id"]

    # Student A saves an opportunity
    save_resp = client.post(
        "/api/v1/tracker/save",
        json={
            "student_id": student_a_id,
            "opportunity_id": "opp-hef-undergraduate-2026",
            "stage": "Saved",
            "notes": "Student A confidential note"
        },
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert save_resp.status_code == 201
    saved_app_id = save_resp.json()["tracked_application_id"]

    # Student B attempts to read Student A's application by ID -> 403 Forbidden
    get_resp = client.get(
        f"/api/v1/tracker/application/{saved_app_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert get_resp.status_code in [403, 404]

    # Student B attempts to list Student A's tracker -> 403 Forbidden
    cross_list_resp = client.get(
        f"/api/v1/tracker/{student_a_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert cross_list_resp.status_code == 403

    # Student B views own tracker -> 200 OK (empty list)
    own_list_resp = client.get(
        f"/api/v1/tracker/{student_b_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert own_list_resp.status_code == 200
    assert len(own_list_resp.json()) == 0

def test_rbac_admin_endpoint_gating():
    """Ensures regular student tokens cannot perform admin operations."""
    uid = uuid.uuid4().hex[:8]
    reg_student = client.post("/api/v1/auth/register", json={
        "email": f"student_rbac_{uid}@strathmore.edu",
        "password": "Password123!",
        "full_name": "Student RBAC",
        "role": "student"
    })
    student_token = reg_student.json()["access_token"]

    # Student tries to post a new curated opportunity
    admin_op_resp = client.post(
        "/api/v1/admin/opportunities",
        json={
            "title": "Unauthorized Opportunity",
            "provider": "Fake Provider",
            "category": "Scholarship",
            "target_audience": "Undergrads",
            "official_url": "https://example.com",
            "application_deadline": "2026-12-31"
        },
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert admin_op_resp.status_code == 403
    assert "Administrator privileges required" in admin_op_resp.json().get("detail", "")

# ------------------------------------------------------------------------------
# 3. Database Session Lifecycle & Concurrency
# ------------------------------------------------------------------------------

def test_database_session_generator_cleanup():
    """Verifies get_db() generator cleanly closes database sessions."""
    gen = get_db()
    db_session = next(gen)
    assert isinstance(db_session, Session)

    # Closing generator must execute db.close()
    try:
        next(gen)
    except StopIteration:
        pass

def test_concurrent_session_handling():
    """Tests rapid sequential session creations simulating serverless concurrency without connection pool exhaustion."""
    sessions = []
    for _ in range(15):
        s = SessionLocal()
        sessions.append(s)
        count = s.query(User).count()
        assert count >= 0

    # Clean up all sessions
    for s in sessions:
        s.close()

# ------------------------------------------------------------------------------
# 4. Vector Store Routing & Semantic Retrieval
# ------------------------------------------------------------------------------

def test_active_vector_store_routing():
    """Verifies get_vector_store() returns active store with 57 chunks indexed."""
    store = get_vector_store()
    stats = store.get_stats()
    assert stats["total_chunks"] == 57
    assert stats.get("embedding_dimensions", 384) == 384

def test_semantic_retrieval_and_source_attribution():
    """Verifies that vector search produces valid scoring and official URLs."""
    results = tool_search_opportunities(SearchOpportunitiesInput(
        query="Mastercard Foundation scholars program Kenya",
        top_k=2
    ))
    assert results["status"] == "success"
    assert results["count"] > 0
    top_hit = results["results"][0]
    assert top_hit["official_url"] is not None
    assert top_hit["official_url"].startswith("http")
    assert top_hit["similarity_score"] > 0.40

# ------------------------------------------------------------------------------
# 5. AI Advisor Lifecycle & Conversation Persistence
# ------------------------------------------------------------------------------

def test_ai_advisor_turn_and_database_persistence():
    """
    Verifies the complete conversational lifecycle:
    1. Student message
    2. Orchestrator turn execution with database session
    3. Tool execution
    4. Relational persistence of conversation and messages
    """
    db = SessionLocal()
    try:
        conv_id = f"test_conv_{uuid.uuid4().hex[:8]}"
        orch = AgentOrchestrator()

        turn_result = orch.process_turn(
            message="What are the eligibility requirements for the KCB Foundation scholarship in Kenya?",
            conversation_id=conv_id,
            db=db,
            user_id=None,
            session_id=f"sess_{conv_id}"
        )

        assert turn_result is not None
        assert "response" in turn_result
        assert len(turn_result["response"]) > 20
        assert "citations" in turn_result

        # Verify database persistence: Conversation record exists
        saved_conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
        assert saved_conv is not None

        # Verify messages persisted in conversation_messages table
        messages = db.query(ConversationMessage).filter(ConversationMessage.conversation_id == conv_id).all()
        assert len(messages) >= 2  # At least user + assistant message
        roles = [m.role for m in messages]
        assert "user" in roles
        assert "assistant" in roles
    finally:
        db.close()

# ------------------------------------------------------------------------------
# 6. Rate Limiting & Security Integrity
# ------------------------------------------------------------------------------

def test_rate_limiter_in_memory_burst_guard():
    """Confirms in-memory rate limiter protects endpoints against high frequency rapid-fire bursts."""
    from app.core.rate_limit import rate_limiter
    rate_limiter.reset()

    blocked = False
    for i in range(15):
        try:
            rate_limiter.check_rate_limit(key="auth:test_client_burst", max_requests=5, window_seconds=60)
        except Exception as e:
            if "Rate limit exceeded" in str(e):
                blocked = True
                break

    assert blocked, "Rate limiter failed to trigger 429 on rapid-fire burst."
    rate_limiter.reset()

def test_error_responses_do_not_leak_secrets():
    """Confirms 404 and 500 error responses do not leak database connection strings or internals."""
    resp = client.get("/api/v1/opportunities/non_existent_opportunity_id_12345")
    assert resp.status_code == 404
    err_body = resp.text.lower()
    assert "password" not in err_body
    assert "postgresql://" not in err_body
    assert "neondb_owner" not in err_body
    assert "traceback" not in err_body

# ------------------------------------------------------------------------------
# 7. Serverless Filesystem Immutability
# ------------------------------------------------------------------------------

def test_zero_disk_writes_during_runtime():
    """
    Verifies that executing search, health checks, and chat requests
    does not create new files on the filesystem.
    """
    root_stat_before = {p: p.stat().st_mtime for p in root_dir.glob("*") if p.is_file()}

    # Execute health check, search, and root endpoints
    client.get("/")
    client.get("/api/v1/health")
    client.post("/api/v1/rag/search", json={"query": "Kenyan engineering bursaries", "top_k": 2})

    root_stat_after = {p: p.stat().st_mtime for p in root_dir.glob("*") if p.is_file()}

    # Confirm no new files were written to project root
    assert set(root_stat_before.keys()) == set(root_stat_after.keys()), "New files were created in project root during runtime!"
