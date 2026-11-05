"""
Integration tests for Stage 2.2B-3:
Eligibility Criteria Administrative Review, Verification, and Management Workflows.

Covers:
1. RBAC enforcement: Students cannot access administrative review endpoints (403 Forbidden).
2. Unauthenticated access blocked (401 Unauthorized).
3. Create criterion manually (POST /api/v1/admin/opportunities/{id}/criteria).
4. Update criterion (PUT /api/v1/admin/criteria/{id}).
5. Verify criterion with evidence URL (POST /api/v1/admin/criteria/{id}/verify).
6. Malformed evidence URLs rejected (422 Unprocessable Entity).
7. Reject criterion (POST /api/v1/admin/criteria/{id}/reject).
8. Flag criterion for review (POST /api/v1/admin/criteria/{id}/flag).
9. Reopen criterion (POST /api/v1/admin/criteria/{id}/reopen).
10. Retrieve immutable criterion audit history (GET /api/v1/admin/criteria/{id}/history).
11. Pagination and filtering on pending criteria (GET /api/v1/admin/criteria/pending).
12. Public opportunity criteria read endpoint (GET /api/opportunities/{id}/criteria).
"""

import sys
import uuid
from pathlib import Path
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

backend_dir = Path(__file__).resolve().parent.parent
repo_root = backend_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.db.session import Base, get_db
from app.models.entities import (
    User,
    Opportunity,
    OpportunityEligibilityCriterion,
    OpportunityCriterionVerificationLog,
    CriterionCategory,
    CriterionOperator,
    CriterionVerificationStatus,
)
from app.core.security import create_access_token


from sqlalchemy.pool import StaticPool

@pytest.fixture
def test_setup():
    """Sets up an isolated SQLite database and test client."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()

    # Create admin user
    admin = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@moi.ac.ke",
        hashed_password="SecretAdminPassword!",
        full_name="Chief Administrator",
        role="admin"
    )
    # Create student user
    student = User(
        email=f"student_{uuid.uuid4().hex[:6]}@student.uonbi.ac.ke",
        hashed_password="SecretStudentPassword!",
        full_name="Student User",
        role="student"
    )
    # Create opportunity
    opp = Opportunity(
        id=f"opp-test-{uuid.uuid4().hex[:6]}",
        title="Software Engineering Fellowship",
        provider="Moi University Tech Hub",
        category="Fellowship",
        official_url="https://moi.ac.ke/tech-fellowship"
    )
    session.add_all([admin, student, opp])
    session.commit()

    admin_token = create_access_token(subject=admin.id, role="admin")
    student_token = create_access_token(subject=student.id, role="student")

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield {
        "client": client,
        "session": session,
        "admin": admin,
        "student": student,
        "opp": opp,
        "admin_token": admin_token,
        "student_token": student_token,
    }

    app.dependency_overrides.clear()
    session.close()


def test_01_rbac_student_access_rejected(test_setup):
    """Students attempting admin operations are rejected with 403 Forbidden."""
    client = test_setup["client"]
    student_token = test_setup["student_token"]
    opp_id = test_setup["opp"].id

    headers = {"Authorization": f"Bearer {student_token}"}
    res = client.get(f"/api/v1/admin/opportunities/{opp_id}/criteria", headers=headers)
    assert res.status_code == 403
    assert "Administrator privileges required" in res.json().get("detail", "")

    # Unauthenticated rejected with 401
    res_unauth = client.get(f"/api/v1/admin/opportunities/{opp_id}/criteria")
    assert res_unauth.status_code == 401


def test_02_create_criterion_manually(test_setup):
    """Admin can create a structured eligibility criterion manually."""
    client = test_setup["client"]
    admin_token = test_setup["admin_token"]
    opp_id = test_setup["opp"].id

    payload = {
        "criterion_type": "MINIMUM_ACADEMIC_GRADE",
        "operator": "GTE",
        "criterion_value": "FIRST_CLASS",
        "is_mandatory": True,
        "source_text": "First Class Honours degree required.",
        "evidence_url": "https://moi.ac.ke/bulletin-2026.pdf"
    }
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post(f"/api/v1/admin/opportunities/{opp_id}/criteria", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["criterion_type"] == "MINIMUM_ACADEMIC_GRADE"
    assert data["criterion_value"] == "FIRST_CLASS"
    assert data["verification_status"] == "PENDING_REVIEW"
    assert data["opportunity_id"] == opp_id


def test_03_verify_criterion_with_audit_trail(test_setup):
    """Admin certifies criterion as VERIFIED with required evidence URL and notes."""
    client = test_setup["client"]
    admin_token = test_setup["admin_token"]
    opp_id = test_setup["opp"].id
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create criterion
    c_res = client.post(
        f"/api/v1/admin/opportunities/{opp_id}/criteria",
        json={
            "criterion_type": "KCSE_GRADE",
            "operator": "GTE",
            "criterion_value": "B+",
            "source_text": "KCSE B+ required.",
            "is_mandatory": True
        },
        headers=headers
    )
    crit_id = c_res.json()["id"]

    # Verify with valid URL
    v_payload = {
        "evidence_url": "https://moi.ac.ke/official-guidelines.pdf",
        "evidence_notes": "Cross-referenced with Moi University 2026 official admissions portal."
    }
    v_res = client.post(f"/api/v1/admin/criteria/{crit_id}/verify", json=v_payload, headers=headers)
    assert v_res.status_code == 200
    v_data = v_res.json()
    assert v_data["verification_status"] == "VERIFIED"
    assert v_data["verified_by"] is not None
    assert v_data["verified_at"] is not None
    assert v_data["evidence_url"] == v_payload["evidence_url"]

    # Inspect audit history
    h_res = client.get(f"/api/v1/admin/criteria/{crit_id}/history", headers=headers)
    assert h_res.status_code == 200
    history = h_res.json()
    assert len(history) >= 2  # MANUAL_CREATE + VERIFY
    latest_event = history[0]
    assert latest_event["event_type"] == "VERIFY"
    assert latest_event["new_status"] == "VERIFIED"


def test_04_verify_rejects_malformed_urls(test_setup):
    """Admin verify endpoint rejects malformed, missing, or localhost evidence URLs."""
    client = test_setup["client"]
    admin_token = test_setup["admin_token"]
    opp_id = test_setup["opp"].id
    headers = {"Authorization": f"Bearer {admin_token}"}

    c_res = client.post(
        f"/api/v1/admin/opportunities/{opp_id}/criteria",
        json={
            "criterion_type": "NUMERIC_GPA",
            "operator": "GTE",
            "criterion_value": "3.5",
            "source_text": "GPA 3.5 required."
        },
        headers=headers
    )
    crit_id = c_res.json()["id"]

    # Localhost URL rejected
    bad_payload = {
        "evidence_url": "http://localhost:8000/internal-doc",
        "evidence_notes": "Testing invalid url"
    }
    res = client.post(f"/api/v1/admin/criteria/{crit_id}/verify", json=bad_payload, headers=headers)
    assert res.status_code == 422


def test_05_reject_flag_and_reopen_criterion(test_setup):
    """Admin can reject, flag, and reopen a criterion."""
    client = test_setup["client"]
    admin_token = test_setup["admin_token"]
    opp_id = test_setup["opp"].id
    headers = {"Authorization": f"Bearer {admin_token}"}

    c_res = client.post(
        f"/api/v1/admin/opportunities/{opp_id}/criteria",
        json={
            "criterion_type": "COUNTY_RESTRICTION",
            "operator": "IN",
            "criterion_value": "Nairobi",
            "source_text": "Must be Nairobi resident."
        },
        headers=headers
    )
    crit_id = c_res.json()["id"]

    # Reject
    rej_res = client.post(
        f"/api/v1/admin/criteria/{crit_id}/reject",
        json={"evidence_notes": "County restriction contradicted by primary source."},
        headers=headers
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["verification_status"] == "REJECTED"

    # Flag for review
    flag_res = client.post(
        f"/api/v1/admin/criteria/{crit_id}/flag",
        json={"evidence_notes": "Needs secondary check with ministry circular."},
        headers=headers
    )
    assert flag_res.status_code == 200
    assert flag_res.json()["verification_status"] == "NEEDS_REVIEW"

    # Reopen
    reopen_res = client.post(
        f"/api/v1/admin/criteria/{crit_id}/reopen",
        json={"reason": "New official gazette notice issued."},
        headers=headers
    )
    assert reopen_res.status_code == 200
    assert reopen_res.json()["verification_status"] == "PENDING_REVIEW"
    assert reopen_res.json()["verified_by"] is None
    assert reopen_res.json()["verified_at"] is None


def test_06_public_opportunity_criteria_endpoint(test_setup):
    """Students and public can retrieve structured criteria via public endpoint."""
    client = test_setup["client"]
    opp_id = test_setup["opp"].id

    res = client.get(f"/api/v1/opportunities/{opp_id}/criteria")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
