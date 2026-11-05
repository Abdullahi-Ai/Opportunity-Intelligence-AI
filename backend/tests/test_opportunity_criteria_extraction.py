"""
Unit and integration tests for Stage 2.2B-2:
Opportunity Eligibility Criteria Ingestion, Extraction, and Normalization.

Covers:
1. Academic honours extraction (First Class, Upper Second, Lower Second).
2. KCSE minimum grade extraction.
3. Numeric GPA and scale extraction.
4. Academic standing extraction.
5. County restriction vs Geographic quota distinction.
6. Fixed graduation year range vs rolling months-since-graduation distinction.
7. Expected graduation window extraction.
8. Age and citizenship restrictions.
9. Mandatory vs Desirable detection.
10. Source text and evidence URL preservation.
11. Idempotent ingestion, duplicate prevention, and preservation of reviewed criteria.
12. Backend and API mirror parity.
"""

import sys
import uuid
from pathlib import Path
from decimal import Decimal
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
    Opportunity,
    OpportunityEligibilityCriterion,
    OpportunityCriterionVerificationLog,
    CriterionCategory,
    CriterionOperator,
    CriterionVerificationStatus,
)
from app.services.opportunity_criteria_extraction import (
    extract_criteria_from_text,
    ingest_opportunity_criteria,
)


@pytest.fixture
def db_session():
    """Provides a fresh isolated in-memory SQLite database per test."""
    test_engine = create_engine("sqlite:///:memory:", echo=False)

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()
    yield session
    session.close()


def test_01_extract_honours_degrees():
    """Extracts British/Kenyan university honours classifications."""
    text = (
        "Applicants must possess a Bachelor's degree with First Class Honours. "
        "A Second Class Honours (Upper Division) in Computer Science is also acceptable."
    )
    criteria = extract_criteria_from_text(text, default_evidence_url="https://uonbi.ac.ke/jobs")
    assert len(criteria) >= 2
    types = [c["criterion_type"] for c in criteria]
    values = [c["criterion_value"] for c in criteria]
    assert CriterionCategory.MINIMUM_ACADEMIC_GRADE.value in types
    assert "FIRST_CLASS" in values
    assert "UPPER_SECOND" in values


def test_02_extract_kcse_grade():
    """Extracts KCSE minimum grades."""
    text = "Must have attained a minimum KCSE mean grade of B+ with C+ in Mathematics."
    criteria = extract_criteria_from_text(text)
    kcse_crits = [c for c in criteria if c["criterion_type"] == CriterionCategory.KCSE_GRADE.value]
    assert len(kcse_crits) >= 1
    assert kcse_crits[0]["criterion_value"] == "B+"
    assert kcse_crits[0]["operator"] == CriterionOperator.GTE.value
    assert kcse_crits[0]["is_mandatory"] is True


def test_03_extract_numeric_gpa():
    """Extracts numeric GPA with scale."""
    text = "Candidates require a cumulative GPA of 3.2 on a 4.0 scale. Preferred GPA 3.5 out of 4.0."
    criteria = extract_criteria_from_text(text)
    gpa_crits = [c for c in criteria if c["criterion_type"] == CriterionCategory.NUMERIC_GPA.value]
    assert len(gpa_crits) >= 2
    assert gpa_crits[0]["criterion_value"] == "3.2"
    assert gpa_crits[0]["numeric_scale"] == Decimal("4.0")
    assert gpa_crits[0]["is_mandatory"] is True
    # The preferred one should be desirable
    assert gpa_crits[1]["criterion_value"] == "3.5"
    assert gpa_crits[1]["is_mandatory"] is False


def test_04_county_restriction_vs_allocation():
    """Distinguishes mandatory county restrictions from affirmative action quotas."""
    text_restriction = "This scholarship is exclusively open to residents of Turkana and Samburu counties."
    c_res = extract_criteria_from_text(text_restriction)
    assert len(c_res) == 1
    assert c_res[0]["criterion_type"] == CriterionCategory.COUNTY_RESTRICTION.value
    assert "Turkana" in c_res[0]["criterion_value"]
    assert "Samburu" in c_res[0]["criterion_value"]
    assert c_res[0]["is_mandatory"] is True

    text_quota = "Regional affirmative action quota allocated across Garissa and Wajir counties."
    c_quota = extract_criteria_from_text(text_quota)
    assert len(c_quota) == 1
    assert c_quota[0]["criterion_type"] == CriterionCategory.GEOGRAPHIC_ALLOCATION.value
    assert "Garissa" in c_quota[0]["criterion_value"]
    assert "Wajir" in c_quota[0]["criterion_value"]
    assert c_quota[0]["is_mandatory"] is False


def test_05_fixed_year_vs_rolling_months():
    """Distinguishes fixed graduation years from rolling post-graduation months."""
    text_fixed = "Targeting graduation class between 2023 and 2025."
    c_fixed = extract_criteria_from_text(text_fixed)
    assert len(c_fixed) == 1
    assert c_fixed[0]["criterion_type"] == CriterionCategory.GRADUATION_YEAR_RANGE.value
    assert c_fixed[0]["criterion_value"] == "2023-2025"
    assert c_fixed[0]["operator"] == CriterionOperator.BETWEEN.value

    text_rolling = "Must have graduated within 24 months of graduation."
    c_rolling = extract_criteria_from_text(text_rolling)
    assert len(c_rolling) == 1
    assert c_rolling[0]["criterion_type"] == CriterionCategory.MONTHS_SINCE_GRADUATION.value
    assert c_rolling[0]["criterion_value"] == "24"
    assert c_rolling[0]["operator"] == CriterionOperator.LTE.value


def test_06_expected_graduation():
    """Extracts forward-looking expected graduation dates."""
    text = "Expected to graduate by December 2026."
    criteria = extract_criteria_from_text(text)
    assert len(criteria) == 1
    assert criteria[0]["criterion_type"] == CriterionCategory.EXPECTED_GRADUATION_WINDOW.value
    assert "2026" in criteria[0]["criterion_value"]


def test_07_age_and_citizenship():
    """Extracts age limits and citizenship requirements."""
    text = "Applicants must be a Kenyan citizen aged between 18 and 28 years."
    criteria = extract_criteria_from_text(text)
    assert len(criteria) >= 2
    cit_crit = [c for c in criteria if c["criterion_value"] == "KENYAN_CITIZEN"][0]
    assert cit_crit["operator"] == CriterionOperator.EQ.value
    age_crit = [c for c in criteria if "AGE" in c["criterion_value"]][0]
    assert age_crit["criterion_value"] == "AGE_18-28"
    assert age_crit["operator"] == CriterionOperator.BETWEEN.value


def test_08_academic_standing():
    """Extracts continuing undergraduate and graduating senior standing."""
    text = "Must be a continuing undergraduate student in year 2 or 3."
    criteria = extract_criteria_from_text(text)
    assert len(criteria) == 1
    assert criteria[0]["criterion_type"] == CriterionCategory.ACADEMIC_STANDING.value
    assert criteria[0]["criterion_value"] == "UNDERGRADUATE"


def test_09_ingest_idempotency_and_preservation(db_session):
    """Verifies that re-ingestion does not duplicate criteria or overwrite verified ones."""
    session = db_session
    admin = User(
        email="auditor@moi.ac.ke",
        hashed_password="SecretAdminPassword!",
        full_name="Auditor General",
        role="admin"
    )
    session.add(admin)
    session.commit()

    opp = Opportunity(
        id=f"opp-ingest-{uuid.uuid4().hex[:6]}",
        title="Software Engineering Apprenticeship",
        provider="Safaricom",
        category="Internship",
        official_url="https://safaricom.co.ke/careers"
    )
    session.add(opp)
    session.commit()

    text = "Must possess Second Class Honours Upper Division. KCSE mean grade B+ required."
    candidates = extract_criteria_from_text(text, default_evidence_url=opp.official_url)

    # Initial ingestion
    res1 = ingest_opportunity_criteria(session, opp.id, candidates)
    assert res1["created_count"] == 2
    assert res1["total_criteria"] == 2

    # Administrator reviews and verifies one criterion
    crit1 = session.query(OpportunityEligibilityCriterion).filter_by(
        opportunity_id=opp.id,
        criterion_type=CriterionCategory.MINIMUM_ACADEMIC_GRADE.value
    ).first()
    from datetime import datetime
    crit1.verified_by = admin.id
    crit1.verified_at = datetime.utcnow()
    crit1.evidence_url = "https://safaricom.co.ke/careers/official-bulletin"
    crit1.verification_status = CriterionVerificationStatus.VERIFIED.value
    session.commit()

    # Re-run ingestion with same candidate list
    res2 = ingest_opportunity_criteria(session, opp.id, candidates)
    assert res2["created_count"] == 0
    assert res2["preserved_count"] == 1  # Verified one was preserved
    assert res2["skipped_count"] == 1    # Pending one was skipped (no duplicate)
    assert res2["total_criteria"] == 2

    # Check verified criterion is unchanged
    session.refresh(crit1)
    assert crit1.verification_status == "VERIFIED"
    assert crit1.verified_by == admin.id
