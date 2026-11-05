"""
Opportunity Eligibility Criteria Ingestion, Extraction, and Normalization Service.

Phase 2 — Stage 2.2B-2 Implementation.
Converts unstructured or semi-structured opportunity eligibility text into typed,
deterministic OpportunityEligibilityCriterion records.

Semantic Rules:
1. Distinguishes actual county restrictions from county quotas / geographic allocations.
2. Distinguishes actual graduation from expected graduation.
3. Distinguishes fixed graduation years from rolling months-since-graduation windows.
4. Preserves exact source excerpt and authoritative evidence URL.
5. Distinguishes mandatory requirements from desirable preferences.
6. Ambiguous requirements default to NEEDS_REVIEW or PENDING_REVIEW; never auto-verified.
7. Reprocessing is idempotent and strictly preserves administrator-reviewed criteria.
"""

import re
import uuid
import json
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session

from app.models.entities import (
    Opportunity,
    OpportunityEligibilityCriterion,
    OpportunityCriterionVerificationLog,
    CriterionCategory,
    CriterionOperator,
    CriterionVerificationStatus,
)
from app.services.academic_profile_normalization import (
    normalize_academic_grade,
    normalize_county,
    GradingSystem,
    CanonicalHonours,
    CanonicalKCSE,
    KENYA_COUNTIES,
)


# ============================================================================
# EXTRACTION PATTERNS AND REGEXES
# ============================================================================

DESIRABLE_INDICATORS = [
    r"\bprefer(?:red|able)?\b",
    r"\bdesir(?:ed|able)\b",
    r"\badded advantage\b",
    r"\bbonus\b",
    r"\bplus\b",
    r"\ban asset\b",
    r"\badvantageous\b",
    r"\boptional\b",
]

MANDATORY_INDICATORS = [
    r"\bmust\b",
    r"\brequir(?:ed|ement|es)\b",
    r"\bminimum\b",
    r"\bmandatory\b",
    r"\bessential\b",
    r"\bshall\b",
    r"\beligible only\b",
    r"\bstrictly\b",
]

# Honours Degrees
HONOURS_PATTERNS = [
    (r"\b(?:1st|first)\s*class(?:\s*(?:honours|honors))?\b", CanonicalHonours.FIRST_CLASS.value, "First Class Honours required"),
    (r"\b(?:2nd|second)\s*class(?:\s*(?:honours|honors))?[\s,\(]*(?:upper|division\s*(?:one|1))\b|\bupper\s*second\b", CanonicalHonours.UPPER_SECOND.value, "Second Class Honours (Upper Division) required"),
    (r"\b(?:2nd|second)\s*class(?:\s*(?:honours|honors))?[\s,\(]*(?:lower|division\s*(?:two|2))\b|\blower\s*second\b", CanonicalHonours.LOWER_SECOND.value, "Second Class Honours (Lower Division) required"),
    (r"\bpass\s*degree\b|\bminimum\s*pass\b", CanonicalHonours.PASS.value, "Pass degree required"),
]

# KCSE Grades
KCSE_REGEX = re.compile(
    r"\b(?:kcse|k\.c\.s\.e\.?)\s*(?:mean\s*grade\s*(?:of)?)?\s*([A-E][+-]?)\s*(?:and\s*above|or\s*above|\+)?\b",
    re.IGNORECASE
)

# Numeric GPA
GPA_REGEX = re.compile(
    r"\b(?:gpa|grade\s*point\s*average)\s*(?:of\s*)?([0-9]\.[0-9]{1,2})\s*(?:(?:/|\s*out\s*of\s*)([0-9]\.[0-9]{1,2}))?\b",
    re.IGNORECASE
)

# Months Since Graduation
MONTHS_SINCE_GRAD_REGEX = re.compile(
    r"\b(?:within|graduated\s*within|not\s*more\s*than)\s*([0-9]{1,2})\s*months?\s*(?:of|since|post)?\s*graduation\b",
    re.IGNORECASE
)

# Fixed Graduation Year Range
GRAD_YEAR_RANGE_REGEX = re.compile(
    r"\b(?:graduated|graduation\s*class(?:\s*of)?|class\s*of)\s*(?:between\s*)?(20[1-3][0-9])\s*(?:and|to|-)\s*(20[1-3][0-9])\b",
    re.IGNORECASE
)

# Expected Graduation
EXPECTED_GRAD_REGEX = re.compile(
    r"\bexpected\s*(?:to\s*)?graduat(?:e|ing|ion)\s*(?:by|in|between)?\s*([A-Za-z]+)?\s*(20[2-3][0-9])\b",
    re.IGNORECASE
)

# Age restrictions
AGE_REGEX = re.compile(
    r"\b(?:aged?|between)\s*([0-9]{2})\s*(?:and|to|-)\s*([0-9]{2})\s*years?(?:\s*of\s*age)?\b|\b(?:not\s*older\s*than|below|under|maximum\s*age\s*of)\s*([0-9]{2})\s*years?\b",
    re.IGNORECASE
)

# Citizenship
CITIZENSHIP_REGEX = re.compile(
    r"\b(?:kenyan\s*citizen(?:ship)?|kenyan\s*national|citizen\s*of\s*kenya)\b",
    re.IGNORECASE
)

# Academic Standing
STANDING_PATTERNS = [
    (r"\b(?:continuing|current)\s*undergraduate(?:\s*student)?\b|\bundergraduate\s*students?\s*only\b", "UNDERGRADUATE"),
    (r"\b(?:final\s*year|graduating\s*senior|fourth\s*year|4th\s*year)\b", "GRADUATING_SENIOR"),
    (r"\b(?:postgraduate|master'?s|phd|doctoral)\s*students?\b", "POSTGRADUATE"),
    (r"\b(?:recent\s*graduates?|alumni)\b", "ALUMNI"),
]


def _is_desirable(sentence: str) -> bool:
    """Checks whether the excerpt expresses a desirable preference rather than a mandatory requirement."""
    for pattern in DESIRABLE_INDICATORS:
        if re.search(pattern, sentence, re.IGNORECASE):
            return True
    return False


def extract_criteria_from_text(
    text: str,
    default_evidence_url: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Deterministically parses free-text requirements and returns candidate criterion dictionaries.
    Preserves exact source sentences, determines mandatory vs desirable, and sets appropriate
    categories and operators.
    """
    if not text or not text.strip():
        return []

    results: List[Dict[str, Any]] = []
    # Split text into sentences / bullet points for granular provenance
    raw_sentences = re.split(r"(?:[\r\n]+|[•\-\*]\s*|\.\s+)", text)
    sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 5]

    for sentence in sentences:
        is_desirable = _is_desirable(sentence)
        is_mandatory = not is_desirable

        # 1. Academic Honours Classification
        for pattern, canonical_val, default_note in HONOURS_PATTERNS:
            if re.search(pattern, sentence, re.IGNORECASE):
                results.append({
                    "criterion_type": CriterionCategory.MINIMUM_ACADEMIC_GRADE.value,
                    "operator": CriterionOperator.GTE.value,
                    "criterion_value": canonical_val,
                    "grading_system": GradingSystem.KENYAN_UNIVERSITY_HONOURS.value,
                    "numeric_scale": None,
                    "is_mandatory": is_mandatory,
                    "source_text": sentence,
                    "evidence_url": default_evidence_url,
                    "verification_status": CriterionVerificationStatus.PENDING_REVIEW.value,
                })
                break

        # 2. KCSE Mean Grade
        kcse_match = KCSE_REGEX.search(sentence)
        if kcse_match:
            raw_grade = kcse_match.group(1).upper()
            norm = normalize_academic_grade(f"KCSE {raw_grade}")
            grade_val = norm.normalized_classification or raw_grade
            results.append({
                "criterion_type": CriterionCategory.KCSE_GRADE.value,
                "operator": CriterionOperator.GTE.value,
                "criterion_value": grade_val,
                "grading_system": GradingSystem.KCSE.value,
                "numeric_scale": None,
                "is_mandatory": is_mandatory,
                "source_text": sentence,
                "evidence_url": default_evidence_url,
                "verification_status": CriterionVerificationStatus.PENDING_REVIEW.value,
            })

        # 3. Numeric GPA
        gpa_match = GPA_REGEX.search(sentence)
        if gpa_match:
            gpa_val = gpa_match.group(1)
            scale_val = gpa_match.group(2) or "4.00"
            results.append({
                "criterion_type": CriterionCategory.NUMERIC_GPA.value,
                "operator": CriterionOperator.GTE.value,
                "criterion_value": gpa_val,
                "grading_system": GradingSystem.NUMERIC_GPA.value,
                "numeric_scale": Decimal(scale_val),
                "is_mandatory": is_mandatory,
                "source_text": sentence,
                "evidence_url": default_evidence_url,
                "verification_status": CriterionVerificationStatus.PENDING_REVIEW.value,
            })

        # 4. Months Since Graduation (Rolling Window)
        months_match = MONTHS_SINCE_GRAD_REGEX.search(sentence)
        if months_match:
            months = months_match.group(1)
            results.append({
                "criterion_type": CriterionCategory.MONTHS_SINCE_GRADUATION.value,
                "operator": CriterionOperator.LTE.value,
                "criterion_value": months,
                "grading_system": None,
                "numeric_scale": None,
                "is_mandatory": is_mandatory,
                "source_text": sentence,
                "evidence_url": default_evidence_url,
                "verification_status": CriterionVerificationStatus.PENDING_REVIEW.value,
            })

        # 5. Fixed Graduation Year Range
        grad_range_match = GRAD_YEAR_RANGE_REGEX.search(sentence)
        if grad_range_match:
            y_start = grad_range_match.group(1)
            y_end = grad_range_match.group(2)
            results.append({
                "criterion_type": CriterionCategory.GRADUATION_YEAR_RANGE.value,
                "operator": CriterionOperator.BETWEEN.value,
                "criterion_value": f"{y_start}-{y_end}",
                "grading_system": None,
                "numeric_scale": None,
                "is_mandatory": is_mandatory,
                "source_text": sentence,
                "evidence_url": default_evidence_url,
                "verification_status": CriterionVerificationStatus.PENDING_REVIEW.value,
            })

        # 6. Expected Graduation
        exp_match = EXPECTED_GRAD_REGEX.search(sentence)
        if exp_match:
            month = exp_match.group(1) or ""
            year = exp_match.group(2)
            val = f"{month} {year}".strip()
            results.append({
                "criterion_type": CriterionCategory.EXPECTED_GRADUATION_WINDOW.value,
                "operator": CriterionOperator.LTE.value,
                "criterion_value": val,
                "grading_system": None,
                "numeric_scale": None,
                "is_mandatory": is_mandatory,
                "source_text": sentence,
                "evidence_url": default_evidence_url,
                "verification_status": CriterionVerificationStatus.PENDING_REVIEW.value,
            })

        # 7. Academic Standing
        for pattern, standing_code in STANDING_PATTERNS:
            if re.search(pattern, sentence, re.IGNORECASE):
                results.append({
                    "criterion_type": CriterionCategory.ACADEMIC_STANDING.value,
                    "operator": CriterionOperator.EQ.value,
                    "criterion_value": standing_code,
                    "grading_system": None,
                    "numeric_scale": None,
                    "is_mandatory": is_mandatory,
                    "source_text": sentence,
                    "evidence_url": default_evidence_url,
                    "verification_status": CriterionVerificationStatus.PENDING_REVIEW.value,
                })
                break

        # 8. County Restrictions vs Allocations
        # Semantic Rule 1: Distinguish county restriction from quota/allocation
        is_quota = bool(re.search(r"\b(?:quota|allocation|representation|target|affirmative\s*action|distributed\s*across)\b", sentence, re.IGNORECASE))
        is_restriction = bool(re.search(r"\b(?:resident|origin|native|exclusively|limited\s*to|only\s*students\s*from)\b", sentence, re.IGNORECASE))

        detected_counties: List[str] = []
        for c_name in KENYA_COUNTIES:
            if re.search(rf"\b{re.escape(c_name)}\b", sentence, re.IGNORECASE):
                detected_counties.append(c_name)

        if detected_counties:
            canonical_counties = ", ".join(sorted(set(detected_counties)))
            if is_quota:
                results.append({
                    "criterion_type": CriterionCategory.GEOGRAPHIC_ALLOCATION.value,
                    "operator": CriterionOperator.IN.value,
                    "criterion_value": canonical_counties,
                    "grading_system": None,
                    "numeric_scale": None,
                    "is_mandatory": False,  # Quotas do not strictly exclude
                    "source_text": sentence,
                    "evidence_url": default_evidence_url,
                    "verification_status": CriterionVerificationStatus.PENDING_REVIEW.value,
                })
            else:
                results.append({
                    "criterion_type": CriterionCategory.COUNTY_RESTRICTION.value,
                    "operator": CriterionOperator.IN.value,
                    "criterion_value": canonical_counties,
                    "grading_system": None,
                    "numeric_scale": None,
                    "is_mandatory": is_mandatory,
                    "source_text": sentence,
                    "evidence_url": default_evidence_url,
                    "verification_status": CriterionVerificationStatus.PENDING_REVIEW.value,
                })

        # 9. Age Restriction
        age_match = AGE_REGEX.search(sentence)
        if age_match:
            if age_match.group(1) and age_match.group(2):
                age_val = f"{age_match.group(1)}-{age_match.group(2)}"
                op_val = CriterionOperator.BETWEEN.value
            else:
                age_val = age_match.group(3)
                op_val = CriterionOperator.LTE.value

            results.append({
                "criterion_type": CriterionCategory.OTHER.value,
                "operator": op_val,
                "criterion_value": f"AGE_{age_val}",
                "grading_system": None,
                "numeric_scale": None,
                "is_mandatory": is_mandatory,
                "source_text": sentence,
                "evidence_url": default_evidence_url,
                "verification_status": CriterionVerificationStatus.PENDING_REVIEW.value,
            })

        # 10. Citizenship
        if CITIZENSHIP_REGEX.search(sentence):
            results.append({
                "criterion_type": CriterionCategory.OTHER.value,
                "operator": CriterionOperator.EQ.value,
                "criterion_value": "KENYAN_CITIZEN",
                "grading_system": None,
                "numeric_scale": None,
                "is_mandatory": is_mandatory,
                "source_text": sentence,
                "evidence_url": default_evidence_url,
                "verification_status": CriterionVerificationStatus.PENDING_REVIEW.value,
            })

    return results


def ingest_opportunity_criteria(
    session: Session,
    opportunity_id: str,
    criteria_candidates: List[Dict[str, Any]],
    policy: str = "preserve_reviewed"
) -> Dict[str, Any]:
    """
    Idempotently inserts or updates criteria for an opportunity.
    Strictly preserves administrator-reviewed criteria (VERIFIED, NEEDS_REVIEW, REJECTED).
    Prevents duplicates and records initial CREATE audit log.
    """
    opp = session.query(Opportunity).filter_by(id=opportunity_id).first()
    if not opp:
        raise ValueError(f"Opportunity with ID '{opportunity_id}' not found.")

    existing_criteria = session.query(OpportunityEligibilityCriterion).filter_by(
        opportunity_id=opportunity_id
    ).all()

    existing_by_type: Dict[str, List[OpportunityEligibilityCriterion]] = {}
    for crit in existing_criteria:
        existing_by_type.setdefault(crit.criterion_type, []).append(crit)

    created_count = 0
    skipped_count = 0
    preserved_count = 0

    for cand in criteria_candidates:
        c_type = cand["criterion_type"]
        c_val = str(cand["criterion_value"]).strip()
        c_op = cand["operator"]

        # Check existing criteria of same type
        matched_existing = None
        for ec in existing_by_type.get(c_type, []):
            if ec.criterion_value.strip().lower() == c_val.lower() and ec.operator == c_op:
                matched_existing = ec
                break

        if matched_existing:
            # If already reviewed by admin, preserve it unconditionally!
            if matched_existing.verification_status in (
                CriterionVerificationStatus.VERIFIED.value,
                CriterionVerificationStatus.NEEDS_REVIEW.value,
                CriterionVerificationStatus.REJECTED.value,
            ):
                preserved_count += 1
                continue
            else:
                # Already pending with identical value -> skip duplicate
                skipped_count += 1
                continue

        # Create new criterion in PENDING_REVIEW state
        new_crit = OpportunityEligibilityCriterion(
            opportunity_id=opportunity_id,
            criterion_type=c_type,
            operator=c_op,
            criterion_value=c_val,
            grading_system=cand.get("grading_system"),
            numeric_scale=cand.get("numeric_scale"),
            is_mandatory=cand.get("is_mandatory", True),
            source_text=cand["source_text"],
            evidence_url=cand.get("evidence_url") or opp.official_url,
            verification_status=CriterionVerificationStatus.PENDING_REVIEW.value,
            verified_by=None,
            verified_at=None,
        )
        session.add(new_crit)
        session.flush()

        # Record initial append-only audit event
        audit_log = OpportunityCriterionVerificationLog(
            criterion_id=new_crit.id,
            admin_id=None,
            admin_email="system@opportunity-intelligence.ai",
            event_type="INGESTION_CREATE",
            previous_status="PENDING_REVIEW",
            new_status="PENDING_REVIEW",
            before_snapshot=None,
            after_snapshot=json.dumps({
                "criterion_type": new_crit.criterion_type,
                "operator": new_crit.operator,
                "criterion_value": new_crit.criterion_value,
                "is_mandatory": new_crit.is_mandatory,
                "source_text": new_crit.source_text,
            }),
            evidence_url=new_crit.evidence_url,
            evidence_notes="Extracted from opportunity source text during automated ingestion.",
            metadata_json=json.dumps({"provenance": "automated_extraction"})
        )
        session.add(audit_log)
        created_count += 1

    session.commit()

    return {
        "opportunity_id": opportunity_id,
        "created_count": created_count,
        "skipped_count": skipped_count,
        "preserved_count": preserved_count,
        "total_criteria": session.query(OpportunityEligibilityCriterion).filter_by(
            opportunity_id=opportunity_id
        ).count(),
    }
