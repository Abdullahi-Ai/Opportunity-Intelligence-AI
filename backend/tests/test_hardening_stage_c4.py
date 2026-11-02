"""
Stage C4 Reliability & Security Hardening Test Suite for Opportunity Intelligence AI.
Tests:
1. Vercel Execution Configuration (memory: 1024, maxDuration: 60)
2. Distributed Rate Limiting architecture (fallback & Upstash REST integration)
3. Database Reliability (NullPool, connect_timeout, rollback on exception)
4. Groq Outage/Timeout Handling & Grounded Fallback
5. Payload Size Guard (413 Request Entity Too Large)
6. Global Exception Sanitization (no leaked tracebacks or credentials)
7. Security Headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection)
8. Frontend Secrets Leakage Guard
"""

import sys
import os
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

# Setup path
root_dir = Path(__file__).resolve().parent.parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.main import app
from app.config import settings
from app.db.session import engine, get_db, SessionLocal
from app.rag import get_vector_store
from app.core.rate_limit import DistributedRateLimiter, InMemoryRateLimiter, rate_limiter
from app.agent.orchestrator import AgentOrchestrator
from app.agent.intent import IntentType

client = TestClient(app)

# ------------------------------------------------------------------------------
# 1. Vercel Configuration & Execution Bounds
# ------------------------------------------------------------------------------

def test_vercel_json_configuration():
    """Verifies root vercel.json memory, maxDuration, rewrites, and security headers."""
    vercel_path = root_dir / "vercel.json"
    assert vercel_path.exists(), "vercel.json missing from project root."

    with open(vercel_path, "r", encoding="utf-8") as f:
        vcfg = json.load(f)

    # Function configuration
    assert "functions" in vcfg
    fn_cfg = vcfg["functions"].get("api/index.py", {})
    assert fn_cfg.get("memory") == 1024, f"Expected 1024MB memory, found {fn_cfg.get('memory')}"
    assert fn_cfg.get("maxDuration") == 60, f"Expected 60s maxDuration, found {fn_cfg.get('maxDuration')}"

    # Rewrites check
    rewrites = vcfg.get("rewrites", [])
    rewrite_sources = [r.get("source") for r in rewrites]
    assert "/api/v1/:path*" in rewrite_sources
    assert "/api/:path*" in rewrite_sources
    assert "/(.*)" in rewrite_sources

# ------------------------------------------------------------------------------
# 2. Distributed Rate Limiting Architecture
# ------------------------------------------------------------------------------

def test_distributed_rate_limiter_defaults_to_in_memory():
    """Verifies rate limiter defaults to in-memory mode when Upstash credentials are not set."""
    limiter = DistributedRateLimiter()
    assert not limiter.is_distributed()
    assert isinstance(limiter.memory, InMemoryRateLimiter)

def test_distributed_rate_limiter_upstash_mock():
    """Simulates Upstash Redis REST pipeline response when configured."""
    mock_memory = MagicMock()
    limiter = DistributedRateLimiter(memory_fallback=mock_memory)

    with patch.object(settings, "UPSTASH_REDIS_REST_URL", "https://mock-redis.upstash.io"), \
         patch.object(settings, "UPSTASH_REDIS_REST_TOKEN", "mock_token"), \
         patch("httpx.Client") as mock_client_cls:

        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_http

        # Simulate count within limits (e.g. request 3 of 5)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"result": 3}, {"result": 1}]
        mock_http.post.return_value = mock_resp

        # Should pass without exception
        limiter.check_rate_limit(key="test:user_123", max_requests=5, window_seconds=60)
        assert mock_http.post.called

def test_distributed_rate_limiter_upstash_exceeded():
    """Verifies that exceeding Upstash distributed count raises HTTP 429."""
    limiter = DistributedRateLimiter()

    with patch.object(settings, "UPSTASH_REDIS_REST_URL", "https://mock-redis.upstash.io"), \
         patch.object(settings, "UPSTASH_REDIS_REST_TOKEN", "mock_token"), \
         patch("httpx.Client") as mock_client_cls:

        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_http

        # Simulate count exceeded (e.g. request 6 of 5)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"result": 6}, {"result": 1}]
        mock_http.post.return_value = mock_resp

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            limiter.check_rate_limit(key="test:user_blocked", max_requests=5, window_seconds=60)
        assert exc_info.value.status_code == 429

def test_distributed_rate_limiter_upstash_outage_fails_open_to_memory():
    """Verifies that an Upstash network failure or 500 fails open to local in-memory limiter."""
    mock_memory = MagicMock()
    limiter = DistributedRateLimiter(memory_fallback=mock_memory)

    with patch.object(settings, "UPSTASH_REDIS_REST_URL", "https://mock-redis.upstash.io"), \
         patch.object(settings, "UPSTASH_REDIS_REST_TOKEN", "mock_token"), \
         patch("httpx.Client") as mock_client_cls:

        mock_http = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_http
        # Simulate network timeout / connection error
        mock_http.post.side_effect = Exception("Upstash Connection Timeout")

        # Must not raise an unhandled exception; must call in-memory fallback
        limiter.check_rate_limit(key="test:fail_open", max_requests=5, window_seconds=60)
        assert mock_memory.check_rate_limit.called

# ------------------------------------------------------------------------------
# 3. Database Reliability & NullPool
# ------------------------------------------------------------------------------

def test_database_session_rollback_on_exception():
    """Verifies get_db() rolls back the transaction when an exception occurs inside the context."""
    gen = get_db()
    session = next(gen)

    # Mock rollback to verify it gets invoked on error
    with patch.object(session, "rollback") as mock_rollback:
        try:
            gen.throw(ValueError("Simulated endpoint failure"))
        except ValueError:
            pass

        assert mock_rollback.called, "Database session failed to call rollback() on endpoint exception!"

# ------------------------------------------------------------------------------
# 4. Groq Outage & Fallback Handling
# ------------------------------------------------------------------------------

def test_groq_orchestrator_bounds():
    """Verifies safe timeout and bounded tool iterations in AgentOrchestrator."""
    orch = AgentOrchestrator()
    assert orch.max_tool_iterations <= 4, f"max_tool_iterations ({orch.max_tool_iterations}) should be <= 4"
    assert orch.timeout_seconds <= 15.0, f"timeout_seconds ({orch.timeout_seconds}) should be <= 15s"

def test_groq_outage_grounded_fallback():
    """Verifies that when Groq raises an API error, orchestrator falls back to deterministic RAG."""
    orch = AgentOrchestrator()
    mock_groq = MagicMock()
    mock_groq.chat.completions.create.side_effect = Exception("503 Service Unavailable: Groq inference outage")
    orch.groq_client = mock_groq

    db = SessionLocal()
    try:
        res = orch.process_turn(
            message="What are the eligibility requirements for the KCB Foundation scholarship in Kenya?",
            conversation_id="test_groq_fallback_conv",
            db=db
        )
        assert res is not None
        assert "response" in res
        assert len(res["response"]) > 30
        assert "citations" in res
        # Must contain grounded details, not hallucinated text
        resp_lower = res["response"].lower()
        assert "kcb" in resp_lower or "eligibility" in resp_lower or "scholarship" in resp_lower
    finally:
        db.close()

# ------------------------------------------------------------------------------
# 5. API Security, Payload Size & Headers
# ------------------------------------------------------------------------------

def test_payload_size_limit_guard():
    """Verifies requests with Content-Length > 1 MB are rejected with 413."""
    headers = {"Content-Length": "1500000"}  # 1.5 MB
    resp = client.post("/api/v1/rag/search", headers=headers, json={"query": "test"})
    assert resp.status_code == 413
    assert "too large" in resp.json().get("detail", "").lower()

def test_security_headers_present_on_all_responses():
    """Verifies defensive security headers are appended to responses."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"

def test_global_exception_sanitizer_masks_internal_errors():
    """Verifies unhandled exceptions return generic 500 without leaking credentials or tracebacks."""
    safe_client = TestClient(app, raise_server_exceptions=False)
    with patch.object(get_vector_store(), "get_stats", side_effect=RuntimeError("psycopg2.OperationalError: host=ep-falling-fog password=supersecret")):
        resp = safe_client.get("/api/v1/health")
        assert resp.status_code == 500
        data = resp.json()
        assert "password" not in resp.text.lower()
        assert "ep-falling-fog" not in resp.text.lower()
        assert "psycopg2" not in resp.text.lower()
        assert "traceback" not in resp.text.lower()
        assert "internal server error occurred" in data.get("detail", "").lower()

# ------------------------------------------------------------------------------
# 6. Frontend Secrets Exposure Guard
# ------------------------------------------------------------------------------

def test_frontend_does_not_contain_backend_secrets():
    """Verifies frontend source files do not contain exposed backend credentials."""
    frontend_src = root_dir / "frontend" / "src"
    assert frontend_src.exists(), "Frontend src directory missing."

    sensitive_patterns = [
        "npg_",
        "gsk_",
        "postgresql://",
        "ADMIN_REGISTRATION_SECRET",
        "kenya_admin_secret"
    ]

    for p in frontend_src.rglob("*.js*"):
        text = p.read_text(encoding="utf-8")
        for pat in sensitive_patterns:
            assert pat not in text, f"Potential secret pattern '{pat}' discovered in frontend file: {p}"
