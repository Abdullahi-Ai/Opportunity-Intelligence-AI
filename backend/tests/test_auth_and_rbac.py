import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

def test_student_registration_and_login():
    test_email = f"student_{uuid.uuid4().hex[:8]}@uonbi.ac.ke"
    reg_payload = {
        "email": test_email,
        "password": "SecurePassword123!",
        "full_name": "Wanjiku Mwangi",
        "role": "student",
        "university": "University of Nairobi",
        "field_of_study": "Data Science",
        "degree_level": "Undergraduate"
    }
    
    reg_resp = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert "access_token" in reg_data
    assert reg_data["user"]["role"] == "student"
    assert reg_data["user"]["full_name"] == "Wanjiku Mwangi"
    assert reg_data["user"]["student_profile"]["university"] == "University of Nairobi"
    
    login_resp = client.post("/api/v1/auth/login", json={
        "email": test_email,
        "password": "SecurePassword123!"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == test_email
    assert me_data["role"] == "student"

def test_duplicate_registration_rejected():
    test_email = f"dup_{uuid.uuid4().hex[:8]}@jkuat.ac.ke"
    payload = {
        "email": test_email,
        "password": "Password123!",
        "full_name": "Test User",
        "role": "student"
    }
    resp1 = client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 400
    assert "already exists" in resp2.json()["detail"]

def test_admin_registration_requires_verified_secret():
    admin_email = f"admin_{uuid.uuid4().hex[:8]}@opportunity.or.ke"
    
    fail_payload = {
        "email": admin_email,
        "password": "AdminPassword123!",
        "full_name": "System Administrator",
        "role": "admin",
        "admin_secret": "wrong_secret"
    }
    fail_resp = client.post("/api/v1/auth/register", json=fail_payload)
    assert fail_resp.status_code == 403
    assert "Invalid administrator secret" in fail_resp.json()["detail"]

    success_payload = {
        "email": admin_email,
        "password": "AdminPassword123!",
        "full_name": "System Administrator",
        "role": "admin",
        "admin_secret": settings.ADMIN_REGISTRATION_SECRET
    }
    success_resp = client.post("/api/v1/auth/register", json=success_payload)
    assert success_resp.status_code == 201
    admin_data = success_resp.json()
    assert admin_data["user"]["role"] == "admin"
    assert "access_token" in admin_data

def test_role_based_access_control_on_admin_endpoints():
    student_email = f"student_rbac_{uuid.uuid4().hex[:8]}@ku.ac.ke"
    student_reg = client.post("/api/v1/auth/register", json={
        "email": student_email,
        "password": "StudentPassword123!",
        "full_name": "Otieno James",
        "role": "student"
    })
    student_token = student_reg.json()["access_token"]

    admin_email = f"admin_rbac_{uuid.uuid4().hex[:8]}@ku.ac.ke"
    admin_reg = client.post("/api/v1/auth/register", json={
        "email": admin_email,
        "password": "AdminPassword123!",
        "full_name": "Chief Admin",
        "role": "admin",
        "admin_secret": settings.ADMIN_REGISTRATION_SECRET
    })
    admin_token = admin_reg.json()["access_token"]

    opp_payload = {
        "title": "National Science Foundation Fellowship 2026",
        "provider": "Ministry of Education",
        "category": "Fellowship",
        "target_audience": "Kenyan Postgraduate Researchers",
        "official_url": "https://education.go.ke/nsf",
        "application_deadline": "2026-12-15",
        "is_verified": True,
        "source_notes": "Official Kenya Gazette Notice Vol. CXXVIII No. 42"
    }

    unauth_resp = client.post("/api/v1/admin/opportunities", json=opp_payload)
    assert unauth_resp.status_code == 401

    student_resp = client.post(
        "/api/v1/admin/opportunities",
        json=opp_payload,
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert student_resp.status_code == 403
    assert "Administrator privileges required" in student_resp.json()["detail"]

    admin_resp = client.post(
        "/api/v1/admin/opportunities",
        json=opp_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert admin_resp.status_code == 201
    created_opp = admin_resp.json()
    assert created_opp["title"] == opp_payload["title"]
    opp_id = created_opp["id"]

    update_payload = {
        **opp_payload,
        "title": "National Science Foundation Fellowship 2026 (Updated)",
        "source_notes": "Recertified by Admin review."
    }
    update_resp = client.put(
        f"/api/v1/admin/opportunities/{opp_id}",
        json=update_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "National Science Foundation Fellowship 2026 (Updated)"

    delete_resp = client.delete(
        f"/api/v1/admin/opportunities/{opp_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["status"] in ["success", "archived"]
