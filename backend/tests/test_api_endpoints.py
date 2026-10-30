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

def test_rag_search_endpoint():
    payload = {
        "query": "Safaricom industrial attachment for undergraduate computer science",
        "category": "Internship",
        "top_k": 3
    }
    response = client.post("/api/v1/rag/search", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["results"]) > 0
    assert "safaricom" in data["results"][0]["title"].lower()

def test_deadline_countdown_endpoint():
    payload = {"deadline_date_str": "2026-12-31"}
    response = client.post("/api/v1/agent/deadline-countdown", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "open"
    assert data["is_open"] is True
    assert data["days_remaining"] >= 0

def test_eligibility_assessment_endpoint():
    payload = {
        "opportunity_id": "opp-safaricom-attachment-2026",
        "student_degree_level": "Undergraduate",
        "student_field_of_study": "Computer Science",
        "student_year_of_study": 3
    }
    response = client.post("/api/v1/agent/assess-eligibility", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["overall_assessment"] == "Likely Eligible"

def test_student_profile_and_tracking_flow():
    # 1. Create Student Profile
    profile_data = {
        "email": "brian.test@students.uonbi.ac.ke",
        "full_name": "Brian Kiprono",
        "university": "University of Nairobi",
        "field_of_study": "Computer Science",
        "degree_level": "Undergraduate",
        "year_of_study": 3,
        "graduation_year": 2027,
        "county_of_origin": "Uasin Gishu"
    }
    resp = client.post("/api/v1/profile", json=profile_data)
    assert resp.status_code == 201
    student = resp.json()
    student_id = student["id"]

    # 2. Track an opportunity
    track_payload = {
        "student_id": student_id,
        "opportunity_id": "opp-safaricom-attachment-2026",
        "stage": "Saved",
        "notes": "Need to request Dean's recommendation letter next week."
    }
    resp_track = client.post("/api/v1/tracker/save", json=track_payload)
    assert resp_track.status_code == 201
    tracked_id = resp_track.json()["tracked_application_id"]

    # 3. Update stage
    resp_patch = client.patch(f"/api/v1/tracker/{tracked_id}/stage?new_stage=Drafting")
    assert resp_patch.status_code == 200
    assert resp_patch.json()["new_stage"] == "Drafting"

    # 4. Retrieve student tracked list
    resp_list = client.get(f"/api/v1/tracker/{student_id}")
    assert resp_list.status_code == 200
    apps = resp_list.json()
    assert len(apps) == 1
    assert apps[0]["opportunity_id"] == "opp-safaricom-attachment-2026"
    assert apps[0]["stage"] == "Drafting"
