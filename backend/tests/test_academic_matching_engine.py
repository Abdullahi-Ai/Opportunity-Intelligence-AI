"""
Automated Test Suite for Deterministic Academic Matching Engine (Phase 2 — Stage 2.1).

Validates:
A. Degree matching correctness (Undergraduate vs Graduate, Diploma vs Advanced Diploma, Masters vs Undergraduate, PhD vs Masters, aliases).
B. Field-of-study precision (Exact match, aliases, token collision prevention: Political Science vs Public Health, Computer Science vs Environmental Science).
C. Academic year & student standing evaluation (Industrial attachments, final-year schemes, graduate trainees, unconstrained).
D. Scoring methodology & 3-tier numerical separation (100% reachable, All Fields unpenalized, Ineligible capped at 0-20%, Needs Verification 35-55%).
E. Deterministic 4-tier sorting stability and reproducibility.
F. End-to-end API integration and Phase 1 verification preservation.
"""

import uuid
from datetime import datetime, timedelta, date
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, engine, SessionLocal
from app.models.entities import User, StudentProfile, Opportunity, TrackedApplication, VerificationStatus
from app.services.matching_engine import (
    CanonicalDegree,
    normalize_degree_level,
    evaluate_degree_level,
    normalize_field_name,
    evaluate_field_of_study,
    evaluate_academic_year_and_standing,
    calculate_match_score,
    get_match_sort_key,
)

client = TestClient(app)


# Setup fixture: ensures clean SQLite schema in isolated test session
@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    # No teardown necessary for in-memory SQLite


# Helper to create test student
def create_test_student(db, name_prefix="student", degree="Undergraduate", field="Computer Science", year=3, prefs="Internship"):
    user_id = str(uuid.uuid4())
    student_id = str(uuid.uuid4())
    email = f"{name_prefix}_{user_id[:8]}@uonbi.ac.ke"

    user = User(
        id=user_id,
        email=email,
        hashed_password="TestHashedPassword123!",
        full_name=f"Test {name_prefix.title()}",
        role="student",
        is_active=True
    )
    db.add(user)

    student = StudentProfile(
        id=student_id,
        user_id=user_id,
        email=email,
        full_name=f"Test {name_prefix.title()}",
        university="University of Nairobi",
        field_of_study=field,
        degree_level=degree,
        year_of_study=year,
        preferred_categories=prefs,
        country="Kenya"
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student, user


# =========================================================================
# CATEGORY A: DEGREE LEVEL MATCHING TESTS
# =========================================================================

def test_degree_matching_undergraduate_vs_graduate_negative():
    """Undergraduate must NOT match Graduate / Postgraduate requirements."""
    meets, status, reason = evaluate_degree_level("Undergraduate", "Graduate")
    assert not meets
    assert status == "Does Not Meet"

    meets_rev, status_rev, _ = evaluate_degree_level("Graduate", "Undergraduate")
    assert not meets_rev
    assert status_rev == "Does Not Meet"


def test_degree_matching_diploma_vs_advanced_diploma_negative():
    """Ordinary Diploma must NOT falsely match Advanced Diploma."""
    meets, status, reason = evaluate_degree_level("Diploma", "Advanced Diploma")
    assert not meets
    assert status == "Does Not Meet"

    meets_rev, status_rev, _ = evaluate_degree_level("Advanced Diploma", "Diploma")
    assert not meets_rev
    assert status_rev == "Does Not Meet"


def test_degree_matching_masters_vs_undergraduate_negative():
    """Masters degree must NOT match Undergraduate requirements and vice versa."""
    meets, status, _ = evaluate_degree_level("Masters", "Undergraduate")
    assert not meets
    assert status == "Does Not Meet"

    meets_rev, status_rev, _ = evaluate_degree_level("Undergraduate", "Masters")
    assert not meets_rev
    assert status_rev == "Does Not Meet"


def test_degree_matching_phd_vs_masters_negative():
    """Doctoral / PhD degree must NOT match Masters requirements and vice versa."""
    meets, status, _ = evaluate_degree_level("PhD", "Masters")
    assert not meets
    assert status == "Does Not Meet"

    meets_rev, status_rev, _ = evaluate_degree_level("Masters", "PhD")
    assert not meets_rev
    assert status_rev == "Does Not Meet"


@pytest.mark.parametrize("input_alias,expected_canonical", [
    ("Undergraduate", CanonicalDegree.UNDERGRADUATE),
    ("undergrad", CanonicalDegree.UNDERGRADUATE),
    ("bachelor", CanonicalDegree.UNDERGRADUATE),
    ("Bachelor's Degree", CanonicalDegree.UNDERGRADUATE),
    ("B.Sc.", CanonicalDegree.UNDERGRADUATE),
    ("BSc", CanonicalDegree.UNDERGRADUATE),
    ("B.A.", CanonicalDegree.UNDERGRADUATE),
    ("BEng", CanonicalDegree.UNDERGRADUATE),
    ("BCom", CanonicalDegree.UNDERGRADUATE),
    ("LLB", CanonicalDegree.UNDERGRADUATE),
    ("Masters", CanonicalDegree.POSTGRADUATE_MASTERS),
    ("M.Sc", CanonicalDegree.POSTGRADUATE_MASTERS),
    ("MSc", CanonicalDegree.POSTGRADUATE_MASTERS),
    ("MBA", CanonicalDegree.POSTGRADUATE_MASTERS),
    ("Postgraduate", CanonicalDegree.POSTGRADUATE_MASTERS),
    ("Post-Graduate", CanonicalDegree.POSTGRADUATE_MASTERS),
    ("PhD", CanonicalDegree.DOCTORAL_PHD),
    ("Doctorate", CanonicalDegree.DOCTORAL_PHD),
    ("Doctoral", CanonicalDegree.DOCTORAL_PHD),
    ("DPhil", CanonicalDegree.DOCTORAL_PHD),
    ("Diploma", CanonicalDegree.DIPLOMA),
    ("Ordinary Diploma", CanonicalDegree.DIPLOMA),
    ("National Diploma", CanonicalDegree.DIPLOMA),
    ("Higher National Diploma", CanonicalDegree.ADVANCED_DIPLOMA),
    ("Advanced Diploma", CanonicalDegree.ADVANCED_DIPLOMA),
    ("HND", CanonicalDegree.ADVANCED_DIPLOMA),
    ("Certificate", CanonicalDegree.CERTIFICATE),
    ("KCSE", CanonicalDegree.SECONDARY_SCHOOL),
])
def test_degree_canonical_normalization_aliases(input_alias, expected_canonical):
    canonical, _ = normalize_degree_level(input_alias)
    assert canonical == expected_canonical


def test_degree_matching_empty_or_all_degrees():
    """Unrestricted or empty degree level requirements must evaluate as Meets."""
    meets, status, _ = evaluate_degree_level("Undergraduate", None)
    assert meets and status == "Meets"

    meets, status, _ = evaluate_degree_level("Undergraduate", "")
    assert meets and status == "Meets"

    meets, status, _ = evaluate_degree_level("Masters", "All Degree Levels")
    assert meets and status == "Meets"

    meets, status, _ = evaluate_degree_level("Diploma", "Open to All")
    assert meets and status == "Meets"


def test_degree_matching_unknown_values_handled_safely():
    """Unrecognized or missing student degree values must return Needs Verification."""
    meets, status, _ = evaluate_degree_level(None, "Undergraduate")
    assert not meets and status == "Needs Verification"

    meets, status, _ = evaluate_degree_level("", "Undergraduate")
    assert not meets and status == "Needs Verification"

    meets, status, _ = evaluate_degree_level("Guild Apprenticeship Level 7", "Undergraduate")
    assert not meets and status == "Needs Verification"


# =========================================================================
# CATEGORY B: FIELD OF STUDY MATCHING TESTS
# =========================================================================

def test_field_matching_exact():
    """Exact field of study match must evaluate as Meets."""
    meets, status, reason = evaluate_field_of_study("Computer Science", None, "Computer Science, Software Engineering")
    assert meets
    assert status == "Meets"
    assert "Computer Science" in reason


def test_field_matching_aliases():
    """Valid academic field aliases must evaluate as Meets."""
    meets, status, _ = evaluate_field_of_study("CS", None, "Computer Science")
    assert meets and status == "Meets"

    meets, status, _ = evaluate_field_of_study("SE", None, "Software Engineering")
    assert meets and status == "Meets"

    meets, status, _ = evaluate_field_of_study("IT", None, "Information Technology")
    assert meets and status == "Meets"

    meets, status, _ = evaluate_field_of_study("MBChB", None, "Medicine and Surgery")
    assert meets and status == "Meets"


def test_field_matching_token_collision_political_science_vs_public_health():
    """Political Science must NOT match Public Health despite sharing words or categories."""
    meets, status, _ = evaluate_field_of_study("Political Science", None, "Public Health")
    assert not meets
    assert status == "Does Not Meet"


def test_field_matching_token_collision_computer_science_vs_environmental_science():
    """Computer Science must NOT match Environmental Science despite sharing 'Science'."""
    meets, status, _ = evaluate_field_of_study("Computer Science", None, "Environmental Science, Forestry")
    assert not meets
    assert status == "Does Not Meet"

    meets_rev, status_rev, _ = evaluate_field_of_study("Environmental Science", None, "Computer Science, Software Engineering")
    assert not meets_rev
    assert status_rev == "Does Not Meet"


def test_field_matching_cluster_equivalence():
    """Fields within the same academic cluster must be recognized as Meets."""
    # Both Software Engineering and Computer Science belong to COMPUTING_AND_TECH cluster
    meets, status, reason = evaluate_field_of_study("Software Engineering", None, "Computer Science")
    assert meets
    assert status == "Meets"
    assert "Computing And Tech" in reason or "Software Engineering" in reason


def test_field_matching_interdisciplinary_needs_verification():
    """Interdisciplinary courses (e.g. Environmental Economics vs Economics) return Needs Verification."""
    meets, status, reason = evaluate_field_of_study("Environmental Economics", None, "Economics")
    assert not meets
    assert status == "Needs Verification"
    assert "verification" in reason.lower()


def test_field_matching_all_fields_unrestricted():
    """All Fields or unspecified disciplines must evaluate as Meets."""
    meets, status, _ = evaluate_field_of_study("Political Science", None, "All Fields")
    assert meets and status == "Meets"

    meets, status, _ = evaluate_field_of_study("Fine Arts", None, "All Academic Disciplines")
    assert meets and status == "Meets"

    meets, status, _ = evaluate_field_of_study("Computer Science", None, None)
    assert meets and status == "Meets"


def test_field_matching_missing_student_field():
    """Missing student field in profile must evaluate as Needs Verification."""
    meets, status, _ = evaluate_field_of_study(None, None, "Computer Science")
    assert not meets and status == "Needs Verification"


# =========================================================================
# CATEGORY C: ELIGIBILITY EVALUATION & ACADEMIC YEAR TESTS
# =========================================================================

def test_eligibility_continuing_attachment_years_2_3_4_meets():
    """Continuing industrial attachment allows 2nd, 3rd, and 4th year students."""
    for yr in [2, 3, 4]:
        meets, status, _, crit = evaluate_academic_year_and_standing(
            student_year=yr,
            opp_title="Safaricom Industrial Attachment Programme",
            opp_id="opp-safaricom-attachment-2026",
            target_audience="Continuing 2nd, 3rd, and 4th year university students in Kenya seeking mandatory industrial attachment",
            category="Internship"
        )
        assert meets
        assert status == "Meets"
        assert crit is not None
        assert crit["status"] == "Meets"


def test_eligibility_continuing_attachment_year_1_does_not_meet():
    """1st year students are NOT eligible for continuing industrial attachment."""
    meets, status, _, crit = evaluate_academic_year_and_standing(
        student_year=1,
        opp_title="Safaricom Industrial Attachment Programme",
        opp_id="opp-safaricom-attachment-2026",
        target_audience="Continuing 2nd, 3rd, and 4th year university students in Kenya seeking mandatory industrial attachment",
        category="Internship"
    )
    assert not meets
    assert status == "Does Not Meet"
    assert crit is not None
    assert crit["status"] == "Does Not Meet"


def test_eligibility_final_year_standing():
    """Final year requirement is met by year 4 and 5, rejected for years 1-2."""
    meets, status, _, _ = evaluate_academic_year_and_standing(
        student_year=4,
        opp_title="UN Gigiri Internship",
        opp_id="opp-un-gigiri-internship-2026",
        target_audience="Final year undergraduate or enrolled graduate students",
        category="Internship"
    )
    assert meets and status == "Meets"

    meets_y1, status_y1, _, _ = evaluate_academic_year_and_standing(
        student_year=1,
        opp_title="UN Gigiri Internship",
        opp_id="opp-un-gigiri-internship-2026",
        target_audience="Final year undergraduate or enrolled graduate students",
        category="Internship"
    )
    assert not meets_y1 and status_y1 == "Does Not Meet"


def test_eligibility_graduate_trainee_standing():
    """Graduate trainee schemes reject continuing early-stage undergraduates."""
    meets_y2, status_y2, _, _ = evaluate_academic_year_and_standing(
        student_year=2,
        opp_title="Presidential Digital Talent Programme",
        opp_id="opp-pdtp-digika-2026",
        target_audience="Fresh Kenyan university graduates in ICT",
        category="Graduate Trainee"
    )
    assert not meets_y2 and status_y2 == "Does Not Meet"


def test_eligibility_unconstrained_opportunity():
    """Opportunities without academic year restrictions do not penalize students."""
    meets, status, _, crit = evaluate_academic_year_and_standing(
        student_year=1,
        opp_title="Higher Education Financing (HEF) Scholarship",
        opp_id="opp-hef-undergraduate-2026",
        target_audience="Kenyan undergraduate students placed by KUCCPS",
        category="Scholarship"
    )
    assert meets and status == "Meets"
    assert crit is None


# =========================================================================
# CATEGORY D: SCORING METHODOLOGY & 3-TIER NUMERICAL SEPARATION
# =========================================================================

def test_scoring_fully_eligible_reaches_100():
    """Fully eligible student satisfying course, degree, category, and deadline must achieve 100%."""
    score = calculate_match_score(
        eligibility_status="Meets requirements",
        deg_meets=True,
        field_status="Meets",
        pref_meets=True,
        is_open=True,
        is_universal_field=False
    )
    assert score == 100, f"Expected 100%, got {score}%"


def test_scoring_all_fields_unpenalized_reaches_100():
    """All Fields opportunities must receive full field credit and reach 100%."""
    score = calculate_match_score(
        eligibility_status="Meets requirements",
        deg_meets=True,
        field_status="Meets",
        pref_meets=True,
        is_open=True,
        is_universal_field=True
    )
    assert score == 100, f"All Fields opportunity did not reach 100%: got {score}%"


def test_scoring_ineligible_opportunity_capped():
    """Ineligible opportunities must never receive misleadingly high scores (capped at 20%)."""
    score = calculate_match_score(
        eligibility_status="Does not meet requirements",
        deg_meets=True,
        field_status="Meets",
        pref_meets=True,
        is_open=True,
        is_universal_field=False
    )
    assert score <= 20, f"Ineligible opportunity score too high: {score}%"

    score_total_mismatch = calculate_match_score(
        eligibility_status="Does not meet requirements",
        deg_meets=False,
        field_status="Does Not Meet",
        pref_meets=False,
        is_open=False,
        is_universal_field=False
    )
    assert score_total_mismatch == 0


def test_scoring_needs_verification_tier_separation():
    """Needs Verification scores (35-55%) must remain strictly between Ineligible (<=20%) and Meets (>=70%)."""
    score_nv_max = calculate_match_score(
        eligibility_status="Needs verification",
        deg_meets=True,
        field_status="Needs Verification",
        pref_meets=True,
        is_open=True,
        is_universal_field=False
    )
    assert 35 <= score_nv_max <= 55

    score_nv_min = calculate_match_score(
        eligibility_status="Needs verification",
        deg_meets=False,
        field_status="Needs Verification",
        pref_meets=False,
        is_open=False,
        is_universal_field=False
    )
    assert 35 <= score_nv_min <= 55

    # Ineligible max < Needs Verification min
    score_ineligible_max = calculate_match_score(
        eligibility_status="Does not meet requirements",
        deg_meets=True,
        field_status="Meets",
        pref_meets=True,
        is_open=True,
        is_universal_field=True
    )
    assert score_ineligible_max < score_nv_min, f"Score inversion: Ineligible ({score_ineligible_max}) >= NV ({score_nv_min})"


def test_scoring_reproducibility():
    """Scoring calculation must be strictly reproducible and deterministic."""
    inputs = ("Meets requirements", True, "Meets", True, True, False)
    scores = [calculate_match_score(*inputs) for _ in range(20)]
    assert all(s == scores[0] for s in scores)


# =========================================================================
# CATEGORY E: DETERMINISTIC 4-TIER SORTING TESTS
# =========================================================================

def test_deterministic_sorting_tier_hierarchy():
    """Sorting key must place Meets before Needs Verification before Does Not Meet."""
    now = datetime.utcnow()

    key_meets = get_match_sort_key("Meets requirements", 75, 10, now, "opp-1")
    key_nv = get_match_sort_key("Needs verification", 50, 2, now, "opp-2")
    key_dnm = get_match_sort_key("Does not meet requirements", 20, 1, now, "opp-3")

    assert key_meets < key_nv < key_dnm


def test_deterministic_sorting_score_within_tier():
    """Within the same tier, higher match score ranks ahead of lower match score."""
    now = datetime.utcnow()

    key_100 = get_match_sort_key("Meets requirements", 100, 10, now, "opp-a")
    key_85 = get_match_sort_key("Meets requirements", 85, 10, now, "opp-b")

    assert key_100 < key_85


def test_deterministic_sorting_deadline_urgency():
    """Within same tier and score, more urgent deadline (fewer days left) ranks first."""
    now = datetime.utcnow()

    key_urgent = get_match_sort_key("Meets requirements", 95, 3, now, "opp-urgent")
    key_relaxed = get_match_sort_key("Meets requirements", 95, 30, now, "opp-relaxed")

    assert key_urgent < key_relaxed


def test_deterministic_sorting_reproducibility():
    """Sorting identical sets of records yields the exact same permutation every time."""
    now = datetime.utcnow()
    records = [
        ("Meets requirements", 90, 5, now, "opp-1"),
        ("Needs verification", 50, 2, now, "opp-2"),
        ("Meets requirements", 100, 15, now, "opp-3"),
        ("Does not meet requirements", 15, 1, now, "opp-4"),
        ("Meets requirements", 90, 2, now, "opp-5"),
    ]

    sorted_runs = []
    for _ in range(10):
        s = sorted(records, key=lambda r: get_match_sort_key(*r))
        sorted_runs.append([r[4] for r in s])

    for i in range(1, len(sorted_runs)):
        assert sorted_runs[i] == sorted_runs[0]


# =========================================================================
# CATEGORY F: ENDPOINT INTEGRATION & PHASE 1 PRESERVATION TESTS
# =========================================================================

def test_matches_endpoint_integration_and_phase1_preservation():
    """Tests /api/v1/matches endpoint with authenticated student and verifies Phase 1 attributes."""
    db = SessionLocal()
    try:
        # Seed test student
        student, user = create_test_student(
            db,
            name_prefix="cs_eval",
            degree="Undergraduate",
            field="Computer Science",
            year=3,
            prefs="Internship,Scholarship"
        )

        # Seed 3 explicit opportunities with Phase 1 verification attributes
        opp_meets = Opportunity(
            id="test-opp-safaricom-attachment",
            title="Safaricom Attachment Test",
            provider="Safaricom PLC",
            category="Internship",
            target_audience="Continuing 2nd, 3rd, and 4th year university students",
            fields_of_study="Computer Science, Software Engineering",
            degree_levels="Undergraduate",
            official_url="https://www.safaricom.co.ke/careers",
            application_deadline="2026-11-30",
            status="open",
            is_verified=True,
            verification_status=VerificationStatus.VERIFIED.value
        )
        opp_all_fields = Opportunity(
            id="test-opp-hef-all-fields",
            title="HEF Scholarship Test",
            provider="Universities Fund",
            category="Scholarship",
            target_audience="Kenyan undergraduate students",
            fields_of_study="All Fields",
            degree_levels="Undergraduate",
            official_url="https://www.hef.co.ke",
            application_deadline="2026-12-31",
            status="open",
            is_verified=True,
            verification_status=VerificationStatus.VERIFIED.value
        )
        opp_ineligible = Opportunity(
            id="test-opp-masters-chevening",
            title="Chevening Masters Test",
            provider="UK FCDO",
            category="Scholarship",
            target_audience="Graduates seeking Master's degree in UK",
            fields_of_study="Public Policy, Law",
            degree_levels="Masters",
            official_url="https://www.chevening.org",
            application_deadline="2026-11-05",
            status="open",
            is_verified=True,
            verification_status=VerificationStatus.VERIFIED.value
        )
        db.merge(opp_meets)
        db.merge(opp_all_fields)
        db.merge(opp_ineligible)
        db.commit()

        # Login student to get auth token
        from app.core.security import create_access_token
        token = create_access_token(subject=user.id, role=user.role)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/v1/matches", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()

        assert "matches" in data
        matches = data["matches"]
        assert len(matches) >= 3

        opp_map = {m["opportunity_id"]: m for m in matches}

        # 1. Verify opp_meets (Computer Science 3rd Year Undergraduate) -> Meets, 100%
        item_meets = opp_map.get("test-opp-safaricom-attachment")
        assert item_meets is not None
        assert item_meets["eligibility_status"] == "Meets requirements"
        assert item_meets["match_score"] == 100
        assert item_meets["is_verified"] is True
        assert item_meets["verification_status"] == "VERIFIED"

        # 2. Verify opp_all_fields -> Meets, 100% (All fields unpenalized)
        item_all = opp_map.get("test-opp-hef-all-fields")
        assert item_all is not None
        assert item_all["eligibility_status"] == "Meets requirements"
        assert item_all["match_score"] == 100
        assert item_all["is_verified"] is True
        assert item_all["verification_status"] == "VERIFIED"

        # 3. Verify opp_ineligible (Undergraduate student applying to Masters) -> Does not meet, <= 20%
        item_inel = opp_map.get("test-opp-masters-chevening")
        assert item_inel is not None
        assert item_inel["eligibility_status"] == "Does not meet requirements"
        assert item_inel["match_score"] <= 20

        # 4. Verify sorting: Meets items must appear before Ineligible items
        indices = {m["opportunity_id"]: idx for idx, m in enumerate(matches)}
        assert indices["test-opp-safaricom-attachment"] < indices["test-opp-masters-chevening"]
        assert indices["test-opp-hef-all-fields"] < indices["test-opp-masters-chevening"]

        # 5. Verify criteria breakdown structure
        for crit in item_meets["criteria_breakdown"]:
            assert "criterion" in crit
            assert "required" in crit
            assert "provided" in crit
            assert "status" in crit
            assert crit["status"] in ["Meets", "Needs Verification", "Does Not Meet"]

    finally:
        db.close()
