"""
Unit tests for database URL normalization and Psycopg 2 dialect resolution.
Guarantees robust driver resolution across PostgreSQL connection string variations
without connecting to any live remote database.
"""

import pytest
from sqlalchemy.engine import make_url
from app.db.session import normalize_database_url


def test_postgres_scheme_conversion():
    raw_url = "postgres://neonuser:mypassword@ep-sample-12345.us-east-2.aws.neon.tech/neondb"
    normalized = normalize_database_url(raw_url)
    assert normalized.startswith("postgresql+psycopg2://")
    assert normalized == "postgresql+psycopg2://neonuser:mypassword@ep-sample-12345.us-east-2.aws.neon.tech/neondb"


def test_postgresql_scheme_conversion():
    raw_url = "postgresql://neonuser:mypassword@ep-sample-12345.us-east-2.aws.neon.tech/neondb"
    normalized = normalize_database_url(raw_url)
    assert normalized.startswith("postgresql+psycopg2://")
    assert normalized == "postgresql+psycopg2://neonuser:mypassword@ep-sample-12345.us-east-2.aws.neon.tech/neondb"


def test_postgresql_psycopg_scheme_conversion():
    raw_url = "postgresql+psycopg://neonuser:mypassword@ep-sample-12345.us-east-2.aws.neon.tech/neondb"
    normalized = normalize_database_url(raw_url)
    assert normalized.startswith("postgresql+psycopg2://")
    assert normalized == "postgresql+psycopg2://neonuser:mypassword@ep-sample-12345.us-east-2.aws.neon.tech/neondb"


def test_postgresql_psycopg2_scheme_preservation():
    raw_url = "postgresql+psycopg2://neonuser:mypassword@ep-sample-12345.us-east-2.aws.neon.tech/neondb"
    normalized = normalize_database_url(raw_url)
    assert normalized == raw_url


def test_sqlite_url_preservation():
    sqlite_absolute = "sqlite:////tmp/isolated_test.db"
    sqlite_relative = "sqlite:///./data/app.db"
    sqlite_memory = "sqlite:///:memory:"

    assert normalize_database_url(sqlite_absolute) == sqlite_absolute
    assert normalize_database_url(sqlite_relative) == sqlite_relative
    assert normalize_database_url(sqlite_memory) == sqlite_memory


def test_query_parameters_preservation():
    raw_url = (
        "postgresql+psycopg://neonuser:secret@ep-sample.neon.tech/neondb"
        "?sslmode=require&connect_timeout=10&application_name=opp_intel"
    )
    normalized = normalize_database_url(raw_url)
    expected = (
        "postgresql+psycopg2://neonuser:secret@ep-sample.neon.tech/neondb"
        "?sslmode=require&connect_timeout=10&application_name=opp_intel"
    )
    assert normalized == expected
    parsed = make_url(normalized)
    assert parsed.query.get("sslmode") == "require"
    assert parsed.query.get("connect_timeout") == "10"
    assert parsed.query.get("application_name") == "opp_intel"


def test_special_characters_in_credentials():
    raw_url = (
        "postgresql+psycopg://user%40example.com:p%40ss%23word%2B123@ep-sample.neon.tech/neondb"
    )
    normalized = normalize_database_url(raw_url)
    expected = (
        "postgresql+psycopg2://user%40example.com:p%40ss%23word%2B123@ep-sample.neon.tech/neondb"
    )
    assert normalized == expected
    parsed = make_url(normalized)
    assert parsed.username == "user@example.com"
    assert parsed.password == "p@ss#word+123"


def test_normalization_idempotency():
    inputs = [
        "postgres://usr:pwd@host:5432/db?sslmode=require",
        "postgresql://usr:pwd@host:5432/db?sslmode=require",
        "postgresql+psycopg://usr:pwd@host:5432/db?sslmode=require",
        "postgresql+psycopg2://usr:pwd@host:5432/db?sslmode=require",
        "sqlite:////tmp/test.db",
    ]
    for raw in inputs:
        first_pass = normalize_database_url(raw)
        second_pass = normalize_database_url(first_pass)
        assert first_pass == second_pass


def test_sqlalchemy_dialect_resolution_to_psycopg2():
    inputs = [
        "postgres://u:p@localhost:5432/testdb",
        "postgresql://u:p@localhost:5432/testdb",
        "postgresql+psycopg://u:p@localhost:5432/testdb",
        "postgresql+psycopg2://u:p@localhost:5432/testdb",
    ]
    for raw in inputs:
        normalized = normalize_database_url(raw)
        url_obj = make_url(normalized)
        dialect_cls = url_obj.get_dialect()
        # Verify it resolves to psycopg2 driver, avoiding 'psycopg' module import
        assert dialect_cls.driver == "psycopg2"
        assert dialect_cls.name == "postgresql"
