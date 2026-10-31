import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "Opportunity Intelligence AI"
    assert data["status"] == "operational"

def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["chromadb"]["total_chunks_indexed"] > 0

def test_list_opportunities_with_filters():
    response = client.get("/api/v1/opportunities")
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 10
    assert "days_remaining" in items[0]
    assert "deadline_status_label" in items[0]

    resp_cat = client.get("/api/v1/opportunities?category=Scholarship")
    assert resp_cat.status_code == 200
    scholarships = resp_cat.json()
    assert len(scholarships) > 0
    for s in scholarships:
        assert s["category"] == "Scholarship"

    resp_search = client.get("/api/v1/opportunities?search=Safaricom")
    assert resp_search.status_code == 200
    safaricom_items = resp_search.json()
    assert len(safaricom_items) >= 2
    for item in safaricom_items:
        assert "safaricom" in item["title"].lower() or "safaricom" in item["provider"].lower()

def test_opportunity_detail_endpoint():
    opp_id = "opp-safaricom-attachment-2026"
    response = client.get(f"/api/v1/opportunities/{opp_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == opp_id
    assert "Safaricom" in data["provider"]
    assert data["official_url"] == "https://www.safaricom.co.ke/careers"
    assert data["is_verified"] is True

def test_student_lifecycle_and_tracking_flow():
    import uuid
    test_email = f"faith.chebet_{uuid.uuid4().hex[:8]}@students.ku.ac.ke"

    reg_payload = {
        "email": test_email,
        "password": "SecurePassword123!",
        "full_name": "Faith Chebet",
        "role": "student",
        "university": "Kenyatta University",
        "field_of_study": "Civil Engineering",
        "degree_level": "Undergraduate",
        "year_of_study": 1,
        "graduation_year": 2029
    }
    reg_resp = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201
    auth_data = reg_resp.json()
    token = auth_data["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    student_id = auth_data["user"]["student_profile"]["id"]

    profile_data = {
        "email": test_email,
        "full_name": "Faith Chebet",
        "university": "Kenyatta University",
        "field_of_study": "Civil Engineering",
        "degree_level": "Undergraduate",
        "year_of_study": 1,
        "graduation_year": 2029,
        "county_of_origin": "Bomet",
        "gpa_or_grade": "A-",
        "preferred_categories": "Scholarship, Bursary"
    }
    resp = client.post("/api/v1/profile", json=profile_data, headers=auth_headers)
    assert resp.status_code == 201
    student = resp.json()
    assert student["email"] == test_email
    assert student["county_of_origin"] == "Bomet"

    opp_id = "opp-hef-undergraduate-2026"
    track_payload = {
        "student_id": student_id,
        "opportunity_id": opp_id,
        "stage": "Saved",
        "notes": "Chief endorsement letter requested.",
        "auto_generate_checklist": True
    }
    resp_track = client.post("/api/v1/tracker/save", json=track_payload, headers=auth_headers)
    assert resp_track.status_code == 201
    tracked_id = resp_track.json()["tracked_application_id"]

    resp_list = client.get(f"/api/v1/tracker/{student_id}", headers=auth_headers)
    assert resp_list.status_code == 200
    tracked_list = resp_list.json()
    assert len(tracked_list) == 1
    assert tracked_list[0]["opportunity_id"] == opp_id
    assert len(tracked_list[0]["checklists"]) > 0

    first_task = tracked_list[0]["checklists"][0]
    task_id = first_task["id"]
    assert first_task["is_completed"] is False

    resp_toggle = client.patch(f"/api/v1/checklists/{task_id}/toggle", headers=auth_headers)
    assert resp_toggle.status_code == 200
    assert resp_toggle.json()["is_completed"] is True
    assert resp_toggle.json()["completed_at"] is not None

    custom_task_payload = {
        "task_description": "Visit Equity Bank Kericho branch for stamped statement",
        "required_document_type": "Bank Statement"
    }
    resp_custom = client.post(f"/api/v1/tracker/{tracked_id}/checklists", json=custom_task_payload, headers=auth_headers)
    assert resp_custom.status_code == 201
    custom_task_id = resp_custom.json()["id"]

    resp_stats = client.get(f"/api/v1/tracker/{student_id}/stats", headers=auth_headers)
    assert resp_stats.status_code == 200
    stats = resp_stats.json()
    assert stats["total_saved"] == 1
    assert stats["completed_checklist_tasks"] == 1
    assert stats["total_checklist_tasks"] >= 2
    assert stats["checklist_completion_rate"] > 0

    resp_stage = client.patch(f"/api/v1/tracker/{tracked_id}/stage?new_stage=Drafting", headers=auth_headers)
    assert resp_stage.status_code == 200
    assert resp_stage.json()["new_stage"] == "Drafting"

    resp_del_task = client.delete(f"/api/v1/checklists/{custom_task_id}", headers=auth_headers)
    assert resp_del_task.status_code == 200

    resp_remove = client.delete(f"/api/v1/tracker/{student_id}/{opp_id}", headers=auth_headers)
    assert resp_remove.status_code == 200

    resp_del_profile = client.delete(f"/api/v1/profile/{test_email}", headers=auth_headers)
    assert resp_del_profile.status_code == 200

    resp_check = client.get(f"/api/v1/profile/{test_email}", headers=auth_headers)
    assert resp_check.status_code == 404
