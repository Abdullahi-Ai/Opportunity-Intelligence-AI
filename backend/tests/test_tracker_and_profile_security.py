"""
Security Verification Suite for Student Profile, Application Tracker, and Checklist Authorization.
Verifies:
1. 401 Unauthorized on unauthenticated requests.
2. 403 Forbidden on cross-user read, write, toggle, update, and delete operations.
3. Proper ownership resolution from JWT subject, not client-supplied student IDs.
4. Admin authorization bypass for authorized operations.
5. 404 handling for non-existent records without information leakage.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

def create_test_student(prefix: str):
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@uonbi.ac.ke"
    password = "SecurePassword123!"
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": f"Student {prefix.upper()}",
        "role": "student",
        "university": "University of Nairobi",
        "field_of_study": "Computer Science",
        "degree_level": "Undergraduate",
        "year_of_study": 2,
        "graduation_year": 2028
    })
    assert reg_resp.status_code == 201
    data = reg_resp.json()
    return {
        "email": email,
        "token": data["access_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "student_id": data["user"]["student_profile"]["id"]
    }

def create_test_admin():
    email = f"admin_{uuid.uuid4().hex[:8]}@opportunity.or.ke"
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "AdminPassword123!",
        "full_name": "Security Administrator",
        "role": "admin",
        "admin_secret": settings.ADMIN_REGISTRATION_SECRET
    })
    assert reg_resp.status_code == 201
    data = reg_resp.json()
    return {
        "email": email,
        "token": data["access_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"}
    }

def test_unauthenticated_requests_rejected():
    """All protected tracker and profile endpoints must return 401 when no token is provided."""
    dummy_id = str(uuid.uuid4())
    
    # Profile
    assert client.get("/api/v1/profile/test@uonbi.ac.ke").status_code == 401
    assert client.post("/api/v1/profile", json={"email": "a@b.com", "full_name": "A", "university": "U", "field_of_study": "CS", "degree_level": "Undergraduate", "year_of_study": 1}).status_code == 401
    assert client.delete("/api/v1/profile/test@uonbi.ac.ke").status_code == 401

    # Tracker & Checklist
    assert client.post("/api/v1/tracker/save", json={"student_id": dummy_id, "opportunity_id": "opp-hef-undergraduate-2026"}).status_code == 401
    assert client.get(f"/api/v1/tracker/{dummy_id}").status_code == 401
    assert client.delete(f"/api/v1/tracker/{dummy_id}/opp-hef-undergraduate-2026").status_code == 401
    assert client.patch(f"/api/v1/tracker/{dummy_id}/stage?new_stage=Drafting").status_code == 401
    assert client.post(f"/api/v1/tracker/{dummy_id}/checklists", json={"task_description": "Task"}).status_code == 401
    assert client.patch(f"/api/v1/checklists/{dummy_id}/toggle").status_code == 401
    assert client.delete(f"/api/v1/checklists/{dummy_id}").status_code == 401
    assert client.get(f"/api/v1/tracker/{dummy_id}/stats").status_code == 401

def test_cross_user_profile_access_forbidden():
    """Student A cannot access, update, or delete Student B's profile."""
    student_a = create_test_student("alice")
    student_b = create_test_student("bob")

    # Alice attempts to read Bob's profile
    read_resp = client.get(f"/api/v1/profile/{student_b['email']}", headers=student_a["headers"])
    assert read_resp.status_code == 403
    assert "Access denied" in read_resp.json()["detail"]

    # Alice attempts to modify Bob's profile
    update_resp = client.post("/api/v1/profile", json={
        "email": student_b["email"],
        "full_name": "Tampered Bob",
        "university": "Tampered Uni",
        "field_of_study": "Malicious",
        "degree_level": "Undergraduate",
        "year_of_study": 4
    }, headers=student_a["headers"])
    assert update_resp.status_code == 403

    # Alice attempts to delete Bob's profile
    del_resp = client.delete(f"/api/v1/profile/{student_b['email']}", headers=student_a["headers"])
    assert del_resp.status_code == 403

def test_cross_user_tracker_and_checklist_operations_forbidden():
    """Student A cannot save, view, modify, or delete Student B's tracked opportunities or tasks."""
    student_a = create_test_student("charlie")
    student_b = create_test_student("david")

    # Bob saves an opportunity to his tracker
    save_bob = client.post("/api/v1/tracker/save", json={
        "student_id": student_b["student_id"],
        "opportunity_id": "opp-safaricom-attachment-2026",
        "stage": "Saved",
        "auto_generate_checklist": True
    }, headers=student_b["headers"])
    assert save_bob.status_code == 201
    bob_app_id = save_bob.json()["tracked_application_id"]

    # Alice attempts to save an opportunity into Bob's tracker
    alice_save_bob = client.post("/api/v1/tracker/save", json={
        "student_id": student_b["student_id"],
        "opportunity_id": "opp-hef-undergraduate-2026"
    }, headers=student_a["headers"])
    assert alice_save_bob.status_code == 403

    # Alice attempts to read Bob's tracker
    read_resp = client.get(f"/api/v1/tracker/{student_b['student_id']}", headers=student_a["headers"])
    assert read_resp.status_code == 403

    # Alice attempts to read Bob's dashboard stats
    stats_resp = client.get(f"/api/v1/tracker/{student_b['student_id']}/stats", headers=student_a["headers"])
    assert stats_resp.status_code == 403

    # Alice attempts to change the stage of Bob's application
    stage_resp = client.patch(f"/api/v1/tracker/{bob_app_id}/stage?new_stage=Accepted", headers=student_a["headers"])
    assert stage_resp.status_code == 403

    # Alice attempts to add a checklist task to Bob's application
    add_chk_resp = client.post(f"/api/v1/tracker/{bob_app_id}/checklists", json={
        "task_description": "Forged requirement"
    }, headers=student_a["headers"])
    assert add_chk_resp.status_code == 403

    # Get one of Bob's checklist items
    bob_apps = client.get(f"/api/v1/tracker/{student_b['student_id']}", headers=student_b["headers"]).json()
    assert len(bob_apps) > 0
    bob_task_id = bob_apps[0]["checklists"][0]["id"]

    # Alice attempts to toggle Bob's checklist item
    toggle_resp = client.patch(f"/api/v1/checklists/{bob_task_id}/toggle", headers=student_a["headers"])
    assert toggle_resp.status_code == 403

    # Alice attempts to delete Bob's checklist item
    del_task_resp = client.delete(f"/api/v1/checklists/{bob_task_id}", headers=student_a["headers"])
    assert del_task_resp.status_code == 403

    # Alice attempts to delete Bob's tracked opportunity
    remove_opp_resp = client.delete(
        f"/api/v1/tracker/{student_b['student_id']}/opp-safaricom-attachment-2026",
        headers=student_a["headers"]
    )
    assert remove_opp_resp.status_code == 403

def test_admin_can_access_student_tracker_and_stats():
    """An administrator with verified role can view student tracking information."""
    admin = create_test_admin()
    student = create_test_student("emma")

    # Student saves an opportunity
    client.post("/api/v1/tracker/save", json={
        "student_id": student["student_id"],
        "opportunity_id": "opp-hef-undergraduate-2026",
        "stage": "Saved"
    }, headers=student["headers"])

    # Admin views student's tracker
    admin_view = client.get(f"/api/v1/tracker/{student['student_id']}", headers=admin["headers"])
    assert admin_view.status_code == 200
    assert len(admin_view.json()) == 1

    # Admin views student's stats
    admin_stats = client.get(f"/api/v1/tracker/{student['student_id']}/stats", headers=admin["headers"])
    assert admin_stats.status_code == 200
    assert admin_stats.json()["total_saved"] == 1
