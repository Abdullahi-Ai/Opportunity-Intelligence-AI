import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_full_14_step_student_journey_and_cross_user_isolation():
    prefix_a = uuid.uuid4().hex[:8]
    email_a = f"student_a_{prefix_a}@uonbi.ac.ke"
    password = "StrongPassword123!"

    reg_resp = client.post("/api/v1/auth/register", json={
        "email": email_a,
        "password": password,
        "full_name": "Wanjiku Kimani",
        "role": "student",
        "university": "University of Nairobi",
        "field_of_study": "Computer Science",
        "degree_level": "Undergraduate",
        "year_of_study": 2,
        "graduation_year": 2027
    })
    assert reg_resp.status_code == 201
    auth_data = reg_resp.json()
    student_a_id = auth_data["user"]["student_profile"]["id"]
    token_a = auth_data["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    login_resp = client.post("/api/v1/auth/login", json={
        "email": email_a,
        "password": password
    })
    assert login_resp.status_code == 200
    token_a = login_resp.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    update_profile_resp = client.post("/api/v1/profile", json={
        "email": email_a,
        "full_name": "Wanjiku Kimani",
        "university": "University of Nairobi",
        "field_of_study": "Computer Science",
        "degree_level": "Undergraduate",
        "year_of_study": 3,
        "graduation_year": 2027,
        "county_of_origin": "Kiambu",
        "preferred_categories": "Internship,Scholarship"
    }, headers=headers_a)
    assert update_profile_resp.status_code == 201
    assert update_profile_resp.json()["year_of_study"] == 3

    matches_resp = client.get("/api/v1/matches", headers=headers_a)
    assert matches_resp.status_code == 200
    matches_data = matches_resp.json()
    assert "matches" in matches_data
    assert len(matches_data["matches"]) > 0

    search_resp = client.get("/api/v1/opportunities?search=safaricom", headers=headers_a)
    assert search_resp.status_code == 200
    opps = search_resp.json()
    assert len(opps) > 0
    opp_id = opps[0]["id"]

    detail_resp = client.get(f"/api/v1/opportunities/{opp_id}", headers=headers_a)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == opp_id

    save_resp = client.post("/api/v1/tracker/save", json={
        "student_id": student_a_id,
        "opportunity_id": opp_id,
        "stage": "Saved",
        "notes": "Interested in 3-month attachment"
    }, headers=headers_a)
    assert save_resp.status_code == 201
    tracked_id = save_resp.json()["tracked_application_id"]

    chk_gen_resp = client.post(f"/api/v1/tracker/{tracked_id}/generate-checklist", headers=headers_a)
    assert chk_gen_resp.status_code == 200

    detail_app_resp = client.get(f"/api/v1/tracker/application/{tracked_id}", headers=headers_a)
    assert detail_app_resp.status_code == 200
    checklists = detail_app_resp.json()["checklists"]
    assert len(checklists) > 0
    task_id = checklists[0]["id"]

    toggle_resp = client.patch(f"/api/v1/checklists/{task_id}/toggle", headers=headers_a)
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["is_completed"] is True

    stage_resp = client.patch(f"/api/v1/tracker/{tracked_id}/stage?new_stage=Drafting", headers=headers_a)
    assert stage_resp.status_code == 200
    assert stage_resp.json()["stage"] == "Drafting"

    notes_resp = client.patch(f"/api/v1/tracker/{tracked_id}/notes", json={
        "notes": "Acquired recommendation letter from faculty dean."
    }, headers=headers_a)
    assert notes_resp.status_code == 200

    date_resp = client.patch(f"/api/v1/tracker/{tracked_id}/target-date", json={
        "target_submission_date": "2026-11-20"
    }, headers=headers_a)
    assert date_resp.status_code == 200

    chat_resp = client.post("/api/v1/chat", json={
        "message": "What applications am I currently tracking and what tasks have I not completed?",
        "student_id": student_a_id
    }, headers=headers_a)
    assert chat_resp.status_code == 200
    conv_id = chat_resp.json()["conversation_id"]
    reply_text = chat_resp.json()["response"].lower()
    assert "application" in reply_text or "task" in reply_text or "safaricom" in reply_text

    relogin_resp = client.post("/api/v1/auth/login", json={
        "email": email_a,
        "password": password
    })
    assert relogin_resp.status_code == 200
    retoken = relogin_resp.json()["access_token"]
    reheaders = {"Authorization": f"Bearer {retoken}"}

    history_resp = client.get(f"/api/v1/conversations/{conv_id}", headers=reheaders)
    assert history_resp.status_code == 200
    assert len(history_resp.json()["messages"]) >= 2

    tracked_list_resp = client.get(f"/api/v1/tracker/{student_a_id}", headers=reheaders)
    assert tracked_list_resp.status_code == 200
    assert len(tracked_list_resp.json()) >= 1

    prefix_b = uuid.uuid4().hex[:8]
    email_b = f"student_b_{prefix_b}@ku.ac.ke"
    reg_b_resp = client.post("/api/v1/auth/register", json={
        "email": email_b,
        "password": "StrongPassword456!",
        "full_name": "Otieno Omondi",
        "role": "student",
        "university": "Kenyatta University",
        "field_of_study": "Economics",
        "degree_level": "Undergraduate",
        "year_of_study": 1
    })
    assert reg_b_resp.status_code == 201
    headers_b = {"Authorization": f"Bearer {reg_b_resp.json()['access_token']}"}

    forbidden_tracker = client.get(f"/api/v1/tracker/{student_a_id}", headers=headers_b)
    assert forbidden_tracker.status_code == 403

    forbidden_notes = client.patch(f"/api/v1/tracker/{tracked_id}/notes", json={
        "notes": "Hacked note"
    }, headers=headers_b)
    assert forbidden_notes.status_code == 403

    forbidden_conv = client.get(f"/api/v1/conversations/{conv_id}", headers=headers_b)
    assert forbidden_conv.status_code == 403
