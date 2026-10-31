import pytest
from datetime import date, timedelta
from app.agent.tools import (
    DeadlineCountdownInput,
    tool_calculate_deadline_countdown,
    AssessEligibilityInput,
    tool_assess_eligibility,
    GenerateChecklistInput,
    tool_generate_application_checklist
)

def test_deadline_countdown_future():
    future_date = date.today() + timedelta(days=15)
    result = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=str(future_date)))
    assert result["status"] == "open"
    assert result["is_open"] is True
    assert result["days_remaining"] == 15

def test_deadline_countdown_past():
    past_date = date.today() - timedelta(days=5)
    result = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=str(past_date)))
    assert result["status"] == "expired"
    assert result["is_open"] is False
    assert result["days_ago"] == 5

def test_deadline_countdown_invalid():
    result = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str="invalid-date"))
    assert result["status"] == "error"

def test_assess_eligibility_safaricom_attachment():
    payload = AssessEligibilityInput(
        opportunity_id="opp-safaricom-attachment-2026",
        student_degree_level="Undergraduate",
        student_field_of_study="Computer Science",
        student_year_of_study=3
    )
    result = tool_assess_eligibility(payload)
    assert result["status"] == "success"
    assert result["overall_assessment"] == "Likely Eligible"
    assert result["official_url"] == "https://www.safaricom.co.ke/careers"

def test_assess_eligibility_ineligible_year():
    payload = AssessEligibilityInput(
        opportunity_id="opp-safaricom-attachment-2026",
        student_degree_level="Undergraduate",
        student_field_of_study="Computer Science",
        student_year_of_study=1
    )
    result = tool_assess_eligibility(payload)
    assert result["status"] == "success"
    assert "Ineligible" in result["overall_assessment"]

def test_generate_application_checklist():
    payload = GenerateChecklistInput(opportunity_id="opp-hef-undergraduate-2026")
    result = tool_generate_application_checklist(payload)
    assert result["status"] == "success"
    assert len(result["tasks"]) > 0
    task_texts = " ".join([t["task"] for t in result["tasks"]])
    assert "KRA PIN" in task_texts or "KCSE" in task_texts or "National ID" in task_texts
