"""
Tests for Application Secret Hardening and Production Safety.
Verifies that:
1. Production environment strictly rejects development fallback secrets.
2. Production environment strictly enforces minimum secret lengths (32 chars for SECRET_KEY, 16 chars for ADMIN_REGISTRATION_SECRET).
3. Production environment allows valid, high-entropy secrets.
4. Local development mode continues to work with documented development defaults.
5. Secrets are never exposed in API endpoints or system status.
"""

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import app

client = TestClient(app)

def test_development_allows_defaults():
    """Development environment must permit documented local development defaults."""
    s = Settings(APP_ENV="development")
    assert s.APP_ENV == "development"
    assert s.SECRET_KEY is not None

def test_production_rejects_default_secret_key():
    """Production mode must immediately fail startup if default SECRET_KEY is used."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            APP_ENV="production",
            SECRET_KEY="super_secret_development_key_not_for_production_32chars",
            ADMIN_REGISTRATION_SECRET="a_strong_prod_admin_secret_12345"
        )
    assert "SECRET_KEY must be set to a dedicated, cryptographically secure value" in str(exc.value)

def test_production_rejects_short_secret_key():
    """Production mode must reject SECRET_KEY with length < 32 characters."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            APP_ENV="production",
            SECRET_KEY="too_short_key",
            ADMIN_REGISTRATION_SECRET="a_strong_prod_admin_secret_12345"
        )
    assert "at least 32 characters" in str(exc.value)

def test_production_rejects_default_admin_secret():
    """Production mode must reject default or placeholder ADMIN_REGISTRATION_SECRET."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            APP_ENV="production",
            SECRET_KEY="a_cryptographically_secure_random_key_of_32_plus_chars",
            ADMIN_REGISTRATION_SECRET="kenya_admin_secret_key_2026"
        )
    assert "ADMIN_REGISTRATION_SECRET must be set to a dedicated secure secret" in str(exc.value)

def test_production_rejects_short_admin_secret():
    """Production mode must reject ADMIN_REGISTRATION_SECRET < 16 characters."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            APP_ENV="production",
            SECRET_KEY="a_cryptographically_secure_random_key_of_32_plus_chars",
            ADMIN_REGISTRATION_SECRET="short_secret"
        )
    assert "at least 16 characters" in str(exc.value)

def test_production_accepts_strong_secrets():
    """Production mode succeeds when compliant, high-entropy secrets and explicit origins are provided."""
    s = Settings(
        APP_ENV="production",
        SECRET_KEY="c84f9a12b67d890e1234567890abcdef1234567890abcdef1234567890abcdef",
        ADMIN_REGISTRATION_SECRET="kenya_admin_secure_token_9999_prod",
        ALLOWED_ORIGINS="https://opportunity-intelligence-ai.vercel.app",
        DATABASE_URL="postgresql+psycopg2://mock_user:mock_pw@localhost:5432/mock_db"
    )
    assert s.APP_ENV == "production"

def test_production_rejects_empty_or_missing_allowed_origins():
    """Production mode must reject missing or empty ALLOWED_ORIGINS (fail-closed)."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            APP_ENV="production",
            SECRET_KEY="c84f9a12b67d890e1234567890abcdef1234567890abcdef1234567890abcdef",
            ADMIN_REGISTRATION_SECRET="kenya_admin_secure_token_9999_prod",
            ALLOWED_ORIGINS=""
        )
    assert "ALLOWED_ORIGINS must be explicitly configured" in str(exc.value)

def test_production_rejects_wildcard_allowed_origins():
    """Production mode must reject wildcard origin '*' when credentials are enabled."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            APP_ENV="production",
            SECRET_KEY="c84f9a12b67d890e1234567890abcdef1234567890abcdef1234567890abcdef",
            ADMIN_REGISTRATION_SECRET="kenya_admin_secure_token_9999_prod",
            ALLOWED_ORIGINS="*"
        )
    assert "Wildcard origin '*' is strictly prohibited in production" in str(exc.value)

def test_cors_preview_regex_validation():
    import re
    from app.main import PREVIEW_ORIGIN_REGEX

    pattern = re.compile(PREVIEW_ORIGIN_REGEX)

    domains = {
        "production": "https://opportunity-intelligence-ai.vercel.app",
        "preview": "https://opportunity-intelligence-ai-git-feature.vercel.app",
        "unrelated": "https://unrelated-project.vercel.app",
        "attacker": "https://opportunity-intelligence-ai.vercel.app.attacker.com",
    }

    expected = {
        "production": True,
        "preview": True,
        "unrelated": False,
        "attacker": False,
    }

    for name, domain in domains.items():
        result = pattern.fullmatch(domain) is not None
        assert result == expected[name], (
            f"Failed domain match: {name}, domain={domain}, result={result}"
        )

def test_secrets_never_exposed_in_api_responses():
    """System and health endpoints must not leak secret values."""
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    root_text = root_resp.text.lower()
    assert "secret" not in root_text

    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    health_text = health_resp.text.lower()
    assert "secret" not in health_text
