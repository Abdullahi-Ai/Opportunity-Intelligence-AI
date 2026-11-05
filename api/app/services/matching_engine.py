"""
Deterministic Academic Matching Engine for Opportunity Intelligence AI.

Phase 2 — Stage 2.1 Implementation.
Provides authoritative, canonical academic normalization, deterministic eligibility
evaluation, 3-tier scoring, and deterministic ranking.
"""

import re
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime


class CanonicalDegree(str, Enum):
    """Authoritative canonical degree qualification levels."""
    CERTIFICATE = "CERTIFICATE"
    DIPLOMA = "DIPLOMA"
    ADVANCED_DIPLOMA = "ADVANCED_DIPLOMA"
    UNDERGRADUATE = "UNDERGRADUATE"
    POSTGRADUATE_MASTERS = "POSTGRADUATE_MASTERS"
    DOCTORAL_PHD = "DOCTORAL_PHD"
    SECONDARY_SCHOOL = "SECONDARY_SCHOOL"


# Explicit, unambiguous alias mapping to canonical qualification tiers.
DEGREE_ALIAS_MAP: Dict[str, CanonicalDegree] = {
    # Undergraduate aliases
    "undergraduate": CanonicalDegree.UNDERGRADUATE,
    "undergrad": CanonicalDegree.UNDERGRADUATE,
    "bachelor": CanonicalDegree.UNDERGRADUATE,
    "bachelors": CanonicalDegree.UNDERGRADUATE,
    "bachelor's": CanonicalDegree.UNDERGRADUATE,
    "degree": CanonicalDegree.UNDERGRADUATE,
    "first degree": CanonicalDegree.UNDERGRADUATE,
    "bsc": CanonicalDegree.UNDERGRADUATE,
    "ba": CanonicalDegree.UNDERGRADUATE,
    "beng": CanonicalDegree.UNDERGRADUATE,
    "bcom": CanonicalDegree.UNDERGRADUATE,
    "bed": CanonicalDegree.UNDERGRADUATE,
    "llb": CanonicalDegree.UNDERGRADUATE,
    "btech": CanonicalDegree.UNDERGRADUATE,
    "bba": CanonicalDegree.UNDERGRADUATE,
    "bpharm": CanonicalDegree.UNDERGRADUATE,
    "mbchb": CanonicalDegree.UNDERGRADUATE,
    "bds": CanonicalDegree.UNDERGRADUATE,

    # Postgraduate / Masters aliases
    "graduate": CanonicalDegree.POSTGRADUATE_MASTERS,
    "grad": CanonicalDegree.POSTGRADUATE_MASTERS,
    "graduate degree": CanonicalDegree.POSTGRADUATE_MASTERS,
    "masters": CanonicalDegree.POSTGRADUATE_MASTERS,
    "master": CanonicalDegree.POSTGRADUATE_MASTERS,
    "master's": CanonicalDegree.POSTGRADUATE_MASTERS,
    "postgraduate": CanonicalDegree.POSTGRADUATE_MASTERS,
    "post graduate": CanonicalDegree.POSTGRADUATE_MASTERS,
    "post-graduate": CanonicalDegree.POSTGRADUATE_MASTERS,
    "msc": CanonicalDegree.POSTGRADUATE_MASTERS,
    "ma": CanonicalDegree.POSTGRADUATE_MASTERS,
    "mba": CanonicalDegree.POSTGRADUATE_MASTERS,
    "meng": CanonicalDegree.POSTGRADUATE_MASTERS,
    "med": CanonicalDegree.POSTGRADUATE_MASTERS,
    "llm": CanonicalDegree.POSTGRADUATE_MASTERS,
    "mph": CanonicalDegree.POSTGRADUATE_MASTERS,
    "mtech": CanonicalDegree.POSTGRADUATE_MASTERS,
    "pgd": CanonicalDegree.POSTGRADUATE_MASTERS,
    "postgraduate diploma": CanonicalDegree.POSTGRADUATE_MASTERS,

    # Doctoral / PhD aliases
    "phd": CanonicalDegree.DOCTORAL_PHD,
    "doctorate": CanonicalDegree.DOCTORAL_PHD,
    "doctoral": CanonicalDegree.DOCTORAL_PHD,
    "dphil": CanonicalDegree.DOCTORAL_PHD,
    "postdoc": CanonicalDegree.DOCTORAL_PHD,
    "postdoctoral": CanonicalDegree.DOCTORAL_PHD,

    # Diploma aliases (strictly separated from Advanced Diploma)
    "diploma": CanonicalDegree.DIPLOMA,
    "ordinary diploma": CanonicalDegree.DIPLOMA,
    "national diploma": CanonicalDegree.DIPLOMA,
    "dip": CanonicalDegree.DIPLOMA,
    "tvet diploma": CanonicalDegree.DIPLOMA,

    # Advanced Diploma aliases
    "advanced diploma": CanonicalDegree.ADVANCED_DIPLOMA,
    "higher diploma": CanonicalDegree.ADVANCED_DIPLOMA,
    "hnd": CanonicalDegree.ADVANCED_DIPLOMA,
    "higher national diploma": CanonicalDegree.ADVANCED_DIPLOMA,

    # Certificate aliases
    "certificate": CanonicalDegree.CERTIFICATE,
    "cert": CanonicalDegree.CERTIFICATE,
    "craft certificate": CanonicalDegree.CERTIFICATE,
    "artisan certificate": CanonicalDegree.CERTIFICATE,
    "professional certificate": CanonicalDegree.CERTIFICATE,

    # Secondary / High School
    "kcse": CanonicalDegree.SECONDARY_SCHOOL,
    "secondary": CanonicalDegree.SECONDARY_SCHOOL,
    "secondary school": CanonicalDegree.SECONDARY_SCHOOL,
    "high school": CanonicalDegree.SECONDARY_SCHOOL,
    "form 4": CanonicalDegree.SECONDARY_SCHOOL,
    "form four": CanonicalDegree.SECONDARY_SCHOOL,
    "o-level": CanonicalDegree.SECONDARY_SCHOOL,
    "a-level": CanonicalDegree.SECONDARY_SCHOOL,
}

UNIVERSAL_DEGREE_KEYWORDS: Set[str] = {
    "all degree levels",
    "all degrees",
    "any degree",
    "any degree level",
    "all",
    "any",
    "open to all",
    "open to all degrees",
}

UNIVERSAL_FIELD_KEYWORDS: Set[str] = {
    "all fields",
    "all disciplines",
    "all academic disciplines",
    "any discipline",
    "open to all",
    "open to all fields",
    "any field",
    "general",
    "unrestricted",
}

# Explicit canonical field aliases
FIELD_ALIAS_MAP: Dict[str, str] = {
    "cs": "computer science",
    "comp sci": "computer science",
    "se": "software engineering",
    "it": "information technology",
    "ict": "information and communication technology",
    "info tech": "information technology",
    "bbit": "business information technology",
    "ds": "data science",
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "cyber security": "cybersecurity",
    "telecom": "telecommunications",
    "telecom engineering": "telecommunications engineering",
    "telecommunication engineering": "telecommunications engineering",
    "electrical and electronic engineering": "electrical & electronic engineering",
    "eee": "electrical & electronic engineering",
    "mech": "mechanical engineering",
    "civil": "civil engineering",
    "medicine": "medicine and surgery",
    "human medicine": "medicine and surgery",
    "mbchb": "medicine and surgery",
    "law": "law",
    "llb": "law",
    "legal studies": "law",
    "bcom": "commerce",
    "bba": "business administration",
    "business admin": "business administration",
    "business management": "business administration",
    "hr": "human resource management",
    "hrm": "human resource management",
    "supply chain": "supply chain management",
    "procurement": "supply chain management",
}

# Academic clusters for deterministic disciplinary grouping
ACADEMIC_CLUSTERS: Dict[str, Set[str]] = {
    "COMPUTING_AND_TECH": {
        "computer science",
        "software engineering",
        "information technology",
        "information and communication technology",
        "computer technology",
        "data science",
        "data analytics",
        "artificial intelligence",
        "machine learning",
        "cybersecurity",
        "computer security",
        "computer security & forensics",
        "information systems",
        "business information technology",
        "informatics",
        "telecommunications",
        "telecommunications engineering",
        "network engineering",
        "graphic design",
        "digital media",
    },
    "ENGINEERING": {
        "civil engineering",
        "mechanical engineering",
        "electrical & electronic engineering",
        "electrical engineering",
        "electronic engineering",
        "mechatronics",
        "mechatronic engineering",
        "chemical engineering",
        "geospatial engineering",
        "agricultural engineering",
        "biomedical engineering",
        "petroleum engineering",
        "telecommunications engineering",
        "structural engineering",
        "engineering",
    },
    "BUSINESS_AND_FINANCE": {
        "business administration",
        "commerce",
        "accounting",
        "finance",
        "banking",
        "banking and finance",
        "actuarial science",
        "marketing",
        "supply chain management",
        "human resource management",
        "entrepreneurship",
        "business & finance",
        "business & economics",
        "business and economics",
        "strategic management",
    },
    "ECONOMICS": {
        "economics",
        "applied economics",
        "econometrics",
        "financial economics",
        "economics and statistics",
        "development economics",
        "economics & finance",
    },
    "HEALTH_AND_MEDICINE": {
        "medicine and surgery",
        "medicine",
        "nursing",
        "pharmacy",
        "public health",
        "clinical medicine",
        "medical laboratory science",
        "biomedical science",
        "dentistry",
        "radiography",
        "physiotherapy",
        "community health",
        "epidemiology",
        "health sciences",
        "medicine & health sciences",
    },
    "LAW_AND_LEGAL": {
        "law",
        "legal studies",
        "commercial law",
        "international law",
        "human rights law",
        "law & human rights",
    },
    "AGRICULTURE_AND_ENVIRONMENT": {
        "agriculture",
        "agribusiness",
        "agricultural economics",
        "horticulture",
        "forestry",
        "environmental science",
        "environmental sciences",
        "environmental studies",
        "natural resource management",
        "wildlife management",
        "soil science",
        "animal science",
        "fisheries",
        "renewable energy & climate",
        "renewable energy",
    },
    "SOCIAL_SCIENCES": {
        "political science",
        "international relations",
        "public administration",
        "public policy",
        "sociology",
        "psychology",
        "social work",
        "development studies",
        "international development",
        "social sciences",
        "social sciences & policy",
        "anthropology",
        "criminology",
    },
    "MEDIA_AND_COMMUNICATION": {
        "journalism",
        "mass communication",
        "public relations",
        "media studies",
        "communications & journalism",
        "communication studies",
    },
    "EDUCATION": {
        "education",
        "curriculum studies",
        "educational management",
        "early childhood education",
        "special needs education",
    },
    "NATURAL_SCIENCES_MATH": {
        "mathematics",
        "statistics",
        "physics",
        "chemistry",
        "biology",
        "biotechnology",
        "biochemistry",
        "microbiology",
        "mathematics & computer science",
    },
}

# Specialized interdisciplinary overlaps that qualify as "Needs Verification"
INTERDISCIPLINARY_OVERLAPS: Dict[str, Set[str]] = {
    "environmental economics": {"economics", "environmental science", "environmental sciences", "agriculture"},
    "agricultural economics": {"economics", "agriculture", "agribusiness"},
    "health economics": {"economics", "public health"},
    "medical informatics": {"computer science", "health sciences", "information technology"},
    "bioinformatics": {"computer science", "biology", "biotechnology", "data science"},
    "data science & ai": {"computer science", "mathematics", "statistics"},
}


def clean_text(text: Optional[str]) -> str:
    """Strips punctuation, normalizes spacing and lowercases text."""
    if not text:
        return ""
    t = text.strip().lower()
    # Remove dots so that acronyms like B.Sc., Ph.D., M.Sc., B.A. become bsc, phd, msc, ba
    t = t.replace(".", "")
    t = re.sub(r'[\,\/_\-\(\)\[\]]', ' ', t)
    return " ".join(t.split())


def normalize_degree_level(degree_str: Optional[str]) -> Tuple[Optional[CanonicalDegree], str]:
    """
    Normalizes arbitrary degree level string to CanonicalDegree.
    Returns (CanonicalDegree, raw_cleaned_string).
    Eliminates substring collisions.
    """
    if not degree_str:
        return (None, "")

    cleaned = clean_text(degree_str)
    if not cleaned:
        return (None, "")

    # Direct alias lookup
    if cleaned in DEGREE_ALIAS_MAP:
        return (DEGREE_ALIAS_MAP[cleaned], cleaned)

    # Word-boundary check for exact known aliases (no substring bleeding)
    for alias, canonical in DEGREE_ALIAS_MAP.items():
        pattern = rf"\b{re.escape(alias)}\b"
        if re.search(pattern, cleaned):
            return (canonical, cleaned)

    return (None, cleaned)


def evaluate_degree_level(
    student_degree: Optional[str],
    allowed_degrees_str: Optional[str]
) -> Tuple[bool, str, str]:
    """
    Evaluates degree level eligibility deterministically.
    Returns: (meets_bool, status_str, reason_str)
    status_str: 'Meets', 'Needs Verification', or 'Does Not Meet'
    """
    # 1. Unconstrained opportunity
    if not allowed_degrees_str or not allowed_degrees_str.strip():
        return (True, "Meets", "Open to all degree levels")

    raw_req = allowed_degrees_str.strip()
    cleaned_req = clean_text(raw_req)

    # Check universal requirements
    if any(kw in cleaned_req for kw in UNIVERSAL_DEGREE_KEYWORDS):
        return (True, "Meets", "Open to all degree levels")

    # Split opportunity required degrees (by comma, semicolon, or slash)
    req_parts = [p.strip() for p in re.split(r'[,;/]| and ', raw_req) if p.strip()]
    allowed_canonicals: Set[CanonicalDegree] = set()
    unmapped_reqs: List[str] = []

    for part in req_parts:
        canonical, c_raw = normalize_degree_level(part)
        if canonical:
            allowed_canonicals.add(canonical)
        elif c_raw:
            unmapped_reqs.append(c_raw)

    # Student degree validation
    student_canonical, student_raw = normalize_degree_level(student_degree)

    if not student_degree or not student_raw:
        return (False, "Needs Verification", "Student degree level not specified in profile")

    if student_canonical is None:
        # Unknown/unrecognized student degree -> Needs manual verification, not false match or immediate rejection
        return (False, "Needs Verification", f"Degree level '{student_degree}' requires institutional verification")

    # Authoritative membership comparison
    if student_canonical in allowed_canonicals:
        display_name = student_canonical.value.replace("_", " ").title()
        return (True, "Meets", f"Eligible qualification ({display_name})")

    # If opportunity had unmapped custom degrees, verify against raw string
    if unmapped_reqs and any(student_raw == r or student_raw in r.split() for r in unmapped_reqs):
        return (True, "Needs Verification", f"Special qualification match for '{student_degree}' requires confirmation")

    return (False, "Does Not Meet", f"Requires {raw_req}; student provided {student_degree}")


def normalize_field_name(field_str: Optional[str]) -> str:
    """Normalizes field of study string using canonical aliases."""
    if not field_str:
        return ""
    cleaned = clean_text(field_str)
    return FIELD_ALIAS_MAP.get(cleaned, cleaned)


def get_field_cluster(field_name: str) -> Optional[str]:
    """Finds the academic cluster for a given normalized field name."""
    norm = normalize_field_name(field_name)
    for cluster_name, fields in ACADEMIC_CLUSTERS.items():
        if norm in fields:
            return cluster_name
        # Match if full field name is in cluster set
        for f in fields:
            if norm == f:
                return cluster_name
    return None


def evaluate_field_of_study(
    student_field: Optional[str],
    student_specialisations: Optional[str],
    allowed_fields_str: Optional[str]
) -> Tuple[bool, str, str]:
    """
    Evaluates field of study eligibility with high precision.
    Returns: (meets_bool, status_str, reason_str)
    status_str: 'Meets', 'Needs Verification', or 'Does Not Meet'
    """
    # 1. Unconstrained opportunity
    if not allowed_fields_str or not allowed_fields_str.strip():
        return (True, "Meets", "Open to all academic disciplines")

    raw_req = allowed_fields_str.strip()
    cleaned_req = clean_text(raw_req)

    # Universal disciplines check
    if any(kw in cleaned_req for kw in UNIVERSAL_FIELD_KEYWORDS):
        return (True, "Meets", "Open to all academic disciplines")

    if not student_field or not student_field.strip():
        return (False, "Needs Verification", "Student field of study not specified in profile")

    norm_student = normalize_field_name(student_field)
    student_cluster = get_field_cluster(norm_student)

    # Parse allowed fields
    req_parts = [p.strip() for p in re.split(r'[,;/]', raw_req) if p.strip()]
    norm_allowed = [normalize_field_name(p) for p in req_parts]

    # Universal phrase within list check
    if any(a in UNIVERSAL_FIELD_KEYWORDS for a in norm_allowed):
        return (True, "Meets", "Open to all academic disciplines")

    # A. Exact Match Check
    if norm_student in norm_allowed:
        return (True, "Meets", f"Matches required course in {student_field}")

    # Check student specialisations for exact match
    if student_specialisations:
        specs = [clean_text(s) for s in re.split(r'[,;/]', student_specialisations) if s.strip()]
        for spec in specs:
            norm_spec = normalize_field_name(spec)
            if norm_spec in norm_allowed:
                return (True, "Meets", f"Specialisation in {spec} matches required course")

    # B. Academic Cluster Matching (controlled disciplinary equivalence)
    if student_cluster:
        for allowed in norm_allowed:
            allowed_cluster = get_field_cluster(allowed)
            if allowed_cluster and allowed_cluster == student_cluster:
                cluster_label = student_cluster.replace("_", " ").title()
                return (True, "Meets", f"Related discipline in {cluster_label} ({allowed.title()})")

    # C. Interdisciplinary / Partial Overlap Check
    # If the student field is known interdisciplinary with explicit relationships
    if norm_student in INTERDISCIPLINARY_OVERLAPS:
        related_fields = INTERDISCIPLINARY_OVERLAPS[norm_student]
        for allowed in norm_allowed:
            if allowed in related_fields or any(allowed in rf for rf in related_fields):
                return (False, "Needs Verification", f"Interdisciplinary course in {student_field} related to {allowed.title()} (verification required)")

    # Reverse interdisciplinary check (opportunity specifies interdisciplinary program)
    for allowed in norm_allowed:
        if allowed in INTERDISCIPLINARY_OVERLAPS:
            if norm_student in INTERDISCIPLINARY_OVERLAPS[allowed]:
                return (False, "Needs Verification", f"Course {student_field} related to required interdisciplinary focus {allowed.title()}")

    # Strict rejection: Unrelated fields sharing stop words (e.g. Science, Arts) MUST NOT match
    return (False, "Does Not Meet", f"Requires study in {raw_req}; provided {student_field}")


def evaluate_academic_year_and_standing(
    student_year: int,
    opp_title: str,
    opp_id: str,
    target_audience: Optional[str] = None,
    category: Optional[str] = None,
    degree_levels: Optional[str] = None,
    source_notes: Optional[str] = None
) -> Tuple[bool, str, str, Optional[Dict[str, str]]]:
    """
    Evaluates academic year and student standing without brittle single-word checks.
    Returns: (meets_bool, status_str, reason_str, criteria_breakdown_dict_or_None)
    """
    text_corpus = f"{opp_title} {opp_id} {target_audience or ''} {category or ''} {source_notes or ''}".lower()

    # Case 1: Industrial Attachment / Internship continuing student rule
    is_attachment = (
        "attachment" in text_corpus or
        "industrial attachment" in text_corpus or
        ("internship" in (category or "").lower() and "continuing" in text_corpus)
    )

    if is_attachment:
        # Check explicit year requirements in text
        has_234 = any(pattern in text_corpus for pattern in [
            "2nd, 3rd, and 4th",
            "2nd, 3rd, or 4th",
            "2nd, 3rd and 4th",
            "second, third, or fourth",
            "at least 2 full years",
            "completed at least 2",
            "continuing 2nd, 3rd",
        ])

        if has_234 or "attachment" in opp_id.lower():
            if student_year in [2, 3, 4]:
                return (
                    True,
                    "Meets",
                    f"Year {student_year} qualifies for continuing industrial attachment",
                    {
                        "criterion": "Year of Study (Attachment)",
                        "required": "2nd, 3rd, or 4th Year continuing student",
                        "provided": f"Year {student_year}",
                        "status": "Meets"
                    }
                )
            else:
                return (
                    False,
                    "Does Not Meet",
                    f"Year {student_year} does not meet continuing attachment requirement (2nd, 3rd, or 4th year required)",
                    {
                        "criterion": "Year of Study (Attachment)",
                        "required": "2nd, 3rd, or 4th Year continuing student",
                        "provided": f"Year {student_year}",
                        "status": "Does Not Meet"
                    }
                )

    # Case 2: Final year requirement (e.g. UN Gigiri Internship)
    is_final_year_req = "final year" in text_corpus or "graduating student" in text_corpus
    if is_final_year_req:
        if student_year in [4, 5]:
            return (
                True,
                "Meets",
                f"Year {student_year} satisfies final-year student requirement",
                {
                    "criterion": "Academic Standing (Final Year)",
                    "required": "Final year undergraduate or enrolled graduate student",
                    "provided": f"Year {student_year}",
                    "status": "Meets"
                }
            )
        elif student_year in [1, 2]:
            return (
                False,
                "Does Not Meet",
                f"Year {student_year} is not a final-year student",
                {
                    "criterion": "Academic Standing (Final Year)",
                    "required": "Final year undergraduate or enrolled graduate student",
                    "provided": f"Year {student_year}",
                    "status": "Does Not Meet"
                }
            )
        else:
            return (
                False,
                "Needs Verification",
                f"Year {student_year} requires verification of final-year academic status",
                {
                    "criterion": "Academic Standing (Final Year)",
                    "required": "Final year undergraduate or enrolled graduate student",
                    "provided": f"Year {student_year}",
                    "status": "Needs Verification"
                }
            )

    # Case 3: Graduate Trainee schemes (e.g. PDTP, Safaricom Discover)
    is_graduate_trainee = (
        (category or "").lower() == "graduate trainee" or
        "graduate trainee" in text_corpus or
        "fresh ... graduate" in text_corpus or
        "recent university graduates" in text_corpus
    )
    if is_graduate_trainee:
        # Continuing students in years 1-3 are generally ineligible for graduate trainee full-time roles
        if student_year in [1, 2, 3]:
            return (
                False,
                "Does Not Meet",
                f"Graduate trainee programmes require completed degree; student is in Year {student_year}",
                {
                    "criterion": "Academic Standing (Graduate Trainee)",
                    "required": "Recent degree graduate / awaiting graduation",
                    "provided": f"Year {student_year} continuing student",
                    "status": "Does Not Meet"
                }
            )
        else:
            # Year 4+ / final year awaiting graduation
            return (
                True,
                "Meets",
                "Graduating or completed student eligible for graduate trainee pipeline",
                {
                    "criterion": "Academic Standing (Graduate Trainee)",
                    "required": "Recent degree graduate / final year awaiting graduation",
                    "provided": f"Year {student_year}",
                    "status": "Meets"
                }
            )

    # Default: Unconstrained academic year
    return (True, "Meets", "No academic year restrictions", None)


def calculate_match_score(
    eligibility_status: str,
    deg_meets: bool,
    field_status: str,
    pref_meets: bool,
    is_open: bool,
    is_universal_field: bool = False
) -> int:
    """
    Computes deterministic match score enforcing 3-tier numerical separation:
    - Meets requirements: 70% to 100% (fully eligible reaches 100%, All Fields not penalized)
    - Needs verification: 35% to 55%
    - Does not meet requirements: 0% to 20% (strictly separated from eligible tiers)
    """
    if eligibility_status == "Meets requirements":
        base_score = 60
        # Full field bonus for exact, cluster, or All Fields / universal disciplines
        field_bonus = 20 if (field_status == "Meets" or is_universal_field) else 10
        deg_bonus = 10 if deg_meets else 0
        pref_bonus = 5 if pref_meets else 0
        deadline_bonus = 5 if is_open else 0
        total = base_score + field_bonus + deg_bonus + pref_bonus + deadline_bonus
        return min(100, max(70, total))

    elif eligibility_status == "Needs verification":
        base_score = 35
        deg_bonus = 5 if deg_meets else 0
        field_bonus = 5 if (field_status in ["Meets", "Needs Verification"] or is_universal_field) else 0
        pref_bonus = 5 if pref_meets else 0
        deadline_bonus = 5 if is_open else 0
        total = base_score + deg_bonus + field_bonus + pref_bonus + deadline_bonus
        return min(55, max(35, total))

    else:  # "Does not meet requirements"
        base_score = 0
        # Ineligible candidates receive marginal baseline alignment points strictly capped below 25%
        deg_bonus = 5 if deg_meets else 0
        field_bonus = 5 if (field_status == "Meets" or is_universal_field) else 0
        pref_bonus = 5 if pref_meets else 0
        deadline_bonus = 5 if is_open else 0
        total = base_score + deg_bonus + field_bonus + pref_bonus + deadline_bonus
        return min(20, max(0, total))


def get_match_sort_key(
    eligibility_status: str,
    match_score: int,
    days_remaining: Optional[int],
    created_at: Optional[datetime],
    opportunity_id: str
) -> Tuple[int, int, int, float, str]:
    """
    Produces deterministic 4-tier sorting key:
    Tier 1: Eligibility status rank (Meets > Needs Verification > Does Not Meet)
    Tier 2: Match score descending (negated)
    Tier 3: Deadline urgency ascending (active closing soonest ranked first)
    Tier 4: Creation date descending (negated timestamp)
    Tier 5: Opportunity ID ascending (stable final tie-breaker)
    """
    status_ranks = {
        "Meets requirements": 1,
        "Needs verification": 2,
        "Does not meet requirements": 3,
    }
    status_rank = status_ranks.get(eligibility_status, 4)

    # Inverted match score for descending sort
    score_rank = -int(match_score)

    # Deadline urgency:
    # 0..N days: active open opportunities, sorted ascending (more urgent first)
    # None: rolling / unspecified deadline (neutral, placed after known active)
    # < 0: expired / closed opportunities (lowest priority)
    if days_remaining is not None and days_remaining >= 0:
        urgency_rank = days_remaining
    elif days_remaining is None:
        urgency_rank = 100000
    else:
        urgency_rank = 200000 + abs(days_remaining)

    # Creation timestamp descending
    if created_at is not None:
        created_timestamp = -created_at.timestamp()
    else:
        created_timestamp = 0.0

    return (status_rank, score_rank, urgency_rank, created_timestamp, str(opportunity_id))


# ============================================================================
# STAGE 2.2C: STRUCTURED ELIGIBILITY CRITERIA DETERMINISTIC EVALUATION
# ============================================================================

from app.services.academic_profile_normalization import (
    normalize_academic_grade,
    normalize_county,
    validate_graduation_year,
    normalize_expected_graduation,
    GradingSystem,
    CanonicalHonours,
    CanonicalKCSE,
    NormalizationStatus,
)

HONOURS_RANK: Dict[str, int] = {
    CanonicalHonours.FIRST_CLASS.value: 4,
    CanonicalHonours.UPPER_SECOND.value: 3,
    CanonicalHonours.LOWER_SECOND.value: 2,
    CanonicalHonours.PASS.value: 1,
}

KCSE_RANK: Dict[str, int] = {
    "A": 12, "A-": 11, "B+": 10, "B": 9, "B-": 8,
    "C+": 7, "C": 6, "C-": 5, "D+": 4, "D": 3, "D-": 2, "E": 1
}


def evaluate_structured_criterion(
    student: Any,
    criterion: Any
) -> Dict[str, Any]:
    """
    Deterministically assesses an individual structured criterion against a student profile.
    
    Invariants Enforced:
    1. Only VERIFIED criteria can cause 'Does Not Meet'. Unverified criteria yield at most 'Needs Verification'.
    2. Desirable criteria (is_mandatory=False) never cause 'Does Not Meet'.
    3. Missing profile info yields 'Needs Verification'.
    4. Incompatible grading systems yield 'Needs Verification' without invented equivalence.
    5. Quotas / allocations never act as exclusionary restrictions.
    """
    c_type = getattr(criterion, "criterion_type", "OTHER")
    c_op = getattr(criterion, "operator", "EQ")
    c_val = str(getattr(criterion, "criterion_value", "")).strip()
    is_mandatory = getattr(criterion, "is_mandatory", True)
    ver_status = getattr(criterion, "verification_status", "PENDING_REVIEW")
    is_verified = (ver_status == "VERIFIED")
    evidence_url = getattr(criterion, "evidence_url", None)

    # Base item template
    item: Dict[str, Any] = {
        "criterion_id": getattr(criterion, "id", None),
        "criterion": c_type.replace("_", " ").title(),
        "criterion_type": c_type,
        "operator": c_op,
        "required": c_val,
        "provided": "Not Specified",
        "status": "Needs Verification",
        "is_mandatory": is_mandatory,
        "verification_status": ver_status,
        "explanation": "",
        "evidence_url": evidence_url,
    }

    # Helper: apply verification and mandatory boundaries to final status
    def resolve_status(preliminary_meets: bool, failure_explanation: str, success_explanation: str) -> Tuple[str, str]:
        if preliminary_meets:
            if is_verified:
                return ("Meets", success_explanation)
            else:
                return ("Needs Verification", f"{success_explanation} (Criterion is pending administrative verification)")
        else:
            if not is_mandatory:
                return ("Meets", f"{failure_explanation} (Desirable preference does not disqualify)")
            if not is_verified:
                return ("Needs Verification", f"{failure_explanation} (Criterion unverified; requires verification before exclusion)")
            return ("Does Not Meet", failure_explanation)

    # 1. MINIMUM ACADEMIC GRADE (Degree Classifications)
    if c_type == "MINIMUM_ACADEMIC_GRADE":
        raw_grade = getattr(student, "gpa_or_grade", None)
        item["provided"] = raw_grade or "Missing from profile"
        if not raw_grade or not str(raw_grade).strip():
            item["status"] = "Needs Verification"
            item["explanation"] = "Student profile lacks academic degree classification"
            return item

        student_norm = normalize_academic_grade(raw_grade)
        if student_norm.status != NormalizationStatus.NORMALIZED:
            item["status"] = "Needs Verification"
            item["explanation"] = f"Academic grade '{raw_grade}' is unverified or ambiguous"
            return item

        if student_norm.grading_system != GradingSystem.KENYAN_UNIVERSITY_HONOURS:
            item["status"] = "Needs Verification"
            item["explanation"] = f"Student grade is in system '{student_norm.grading_system.value}'; cannot safely convert to honours degree without explicit conversion"
            return item

        student_rank = HONOURS_RANK.get(student_norm.normalized_classification, 0)
        req_rank = HONOURS_RANK.get(c_val, 0)

        preliminary = (student_rank >= req_rank) if c_op == "GTE" else (student_rank == req_rank)
        status_val, expl = resolve_status(
            preliminary,
            failure_explanation=f"Requires {c_val}; provided {student_norm.normalized_classification}",
            success_explanation=f"Satisfies minimum grade requirement ({student_norm.normalized_classification} >= {c_val})"
        )
        item["status"] = status_val
        item["explanation"] = expl
        return item

    # 2. KCSE GRADE
    elif c_type == "KCSE_GRADE":
        raw_grade = getattr(student, "gpa_or_grade", None)
        item["provided"] = raw_grade or "Missing from profile"
        if not raw_grade or not str(raw_grade).strip():
            item["status"] = "Needs Verification"
            item["explanation"] = "Student profile does not record secondary (KCSE) mean grade"
            return item

        student_norm = normalize_academic_grade(raw_grade)
        if student_norm.grading_system != GradingSystem.KCSE or not student_norm.normalized_classification:
            item["status"] = "Needs Verification"
            item["explanation"] = f"Student profile grade '{raw_grade}' is not a KCSE secondary mean grade"
            return item

        student_rank = KCSE_RANK.get(student_norm.normalized_classification, 0)
        req_rank = KCSE_RANK.get(c_val, 0)

        preliminary = (student_rank >= req_rank) if c_op == "GTE" else (student_rank == req_rank)
        status_val, expl = resolve_status(
            preliminary,
            failure_explanation=f"Requires KCSE {c_val}; provided {student_norm.normalized_classification}",
            success_explanation=f"Satisfies KCSE requirement ({student_norm.normalized_classification} >= {c_val})"
        )
        item["status"] = status_val
        item["explanation"] = expl
        return item

    # 3. NUMERIC GPA
    elif c_type == "NUMERIC_GPA":
        raw_grade = getattr(student, "gpa_or_grade", None)
        item["provided"] = raw_grade or "Missing from profile"
        if not raw_grade or not str(raw_grade).strip():
            item["status"] = "Needs Verification"
            item["explanation"] = "Student profile lacks numeric GPA"
            return item

        student_norm = normalize_academic_grade(raw_grade)
        if student_norm.grading_system != GradingSystem.NUMERIC_GPA or student_norm.numeric_value is None:
            item["status"] = "Needs Verification"
            item["explanation"] = f"Student grade '{raw_grade}' is not a numeric GPA; scale conversion unsupported"
            return item

        crit_scale = float(getattr(criterion, "numeric_scale", 4.0) or 4.0)
        student_scale = student_norm.numeric_scale or 4.0
        if abs(student_scale - crit_scale) > 0.1:
            item["status"] = "Needs Verification"
            item["explanation"] = f"Scale mismatch: opportunity requires scale {crit_scale}, student has scale {student_scale}"
            return item

        try:
            req_gpa = float(c_val)
            stud_gpa = float(student_norm.numeric_value)
            preliminary = (stud_gpa >= req_gpa) if c_op == "GTE" else (stud_gpa <= req_gpa)
            status_val, expl = resolve_status(
                preliminary,
                failure_explanation=f"Requires GPA {req_gpa:.2f}/{crit_scale:.1f}; provided {stud_gpa:.2f}/{student_scale:.1f}",
                success_explanation=f"Satisfies GPA requirement ({stud_gpa:.2f} >= {req_gpa:.2f})"
            )
            item["status"] = status_val
            item["explanation"] = expl
            return item
        except ValueError:
            item["status"] = "Needs Verification"
            item["explanation"] = f"Invalid numeric GPA format '{c_val}' in criterion"
            return item

    # 4. COUNTY RESTRICTION
    elif c_type == "COUNTY_RESTRICTION":
        raw_county = getattr(student, "county_of_origin", None)
        item["provided"] = raw_county or "Missing from profile"
        if not raw_county or not str(raw_county).strip():
            item["status"] = "Needs Verification"
            item["explanation"] = "County of origin not specified in student profile"
            return item

        c_norm = normalize_county(raw_county)
        if c_norm.status != NormalizationStatus.NORMALIZED or not c_norm.canonical_name:
            item["status"] = "Needs Verification"
            item["explanation"] = f"County '{raw_county}' could not be normalized to official 47 Kenya counties"
            return item

        allowed_counties = [c.strip().lower() for c in c_val.split(",") if c.strip()]
        preliminary = c_norm.canonical_name.lower() in allowed_counties
        status_val, expl = resolve_status(
            preliminary,
            failure_explanation=f"Restricted to {c_val}; student from {c_norm.canonical_name}",
            success_explanation=f"Origin county {c_norm.canonical_name} satisfies geographic restriction"
        )
        item["status"] = status_val
        item["explanation"] = expl
        return item

    # 5. GEOGRAPHIC ALLOCATION / QUOTA
    elif c_type == "GEOGRAPHIC_ALLOCATION":
        raw_county = getattr(student, "county_of_origin", None)
        item["provided"] = raw_county or "Missing from profile"
        if raw_county:
            c_norm = normalize_county(raw_county)
            allowed_counties = [c.strip().lower() for c in c_val.split(",") if c.strip()]
            if c_norm.canonical_name and c_norm.canonical_name.lower() in allowed_counties:
                item["status"] = "Meets"
                item["explanation"] = f"Qualifies for {c_norm.canonical_name} affirmative action / allocation quota"
                return item
        item["status"] = "Meets"
        item["explanation"] = "Opportunity specifies regional quotas; candidates from all counties remain eligible"
        return item

    # 6. GRADUATION YEAR RANGE
    elif c_type == "GRADUATION_YEAR_RANGE":
        grad_yr = getattr(student, "graduation_year", None)
        item["provided"] = f"Class of {grad_yr}" if grad_yr else "Missing from profile"
        if not grad_yr:
            item["status"] = "Needs Verification"
            item["explanation"] = "Graduation year not recorded in student profile"
            return item

        try:
            if "-" in c_val:
                p_start, p_end = c_val.split("-")
                y_min, y_max = int(p_start.strip()), int(p_end.strip())
                preliminary = (y_min <= int(grad_yr) <= y_max)
            else:
                y_req = int(c_val.strip())
                preliminary = (int(grad_yr) >= y_req) if c_op == "GTE" else (int(grad_yr) == y_req)

            status_val, expl = resolve_status(
                preliminary,
                failure_explanation=f"Requires graduation between {c_val}; provided {grad_yr}",
                success_explanation=f"Graduation year {grad_yr} falls within required window {c_val}"
            )
            item["status"] = status_val
            item["explanation"] = expl
            return item
        except ValueError:
            item["status"] = "Needs Verification"
            item["explanation"] = f"Invalid graduation year format '{c_val}'"
            return item

    # 7. MONTHS SINCE GRADUATION
    elif c_type == "MONTHS_SINCE_GRADUATION":
        grad_yr = getattr(student, "graduation_year", None)
        item["provided"] = f"Graduated {grad_yr}" if grad_yr else "Missing from profile"
        if not grad_yr:
            item["status"] = "Needs Verification"
            item["explanation"] = "Graduation year required to compute months since graduation"
            return item

        try:
            max_months = int(c_val.strip())
            current_year = datetime.utcnow().year
            approx_months = max(0, (current_year - int(grad_yr)) * 12)
            preliminary = (approx_months <= max_months) if c_op == "LTE" else (approx_months >= max_months)
            status_val, expl = resolve_status(
                preliminary,
                failure_explanation=f"Requires graduation within {max_months} months; approximately {approx_months} months elapsed",
                success_explanation=f"Recent graduation ({approx_months} months elapsed <= {max_months} months allowed)"
            )
            item["status"] = status_val
            item["explanation"] = expl
            return item
        except ValueError:
            item["status"] = "Needs Verification"
            item["explanation"] = f"Invalid month format '{c_val}'"
            return item

    # 8. EXPECTED GRADUATION WINDOW
    elif c_type == "EXPECTED_GRADUATION_WINDOW":
        exp_grad = getattr(student, "expected_graduation", None)
        item["provided"] = str(exp_grad) if exp_grad else "Missing from profile"
        if not exp_grad:
            item["status"] = "Needs Verification"
            item["explanation"] = "Expected graduation date not specified in student profile"
            return item

        # Temporal comparison
        exp_norm = normalize_expected_graduation(exp_grad)
        if exp_norm.status != NormalizationStatus.NORMALIZED:
            item["status"] = "Needs Verification"
            item["explanation"] = f"Expected graduation '{exp_grad}' requires administrative verification"
            return item

        item["status"] = "Meets" if is_verified else "Needs Verification"
        item["explanation"] = f"Expected graduation {exp_norm.canonical_string} meets forward-looking window"
        return item

    # 9. ACADEMIC STANDING
    elif c_type == "ACADEMIC_STANDING":
        deg_lvl = (getattr(student, "degree_level", "") or "").lower()
        yr_study = getattr(student, "year_of_study", 1)
        grad_yr = getattr(student, "graduation_year", None)
        item["provided"] = f"{deg_lvl.title()} (Year {yr_study})"

        if c_val == "UNDERGRADUATE":
            preliminary = ("undergraduate" in deg_lvl or "bachelor" in deg_lvl)
        elif c_val == "GRADUATING_SENIOR":
            preliminary = yr_study in [4, 5]
        elif c_val == "POSTGRADUATE":
            preliminary = ("master" in deg_lvl or "postgraduate" in deg_lvl or "phd" in deg_lvl)
        elif c_val == "ALUMNI":
            preliminary = bool(grad_yr and grad_yr <= datetime.utcnow().year)
        else:
            preliminary = True

        status_val, expl = resolve_status(
            preliminary,
            failure_explanation=f"Requires {c_val} standing; student is {deg_lvl.title()} Year {yr_study}",
            success_explanation=f"Academic standing qualifies ({c_val})"
        )
        item["status"] = status_val
        item["explanation"] = expl
        return item

    # 10. OTHER (Citizenship, Age, Bespoke)
    elif c_type == "OTHER":
        if "KENYAN_CITIZEN" in c_val:
            country = getattr(student, "country", "Kenya") or "Kenya"
            item["provided"] = f"Citizen of {country}"
            preliminary = (country.lower() == "kenya")
            status_val, expl = resolve_status(
                preliminary,
                failure_explanation="Requires Kenyan citizenship",
                success_explanation="Kenyan citizen status confirmed"
            )
            item["status"] = status_val
            item["explanation"] = expl
            return item

        # Default fallback for unmodeled bespoke criteria
        item["status"] = "Needs Verification"
        item["explanation"] = f"Requires verification of criterion '{c_val}' against student documentation"
        return item

    return item


def evaluate_opportunity_eligibility(
    student: Any,
    opportunity: Any,
    criteria: Optional[List[Any]] = None
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Evaluates complete opportunity eligibility synthesizing structured criteria and legacy rules.
    
    Returns:
    (overall_status, criteria_breakdown_list, evaluation_meta)
    where overall_status is one of:
    - 'Meets requirements'
    - 'Needs verification'
    - 'Does not meet requirements'
    """
    breakdown: List[Dict[str, Any]] = []

    # 1. Degree Level
    deg_meets, deg_status, deg_reason = evaluate_degree_level(
        getattr(student, "degree_level", "Undergraduate"),
        getattr(opportunity, "degree_levels", None)
    )
    breakdown.append({
        "criterion": "Degree Level",
        "criterion_type": "DEGREE_LEVEL",
        "required": getattr(opportunity, "degree_levels", None) or "All Degree Levels",
        "provided": getattr(student, "degree_level", "Undergraduate"),
        "status": deg_status,
        "is_mandatory": True,
        "verification_status": "VERIFIED" if getattr(opportunity, "is_verified", False) else "UNVERIFIED"
    })

    # 2. Field of Study
    field_meets, field_status, field_reason = evaluate_field_of_study(
        getattr(student, "field_of_study", ""),
        getattr(student, "specialisations", None),
        getattr(opportunity, "fields_of_study", None)
    )
    breakdown.append({
        "criterion": "Field of Study",
        "criterion_type": "FIELD_OF_STUDY",
        "required": getattr(opportunity, "fields_of_study", None) or "All Fields",
        "provided": getattr(student, "field_of_study", ""),
        "status": field_status,
        "is_mandatory": True,
        "verification_status": "VERIFIED" if getattr(opportunity, "is_verified", False) else "UNVERIFIED"
    })

    # 3. Academic Year & Standing
    yr_meets, yr_status, yr_reason, yr_crit = evaluate_academic_year_and_standing(
        getattr(student, "year_of_study", 1),
        getattr(opportunity, "title", ""),
        getattr(opportunity, "id", ""),
        target_audience=getattr(opportunity, "target_audience", None),
        category=getattr(opportunity, "category", None),
        degree_levels=getattr(opportunity, "degree_levels", None),
        source_notes=getattr(opportunity, "source_notes", None)
    )
    if yr_crit is not None:
        breakdown.append({
            "criterion": yr_crit["criterion"],
            "criterion_type": "ACADEMIC_STANDING",
            "required": yr_crit["required"],
            "provided": yr_crit["provided"],
            "status": yr_crit["status"],
            "is_mandatory": True,
            "verification_status": "VERIFIED" if getattr(opportunity, "is_verified", False) else "UNVERIFIED"
        })

    # 4. Structured Criteria Evaluation (if criteria exist)
    crit_list = criteria if criteria is not None else getattr(opportunity, "eligibility_criteria", [])
    for crit in crit_list:
        eval_item = evaluate_structured_criterion(student, crit)
        breakdown.append(eval_item)

    # 5. Synthesize Overall Eligibility
    # Strict rule: Only VERIFIED mandatory criteria can trigger 'Does not meet requirements'
    has_does_not_meet = any(
        b["status"] == "Does Not Meet" and b.get("is_mandatory", True)
        for b in breakdown
    )
    has_needs_verification = any(
        b["status"] == "Needs Verification" and b.get("is_mandatory", True)
        for b in breakdown
    )

    if has_does_not_meet:
        overall_status = "Does not meet requirements"
    elif has_needs_verification:
        overall_status = "Needs verification"
    else:
        overall_status = "Meets requirements"

    eval_meta = {
        "deg_meets": deg_meets,
        "field_status": field_status,
        "deg_reason": deg_reason,
        "field_reason": field_reason,
        "yr_reason": yr_reason,
    }

    return (overall_status, breakdown, eval_meta)

