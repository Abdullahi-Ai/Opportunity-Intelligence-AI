import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.agent.intent import classify_intent, IntentType
from app.agent.orchestrator import AgentOrchestrator
from app.db.session import get_db

client = TestClient(app)

def create_student(prefix: str, year: int = 3, field: str = "Computer Science"):
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@uonbi.ac.ke"
    password = "SecurePassword123!"
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": f"Student {prefix.title()}",
        "role": "student",
        "university": "University of Nairobi",
        "field_of_study": field,
        "degree_level": "Undergraduate",
        "year_of_study": year,
        "graduation_year": 2027
    })
    assert reg_resp.status_code == 201
    data = reg_resp.json()
    return {
        "email": email,
        "token": data["access_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "student_id": data["user"]["student_profile"]["id"],
        "user_id": data["user"]["id"]
    }

def get_first_opportunity_id():
    resp = client.get("/api/v1/opportunities")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) > 0
    return items[0]["id"], items[0]

def test_matches_endpoint_unauthenticated():
    resp = client.get("/api/v1/matches")
    assert resp.status_code == 401

def test_personalized_matches_scoring_and_explanation():
    student = create_student("cs_third_year", year=3, field="Computer Science")
    resp = client.get("/api/v1/matches", headers=student["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "matches" in data
    matches = data["matches"]
    assert isinstance(matches, list)
    assert len(matches) > 0

    first = matches[0]
    assert "opportunity_id" in first
    assert "title" in first
    assert "match_score" in first
    assert "eligibility_status" in first
    assert "match_explanation" in first
    assert 0 <= first["match_score"] <= 100
    assert first["eligibility_status"] in ["Meets requirements", "Needs verification", "Does not meet requirements"]

    safaricom_matches = [m for m in matches if "safaricom" in m["title"].lower() or "safaricom" in m["provider"].lower()]
    if safaricom_matches:
        s_match = safaricom_matches[0]
        assert s_match["eligibility_status"] == "Meets requirements"
        assert s_match["match_score"] >= 70
        assert "Computer Science" in s_match["match_explanation"] or "eligible" in s_match["match_explanation"].lower()

def test_personalized_matches_year_one_criteria():
    student = create_student("year1_arts", year=1, field="Fine Arts")
    resp = client.get("/api/v1/matches", headers=student["headers"])
    assert resp.status_code == 200
    data = resp.json()
    matches = data["matches"]
    safaricom_matches = [m for m in matches if "safaricom" in m["title"].lower()]
    if safaricom_matches:
        s_match = safaricom_matches[0]
        assert s_match["eligibility_status"] != "Meets requirements"

def test_planner_notes_and_target_date_lifecycle():
    student_a = create_student("owner_student", year=3)
    student_b = create_student("other_student", year=2)
    opp_id, _ = get_first_opportunity_id()

    save_resp = client.post("/api/v1/tracker/save", json={
        "student_id": student_a["student_id"],
        "opportunity_id": opp_id,
        "stage": "Drafting",
        "notes": "Initial personal tracking note"
    }, headers=student_a["headers"])
    assert save_resp.status_code == 201
    tracked_id = save_resp.json()["tracked_application_id"]

    notes_resp = client.patch(f"/api/v1/tracker/{tracked_id}/notes", json={
        "notes": "Updated application strategy: requested referee recommendation"
    }, headers=student_a["headers"])
    assert notes_resp.status_code == 200
    assert "referee recommendation" in notes_resp.json()["notes"]

    forbidden_notes = client.patch(f"/api/v1/tracker/{tracked_id}/notes", json={
        "notes": "Malicious tampering"
    }, headers=student_b["headers"])
    assert forbidden_notes.status_code == 403

    date_resp = client.patch(f"/api/v1/tracker/{tracked_id}/target-date", json={
        "target_submission_date": "2026-11-25T17:00:00"
    }, headers=student_a["headers"])
    assert date_resp.status_code == 200
    assert "2026-11-25" in str(date_resp.json()["target_submission_date"])

    forbidden_date = client.patch(f"/api/v1/tracker/{tracked_id}/target-date", json={
        "target_submission_date": "2026-12-01T00:00:00"
    }, headers=student_b["headers"])
    assert forbidden_date.status_code == 403

    detail_resp = client.get(f"/api/v1/tracker/application/{tracked_id}", headers=student_a["headers"])
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["id"] == tracked_id
    assert "opportunity" in detail_data
    assert "checklists" in detail_data
    assert len(detail_data["checklists"]) > 0

    forbidden_detail = client.get(f"/api/v1/tracker/application/{tracked_id}", headers=student_b["headers"])
    assert forbidden_detail.status_code == 403

def test_planner_generate_checklist_endpoint():
    student = create_student("checklist_student", year=3)
    opp_id, _ = get_first_opportunity_id()

    save_resp = client.post("/api/v1/tracker/save", json={
        "student_id": student["student_id"],
        "opportunity_id": opp_id,
        "stage": "Saved"
    }, headers=student["headers"])
    tracked_id = save_resp.json()["tracked_application_id"]

    gen_resp = client.post(f"/api/v1/tracker/{tracked_id}/generate-checklist", headers=student["headers"])
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["status"] == "success"
    assert gen_data["total_tasks"] >= 3

def test_intent_detection_tracking_progress():
    intent1, _ = classify_intent("What applications am I currently tracking?")
    assert intent1 == IntentType.TRACKING_PROGRESS

    intent2, _ = classify_intent("Which deadline is approaching in my planner?")
    assert intent2 == IntentType.TRACKING_PROGRESS

    intent3, _ = classify_intent("What incomplete tasks do I need to finish?")
    assert intent3 == IntentType.TRACKING_PROGRESS

def test_ai_advisor_tracking_progress_response():
    student = create_student("tracker_ai_student", year=3)
    opp_id, opp = get_first_opportunity_id()

    client.post("/api/v1/tracker/save", json={
        "student_id": student["student_id"],
        "opportunity_id": opp_id,
        "stage": "Drafting",
        "notes": "Working on statement of purpose"
    }, headers=student["headers"])

    db = next(get_db())
    try:
        orch = AgentOrchestrator()
        result = orch.process_turn(
            message="What applications am I currently tracking and what tasks are pending?",
            conversation_id=f"test_conv_{uuid.uuid4().hex[:6]}",
            student_profile={
                "id": student["student_id"],
                "student_id": student["student_id"],
                "degree_level": "Undergraduate",
                "field_of_study": "Computer Science",
                "year_of_study": 3,
                "preferred_categories": ["Attachment"]
            },
            db=db
        )
        assert result is not None
        reply = result.get("response", "")
        assert opp["title"].lower() in reply.lower() or "application" in reply.lower() or "task" in reply.lower()
    finally:
        db.close()
