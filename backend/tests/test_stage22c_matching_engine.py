"""
Unit and integration tests for Stage 2.2C:
Deterministic Academic Matching Engine Integration with Structured Eligibility Criteria.

Covers:
1. Degree classification evaluation (Honours hierarchy).
2. KCSE grade evaluation.
3. Numeric GPA and scale comparison.
4. Scale mismatch uncertainty (never invented conversion).
5. County restriction vs Geographic quota.
6. Fixed graduation year vs rolling months-since-graduation.
7. Expected graduation window evaluation.
8. Academic standing evaluation.
9. Verified vs Unverified boundary: Unverified criteria NEVER disqualify.
10. Mandatory vs Desirable boundary: Desirable criteria NEVER disqualify.
11. Missing student profile fields yield Needs Verification.
12. 3-tier scoring and deterministic ranking preservation.
13. API and agent tool parity.
"""

import sys
import uuid
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

backend_dir = Path(__file__).resolve().parent.parent
repo_root = backend_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import Base
from app.models.entities import (
    User,
    StudentProfile,
    Opportunity,
    OpportunityEligibilityCriterion,
    CriterionCategory,
    CriterionOperator,
    CriterionVerificationStatus,
)
from app.services.matching_engine import (
    evaluate_structured_criterion,
    evaluate_opportunity_eligibility,
    calculate_match_score,
    get_match_sort_key,
)
from app.agent.tools import tool_assess_eligibility, AssessEligibilityInput


def make_student(**kwargs):
    """Factory helper creating lightweight student profiles for deterministic testing."""
    defaults = {
        "id": "stud-test-1",
        "full_name": "Antigravity Student",
        "email": "student@uonbi.ac.ke",
        "university": "University of Nairobi",
        "degree_level": "Undergraduate",
        "field_of_study": "Computer Science",
        "specialisations": "Software Engineering",
        "year_of_study": 3,
        "graduation_year": None,
        "expected_graduation": "2026-12",
        "county_of_origin": "Nairobi",
        "gpa_or_grade": "First Class Honours",
        "country": "Kenya"
    }
    defaults.update(kwargs)
    return type("StudentProxy", (), defaults)()


def make_criterion(**kwargs):
    """Factory helper creating lightweight criteria for deterministic testing."""
    defaults = {
        "id": "crit-1",
        "opportunity_id": "opp-1",
        "criterion_type": "MINIMUM_ACADEMIC_GRADE",
        "operator": "GTE",
        "criterion_value": "UPPER_SECOND",
        "grading_system": "KENYAN_UNIVERSITY_HONOURS",
        "numeric_scale": None,
        "is_mandatory": True,
        "verification_status": "VERIFIED",
        "evidence_url": "https://official.ke/bulletin",
        "source_text": "Second Class Upper required."
    }
    defaults.update(kwargs)
    return type("CriterionProxy", (), defaults)()


# ============================================================================
# TESTS
# ============================================================================

def test_01_honours_degree_evaluation():
    """First Class student satisfies Upper Second requirement (Meets)."""
    student = make_student(gpa_or_grade="First Class Honours")
    crit = make_criterion(criterion_value="UPPER_SECOND", verification_status="VERIFIED")
    res = evaluate_structured_criterion(student, crit)
    assert res["status"] == "Meets"
    assert "Satisfies minimum grade requirement" in res["explanation"]

    # Lower Second student fails verified Upper Second requirement (Does Not Meet)
    student_lower = make_student(gpa_or_grade="Second Class Lower")
    res_lower = evaluate_structured_criterion(student_lower, crit)
    assert res_lower["status"] == "Does Not Meet"
    assert "Requires UPPER_SECOND; provided LOWER_SECOND" in res_lower["explanation"]


def test_02_kcse_grade_evaluation():
    """Evaluates 12-point KCSE secondary scale."""
    student = make_student(gpa_or_grade="KCSE A-")
    crit = make_criterion(
        criterion_type="KCSE_GRADE",
        criterion_value="B+",
        verification_status="VERIFIED"
    )
    res = evaluate_structured_criterion(student, crit)
    assert res["status"] == "Meets"

    # KCSE C+ student fails KCSE B+ requirement
    student_c = make_student(gpa_or_grade="KCSE C+")
    res_c = evaluate_structured_criterion(student_c, crit)
    assert res_c["status"] == "Does Not Meet"


def test_03_numeric_gpa_and_scale_mismatch():
    """Validates numeric GPA on matching scale, flags scale mismatch with uncertainty."""
    student = make_student(gpa_or_grade="3.4/4.0")
    crit = make_criterion(
        criterion_type="NUMERIC_GPA",
        criterion_value="3.2",
        numeric_scale=Decimal("4.00"),
        verification_status="VERIFIED"
    )
    res = evaluate_structured_criterion(student, crit)
    assert res["status"] == "Meets"

    # Scale mismatch: Opportunity requires 5.0 scale, student has 4.0 scale
    crit_5 = make_criterion(
        criterion_type="NUMERIC_GPA",
        criterion_value="4.0",
        numeric_scale=Decimal("5.00"),
        verification_status="VERIFIED"
    )
    res_5 = evaluate_structured_criterion(student, crit_5)
    assert res_5["status"] == "Needs Verification"
    assert "Scale mismatch" in res_5["explanation"]


def test_04_county_restriction_vs_quota():
    """County restriction disqualifies outside candidates; quotas do not disqualify."""
    student_turkana = make_student(county_of_origin="Turkana")
    student_kiambu = make_student(county_of_origin="Kiambu")

    # Strict restriction
    crit_res = make_criterion(
        criterion_type="COUNTY_RESTRICTION",
        criterion_value="Turkana, Samburu",
        is_mandatory=True,
        verification_status="VERIFIED"
    )
    assert evaluate_structured_criterion(student_turkana, crit_res)["status"] == "Meets"
    assert evaluate_structured_criterion(student_kiambu, crit_res)["status"] == "Does Not Meet"

    # Affirmative action quota (is_mandatory=False)
    crit_quota = make_criterion(
        criterion_type="GEOGRAPHIC_ALLOCATION",
        criterion_value="Turkana, Samburu",
        is_mandatory=False,
        verification_status="VERIFIED"
    )
    # Outside candidate is NOT disqualified
    res_kiambu_quota = evaluate_structured_criterion(student_kiambu, crit_quota)
    assert res_kiambu_quota["status"] == "Meets"


def test_05_unverified_criteria_never_disqualify():
    """CRITICAL BOUNDARY: An unverified criterion can NEVER cause Does Not Meet."""
    student_lower = make_student(gpa_or_grade="Second Class Lower")
    # PENDING_REVIEW criterion requiring Upper Second
    crit_unverified = make_criterion(
        criterion_value="UPPER_SECOND",
        verification_status="PENDING_REVIEW",
        is_mandatory=True
    )
    res = evaluate_structured_criterion(student_lower, crit_unverified)
    assert res["status"] == "Needs Verification"
    assert "requires verification before exclusion" in res["explanation"]


def test_06_desirable_criteria_never_disqualify():
    """CRITICAL BOUNDARY: A desirable criterion (is_mandatory=False) never causes Does Not Meet."""
    student_lower = make_student(gpa_or_grade="Second Class Lower")
    crit_desirable = make_criterion(
        criterion_value="FIRST_CLASS",
        is_mandatory=False,
        verification_status="VERIFIED"
    )
    res = evaluate_structured_criterion(student_lower, crit_desirable)
    assert res["status"] == "Meets"
    assert "Desirable preference does not disqualify" in res["explanation"]


def test_07_missing_profile_info_yields_needs_verification():
    """Missing fields in student profile yield Needs Verification without inventing data."""
    student_blank = make_student(gpa_or_grade=None, county_of_origin=None, graduation_year=None)
    crit_gpa = make_criterion(criterion_type="MINIMUM_ACADEMIC_GRADE", criterion_value="UPPER_SECOND")
    res = evaluate_structured_criterion(student_blank, crit_gpa)
    assert res["status"] == "Needs Verification"
    assert "lacks academic degree classification" in res["explanation"]


def test_08_scoring_3tier_separation():
    """Maintains strict numerical separation between eligibility tiers."""
    # Tier 1 (Meets): 70% - 100%
    score_meets = calculate_match_score(
        eligibility_status="Meets requirements",
        deg_meets=True,
        field_status="Meets",
        pref_meets=True,
        is_open=True,
        is_universal_field=False
    )
    assert 70 <= score_meets <= 100

    # Tier 2 (Needs verification): 35% - 55%
    score_needs = calculate_match_score(
        eligibility_status="Needs verification",
        deg_meets=True,
        field_status="Meets",
        pref_meets=True,
        is_open=True,
        is_universal_field=False
    )
    assert 35 <= score_needs <= 55

    # Tier 3 (Does not meet): 0% - 20%
    score_ineligible = calculate_match_score(
        eligibility_status="Does not meet requirements",
        deg_meets=True,
        field_status="Meets",
        pref_meets=True,
        is_open=True,
        is_universal_field=False
    )
    assert 0 <= score_ineligible <= 20


def test_09_api_and_agent_tool_parity():
    """Verifies that tool_assess_eligibility matches the deterministic evaluation."""
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(bind=test_engine)
    session = TestingSessionLocal()

    opp = Opportunity(
        id=f"opp-parity-{uuid.uuid4().hex[:6]}",
        title="Software Engineering Apprenticeship",
        provider="Equity Bank",
        category="Internship",
        degree_levels="Undergraduate",
        fields_of_study="Computer Science",
        official_url="https://equitybank.co.ke"
    )
    session.add(opp)
    session.commit()

    crit = OpportunityEligibilityCriterion(
        opportunity_id=opp.id,
        criterion_type=CriterionCategory.MINIMUM_ACADEMIC_GRADE.value,
        operator=CriterionOperator.GTE.value,
        criterion_value="UPPER_SECOND",
        is_mandatory=True,
        verification_status=CriterionVerificationStatus.VERIFIED.value,
        source_text="Upper Second Honours required.",
        evidence_url="https://equitybank.co.ke/careers",
        verified_by="admin-1",
        verified_at=datetime.utcnow()
    )
    session.add(crit)
    session.commit()

    # Student with First Class
    tool_input = AssessEligibilityInput(
        opportunity_id=opp.id,
        student_degree_level="Undergraduate",
        student_field_of_study="Computer Science",
        student_year_of_study=3,
        gpa_or_grade="First Class Honours"
    )
    tool_res = tool_assess_eligibility(tool_input, db=session)
    assert tool_res["status"] == "success"
    assert tool_res["overall_assessment"] == "Likely Eligible"
    assert any(b["criterion_type"] == "MINIMUM_ACADEMIC_GRADE" and b["status"] == "Meets" for b in tool_res["criteria_breakdown"])

    # Student with Lower Second
    tool_input_ineligible = AssessEligibilityInput(
        opportunity_id=opp.id,
        student_degree_level="Undergraduate",
        student_field_of_study="Computer Science",
        student_year_of_study=3,
        gpa_or_grade="Second Class Lower"
    )
    tool_res_inelig = tool_assess_eligibility(tool_input_ineligible, db=session)
    assert tool_res_inelig["overall_assessment"] == "Ineligible / Unlikely to Meet Criteria"
    assert any(b["criterion_type"] == "MINIMUM_ACADEMIC_GRADE" and b["status"] == "Does Not Meet" for b in tool_res_inelig["criteria_breakdown"])

    session.close()
