import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_registration_persists_academic_fields_with_list_specialisations():
    """Verify that student registration persists degree_title, specialisations (list), expected_graduation, and country."""
    test_email = f"academic_test_{uuid.uuid4().hex[:8]}@students.uonbi.ac.ke"
    payload = {
        "email": test_email,
        "password": "StrongPassword2026!",
        "full_name": "Amina Odhiambo",
        "role": "student",
        "university": "University of Nairobi",
        "field_of_study": "Computer Science",
        "degree_level": "Undergraduate",
        "degree_title": "Bachelor of Science in Computer Science",
        "specialisations": ["Artificial Intelligence", "Data Engineering"],
        "expected_graduation": "2027",
        "country": "Kenya",
        "year_of_study": 3,
        "graduation_year": 2027
    }

    # 1. Register
    reg_resp = client.post("/api/v1/auth/register", json=payload)
    assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"
    auth_data = reg_resp.json()
    token = auth_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify registration response contains brief student profile with academic fields
    reg_profile = auth_data["user"]["student_profile"]
    assert reg_profile is not None
    assert reg_profile["degree_title"] == "Bachelor of Science in Computer Science"
    assert reg_profile["specialisations"] == "Artificial Intelligence, Data Engineering"
    assert reg_profile["expected_graduation"] == "2027"
    assert reg_profile["country"] == "Kenya"

    # 2. Verify /api/v1/auth/me
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me_profile = me_resp.json()["student_profile"]
    assert me_profile is not None
    assert me_profile["degree_title"] == "Bachelor of Science in Computer Science"
    assert me_profile["specialisations"] == "Artificial Intelligence, Data Engineering"
    assert me_profile["expected_graduation"] == "2027"
    assert me_profile["country"] == "Kenya"

    # 3. Verify /api/v1/profile/{email}
    prof_resp = client.get(f"/api/v1/profile/{test_email}", headers=headers)
    assert prof_resp.status_code == 200
    profile_data = prof_resp.json()
    assert profile_data["email"] == test_email
    assert profile_data["university"] == "University of Nairobi"
    assert profile_data["field_of_study"] == "Computer Science"
    assert profile_data["degree_title"] == "Bachelor of Science in Computer Science"
    assert profile_data["specialisations"] == "Artificial Intelligence, Data Engineering"
    assert profile_data["expected_graduation"] == "2027"
    assert profile_data["country"] == "Kenya"


def test_registration_persists_academic_fields_with_string_specialisations():
    """Verify that student registration persists academic fields with string specialisations and custom country."""
    test_email = f"academic_test_{uuid.uuid4().hex[:8]}@students.uonbi.ac.ke"
    payload = {
        "email": test_email,
        "password": "StrongPassword2026!",
        "full_name": "Jean Paul",
        "role": "student",
        "university": "University of Rwanda",
        "field_of_study": "Information Systems",
        "degree_level": "Undergraduate",
        "degree_title": "Bachelor of Information Systems",
        "specialisations": "Business Analytics, Cloud Infrastructure",
        "expected_graduation": "December 2028",
        "country": "Rwanda",
        "year_of_study": 2,
        "graduation_year": 2028
    }

    reg_resp = client.post("/api/v1/auth/register", json=payload)
    assert reg_resp.status_code == 201
    auth_data = reg_resp.json()
    token = auth_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    prof_resp = client.get(f"/api/v1/profile/{test_email}", headers=headers)
    assert prof_resp.status_code == 200
    data = prof_resp.json()
    assert data["degree_title"] == "Bachelor of Information Systems"
    assert data["specialisations"] == "Business Analytics, Cloud Infrastructure"
    assert data["expected_graduation"] == "December 2028"
    assert data["country"] == "Rwanda"


def test_registration_with_default_and_none_academic_fields():
    """Verify registration handles omitted/none academic fields with safe defaults."""
    test_email = f"academic_test_{uuid.uuid4().hex[:8]}@students.uonbi.ac.ke"
    payload = {
        "email": test_email,
        "password": "StrongPassword2026!",
        "full_name": "Standard Student",
        "role": "student"
    }

    reg_resp = client.post("/api/v1/auth/register", json=payload)
    assert reg_resp.status_code == 201
    auth_data = reg_resp.json()
    token = auth_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    prof_resp = client.get(f"/api/v1/profile/{test_email}", headers=headers)
    assert prof_resp.status_code == 200
    data = prof_resp.json()
    assert data["country"] == "Kenya"
    assert data["degree_title"] is None
    assert data["specialisations"] is None
    assert data["expected_graduation"] is None


def test_profile_update_normalizes_list_and_string_specialisations():
    """Verify that POST /api/v1/profile normalizes list specialisations and updates academic fields."""
    test_email = f"academic_test_{uuid.uuid4().hex[:8]}@students.uonbi.ac.ke"
    reg_payload = {
        "email": test_email,
        "password": "StrongPassword2026!",
        "full_name": "Profile Update Student",
        "role": "student"
    }
    reg_resp = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Update with list specialisations
    update_payload = {
        "email": test_email,
        "full_name": "Profile Update Student",
        "university": "Kenyatta University",
        "field_of_study": "Software Engineering",
        "degree_level": "Undergraduate",
        "degree_title": "BSc Software Engineering",
        "specialisations": ["Cybersecurity", "Distributed Computing"],
        "expected_graduation": "2029",
        "country": "Kenya",
        "year_of_study": 1,
        "graduation_year": 2029
    }
    update_resp = client.post("/api/v1/profile", json=update_payload, headers=headers)
    assert update_resp.status_code == 201, f"Update failed: {update_resp.text}"
    update_data = update_resp.json()
    assert update_data["degree_title"] == "BSc Software Engineering"
    assert update_data["specialisations"] == "Cybersecurity, Distributed Computing"
    assert update_data["expected_graduation"] == "2029"

    # Update with string specialisations
    update_payload["specialisations"] = "DevOps & SRE"
    update_resp2 = client.post("/api/v1/profile", json=update_payload, headers=headers)
    assert update_resp2.status_code == 201
    assert update_resp2.json()["specialisations"] == "DevOps & SRE"
