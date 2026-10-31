import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.rate_limit import rate_limiter, limiter_auth
from app.config import settings

client = TestClient(app)

def test_rate_limiting_enforcement_on_auth():
    fresh_key = f"auth:test_unit_{uuid.uuid4().hex[:6]}"
    rate_limiter.check_rate_limit(key=fresh_key, max_requests=2, window_seconds=60)
    rate_limiter.check_rate_limit(key=fresh_key, max_requests=2, window_seconds=60)
    with pytest.raises(Exception) as exc_info:
        rate_limiter.check_rate_limit(key=fresh_key, max_requests=2, window_seconds=60)
    assert "Rate limit exceeded" in str(exc_info.value)
    assert exc_info.value.status_code == 429

def test_rate_limiter_reset():
    rate_limiter.reset()
    key = "test_key_1"
    rate_limiter.check_rate_limit(key=key, max_requests=2, window_seconds=60)
    rate_limiter.check_rate_limit(key=key, max_requests=2, window_seconds=60)
    with pytest.raises(Exception):
        rate_limiter.check_rate_limit(key=key, max_requests=2, window_seconds=60)
    rate_limiter.reset()
    rate_limiter.check_rate_limit(key=key, max_requests=2, window_seconds=60)
