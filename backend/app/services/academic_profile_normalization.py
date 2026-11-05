"""
Academic and Demographic Normalization Utilities for Opportunity Intelligence AI.

Phase 2 — Stage 2.2A Implementation.
Provides isolated, deterministic, and pure validation and normalization functions for:
1. Academic Grade / GPA (Kenyan university honours, KCSE grades, numeric GPA scales, percentages).
2. Kenyan County of Origin (official 47 counties of Kenya, aliases, suffix cleaning).
3. Graduation Year (integer validation, temporal plausibility bounds).
4. Expected Graduation Date (year-only, month-and-year formats, canonical string representation).
5. Graduation Consistency Validation (cross-field verification between year of study,
   historical graduation year, and forward-looking expected graduation).

This module contains zero database dependencies, zero network dependencies, and zero LLM calls.
All functions are pure, deterministic, and strictly type-annotated.
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime


# ============================================================================
# 1. ENUMS AND DATA STRUCTURES
# ============================================================================

class NormalizationStatus(str, Enum):
    """Result status of a normalization or validation operation."""
    NORMALIZED = "NORMALIZED"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID = "INVALID"
    MISSING = "MISSING"


class GradingSystem(str, Enum):
    """Categorized academic grading systems."""
    KENYAN_UNIVERSITY_HONOURS = "KENYAN_UNIVERSITY_HONOURS"
    KCSE = "KCSE"
    NUMERIC_GPA = "NUMERIC_GPA"
    PERCENTAGE = "PERCENTAGE"
    UNKNOWN = "UNKNOWN"


class CanonicalHonours(str, Enum):
    """Canonical British / Kenyan university honours degree classifications."""
    FIRST_CLASS = "FIRST_CLASS"
    UPPER_SECOND = "UPPER_SECOND"
    LOWER_SECOND = "LOWER_SECOND"
    PASS = "PASS"


class CanonicalKCSE(str, Enum):
    """Official 12-point Kenya Certificate of Secondary Education (KCSE) mean grades."""
    A = "A"
    A_MINUS = "A-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    C_PLUS = "C+"
    C = "C"
    C_MINUS = "C-"
    D_PLUS = "D+"
    D = "D"
    D_MINUS = "D-"
    E = "E"


class ConsistencyStatus(str, Enum):
    """Graduation cross-field consistency standing."""
    CONSISTENT = "CONSISTENT"
    WARNING = "WARNING"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class AcademicGradeResult:
    """Immutable result of academic grade or GPA normalization."""
    original_value: Optional[str]
    normalized_classification: Optional[str]
    grading_system: GradingSystem
    numeric_value: Optional[float]
    numeric_scale: Optional[float]
    status: NormalizationStatus
    message: str


@dataclass(frozen=True)
class CountyResult:
    """Immutable result of Kenyan county normalization."""
    original_value: Optional[str]
    canonical_name: Optional[str]
    county_number: Optional[int]
    status: NormalizationStatus
    message: str


@dataclass(frozen=True)
class GraduationYearResult:
    """Immutable result of graduation year validation."""
    original_value: Any
    year: Optional[int]
    status: NormalizationStatus
    message: str


@dataclass(frozen=True)
class ExpectedGraduationResult:
    """Immutable result of expected graduation normalization."""
    original_value: Optional[str]
    year: Optional[int]
    month: Optional[int]
    formatted: Optional[str]
    status: NormalizationStatus
    message: str


@dataclass(frozen=True)
class GraduationConsistencyResult:
    """Immutable result of cross-field graduation consistency validation."""
    status: ConsistencyStatus
    is_consistent: bool
    warnings: List[str]
    inferred_standing: Optional[str]


# ============================================================================
# 2. CENTRALIZED KENYAN COUNTIES REGISTRY (47 COUNTIES)
# ============================================================================

# Official 47 Counties of the Republic of Kenya (Constitution of Kenya, First Schedule)
KENYA_COUNTIES: Tuple[str, ...] = (
    "Mombasa",
    "Kwale",
    "Kilifi",
    "Tana River",
    "Lamu",
    "Taita/Taveta",
    "Garissa",
    "Wajir",
    "Mandera",
    "Marsabit",
    "Isiolo",
    "Meru",
    "Tharaka-Nithi",
    "Embu",
    "Kitui",
    "Machakos",
    "Makueni",
    "Nyandarua",
    "Nyeri",
    "Kirinyaga",
    "Murang'a",
    "Kiambu",
    "Turkana",
    "West Pokot",
    "Samburu",
    "Trans Nzoia",
    "Uasin Gishu",
    "Elgeyo/Marakwet",
    "Nandi",
    "Baringo",
    "Laikipia",
    "Nakuru",
    "Narok",
    "Kajiado",
    "Kericho",
    "Bomet",
    "Kakamega",
    "Vihiga",
    "Bungoma",
    "Busia",
    "Siaya",
    "Kisumu",
    "Homa Bay",
    "Migori",
    "Kisii",
    "Nyamira",
    "Nairobi City",
)

COUNTY_NUMBER_MAP: Dict[str, int] = {
    county: idx + 1 for idx, county in enumerate(KENYA_COUNTIES)
}

# Recognized aliases and alternative orthographies for Kenyan counties
COUNTY_ALIASES: Dict[str, str] = {
    # Taita / Taveta
    "taita taveta": "Taita/Taveta",
    "taita-taveta": "Taita/Taveta",
    "taita / taveta": "Taita/Taveta",
    "taita": "Taita/Taveta",
    "taveta": "Taita/Taveta",

    # Tharaka-Nithi
    "tharaka nithi": "Tharaka-Nithi",
    "tharaka-nithi": "Tharaka-Nithi",
    "tharaka - nithi": "Tharaka-Nithi",
    "tharaka/nithi": "Tharaka-Nithi",
    "tharaka": "Tharaka-Nithi",

    # Murang'a
    "muranga": "Murang'a",
    "murang’a": "Murang'a",
    "murang`a": "Murang'a",

    # Trans Nzoia
    "trans-nzoia": "Trans Nzoia",
    "trans nzoia": "Trans Nzoia",
    "transnzoia": "Trans Nzoia",

    # Elgeyo/Marakwet
    "elgeyo marakwet": "Elgeyo/Marakwet",
    "elgeyo-marakwet": "Elgeyo/Marakwet",
    "elgeyo / marakwet": "Elgeyo/Marakwet",
    "keiyo marakwet": "Elgeyo/Marakwet",
    "keiyo-marakwet": "Elgeyo/Marakwet",

    # Homa Bay
    "homabay": "Homa Bay",
    "homa-bay": "Homa Bay",
    "homa bay": "Homa Bay",

    # Nairobi City
    "nairobi": "Nairobi City",
    "nairobi city": "Nairobi City",
    "nrb": "Nairobi City",
}


# ============================================================================
# 3. ACADEMIC GRADE NORMALIZATION CONSTANTS & ALIASES
# ============================================================================

HONOURS_ALIAS_MAP: Dict[str, CanonicalHonours] = {
    # First Class Honours
    "first class": CanonicalHonours.FIRST_CLASS,
    "first class honours": CanonicalHonours.FIRST_CLASS,
    "first class honors": CanonicalHonours.FIRST_CLASS,
    "1st class": CanonicalHonours.FIRST_CLASS,
    "1st class honours": CanonicalHonours.FIRST_CLASS,
    "first": CanonicalHonours.FIRST_CLASS,
    "1:1": CanonicalHonours.FIRST_CLASS,
    "1.1": CanonicalHonours.FIRST_CLASS,
    "distinction": CanonicalHonours.FIRST_CLASS,
    "summa cum laude": CanonicalHonours.FIRST_CLASS,

    # Upper Second Class Honours (2:1)
    "second class upper": CanonicalHonours.UPPER_SECOND,
    "second class honours upper division": CanonicalHonours.UPPER_SECOND,
    "second class honors upper division": CanonicalHonours.UPPER_SECOND,
    "second class honours (upper division)": CanonicalHonours.UPPER_SECOND,
    "second class (upper division)": CanonicalHonours.UPPER_SECOND,
    "second upper": CanonicalHonours.UPPER_SECOND,
    "upper second": CanonicalHonours.UPPER_SECOND,
    "upper second class": CanonicalHonours.UPPER_SECOND,
    "upper second class honours": CanonicalHonours.UPPER_SECOND,
    "2:1": CanonicalHonours.UPPER_SECOND,
    "2.1": CanonicalHonours.UPPER_SECOND,
    "2nd upper": CanonicalHonours.UPPER_SECOND,
    "upper 2nd": CanonicalHonours.UPPER_SECOND,
    "magna cum laude": CanonicalHonours.UPPER_SECOND,

    # Lower Second Class Honours (2:2)
    "second class lower": CanonicalHonours.LOWER_SECOND,
    "second class honours lower division": CanonicalHonours.LOWER_SECOND,
    "second class honors lower division": CanonicalHonours.LOWER_SECOND,
    "second class honours (lower division)": CanonicalHonours.LOWER_SECOND,
    "second class (lower division)": CanonicalHonours.LOWER_SECOND,
    "second lower": CanonicalHonours.LOWER_SECOND,
    "lower second": CanonicalHonours.LOWER_SECOND,
    "lower second class": CanonicalHonours.LOWER_SECOND,
    "lower second class honours": CanonicalHonours.LOWER_SECOND,
    "2:2": CanonicalHonours.LOWER_SECOND,
    "2.2": CanonicalHonours.LOWER_SECOND,
    "2nd lower": CanonicalHonours.LOWER_SECOND,
    "lower 2nd": CanonicalHonours.LOWER_SECOND,
    "cum laude": CanonicalHonours.LOWER_SECOND,

    # Pass
    "pass": CanonicalHonours.PASS,
    "pass degree": CanonicalHonours.PASS,
    "ordinary pass": CanonicalHonours.PASS,
    "general pass": CanonicalHonours.PASS,
}

KCSE_GRADE_MAP: Dict[str, CanonicalKCSE] = {
    "a": CanonicalKCSE.A,
    "a-": CanonicalKCSE.A_MINUS,
    "b+": CanonicalKCSE.B_PLUS,
    "b": CanonicalKCSE.B,
    "b-": CanonicalKCSE.B_MINUS,
    "c+": CanonicalKCSE.C_PLUS,
    "c": CanonicalKCSE.C,
    "c-": CanonicalKCSE.C_MINUS,
    "d+": CanonicalKCSE.D_PLUS,
    "d": CanonicalKCSE.D,
    "d-": CanonicalKCSE.D_MINUS,
    "e": CanonicalKCSE.E,
}

MONTH_NAME_TO_INT: Dict[str, int] = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12
}

INT_TO_MONTH_NAME: Dict[int, str] = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}


# ============================================================================
# 4. IMPLEMENTATION OF NORMALIZATION UTILITIES
# ============================================================================

def normalize_academic_grade(
    value: Optional[str],
    grading_system: Optional[str] = None,
    numeric_scale: Optional[float] = None,
    institution: Optional[str] = None
) -> AcademicGradeResult:
    """
    Normalizes academic grades and GPA across Kenyan university honours, KCSE secondary
    education scales, declared numeric GPA scales, and percentages.

    Guarantees:
    - Never equates KCSE grades with university GPA.
    - Never converts a numeric GPA into an honours tier unless an explicit institution
      policy is supplied.
    - Preserves missing values as MISSING without assuming a failing grade.
    - Validates numeric GPAs strictly against their declared or parsed scale.
    """
    if value is None or not str(value).strip():
        return AcademicGradeResult(
            original_value=value,
            normalized_classification=None,
            grading_system=GradingSystem.UNKNOWN,
            numeric_value=None,
            numeric_scale=None,
            status=NormalizationStatus.MISSING,
            message="Academic grade or GPA is missing."
        )

    raw_str = str(value).strip()
    norm_text = raw_str.lower()

    # Clean superfluous punctuation and wording
    norm_cleaned = re.sub(r'[\(\)\[\],]', ' ', norm_text)
    norm_cleaned = re.sub(r'\s+-\s+', ' ', norm_cleaned)
    norm_cleaned = re.sub(r'\s+', ' ', norm_cleaned).strip()

    # ------------------------------------------------------------------------
    # 1. Percentage Grade Format (e.g. "78%", "78 percent", "78 / 100")
    # ------------------------------------------------------------------------
    pct_match = re.search(r'^(\d+(?:\.\d+)?)\s*(?:%|percent|\/\s*100)$', norm_cleaned)
    if pct_match:
        pct_val = float(pct_match.group(1))
        if 0.0 <= pct_val <= 100.0:
            return AcademicGradeResult(
                original_value=raw_str,
                normalized_classification=f"{pct_val:.1f}%",
                grading_system=GradingSystem.PERCENTAGE,
                numeric_value=pct_val,
                numeric_scale=100.0,
                status=NormalizationStatus.NORMALIZED,
                message=f"Percentage grade {pct_val:.1f}% recognized."
            )
        else:
            return AcademicGradeResult(
                original_value=raw_str,
                normalized_classification=None,
                grading_system=GradingSystem.PERCENTAGE,
                numeric_value=pct_val,
                numeric_scale=100.0,
                status=NormalizationStatus.INVALID,
                message=f"Percentage {pct_val} is outside valid 0-100 range."
            )

    # ------------------------------------------------------------------------
    # 2. University Honours Classification
    # ------------------------------------------------------------------------
    # Direct match in honours dictionary
    if norm_cleaned in HONOURS_ALIAS_MAP:
        h_enum = HONOURS_ALIAS_MAP[norm_cleaned]
        return AcademicGradeResult(
            original_value=raw_str,
            normalized_classification=h_enum.value,
            grading_system=GradingSystem.KENYAN_UNIVERSITY_HONOURS,
            numeric_value=None,
            numeric_scale=None,
            status=NormalizationStatus.NORMALIZED,
            message=f"Kenyan university honours classification '{h_enum.value}' recognized."
        )

    # Substring / pattern matching for honours with surrounding words
    for alias, h_enum in HONOURS_ALIAS_MAP.items():
        if len(alias) >= 4 and re.search(rf'\b{re.escape(alias)}\b', norm_cleaned):
            return AcademicGradeResult(
                original_value=raw_str,
                normalized_classification=h_enum.value,
                grading_system=GradingSystem.KENYAN_UNIVERSITY_HONOURS,
                numeric_value=None,
                numeric_scale=None,
                status=NormalizationStatus.NORMALIZED,
                message=f"Kenyan university honours classification '{h_enum.value}' recognized from text."
            )

    # ------------------------------------------------------------------------
    # 3. KCSE Secondary School Mean Grade
    # ------------------------------------------------------------------------
    # Explicit KCSE prefix check (e.g. "KCSE B+", "KCSE: A-", "KCSE Grade B")
    kcse_prefix_match = re.search(r'(?:kcse|mean\s+grade|grade)[:\s]+([a-e][+-]?)', norm_cleaned)
    if kcse_prefix_match:
        grade_token = kcse_prefix_match.group(1).lower()
        if grade_token in KCSE_GRADE_MAP:
            kcse_enum = KCSE_GRADE_MAP[grade_token]
            return AcademicGradeResult(
                original_value=raw_str,
                normalized_classification=kcse_enum.value,
                grading_system=GradingSystem.KCSE,
                numeric_value=None,
                numeric_scale=None,
                status=NormalizationStatus.NORMALIZED,
                message=f"KCSE mean grade '{kcse_enum.value}' recognized."
            )

    # Kenyan verbal qualifiers for KCSE: "a plain", "b plus", "c minus", "b+ (plus)"
    kcse_verbal_match = re.search(r'\b([a-e])(?:\s*([+-]))?\s*(plus|\+|minus|\-|plain)\b', norm_cleaned)
    if kcse_verbal_match:
        letter = kcse_verbal_match.group(1).lower()
        sign = kcse_verbal_match.group(2)
        qual = kcse_verbal_match.group(3).lower()
        if sign == "+" or qual in ["plus", "+"]:
            symbol = "+"
        elif sign == "-" or qual in ["minus", "-"]:
            symbol = "-"
        else:
            symbol = ""
        cand_key = f"{letter}{symbol}"
        if cand_key in KCSE_GRADE_MAP:
            kcse_enum = KCSE_GRADE_MAP[cand_key]
            return AcademicGradeResult(
                original_value=raw_str,
                normalized_classification=kcse_enum.value,
                grading_system=GradingSystem.KCSE,
                numeric_value=None,
                numeric_scale=None,
                status=NormalizationStatus.NORMALIZED,
                message=f"KCSE grade '{kcse_enum.value}' recognized from verbal qualifier."
            )

    # Exact KCSE letter with plus/minus (e.g. "B+", "A-", "C+", "D-")
    # Plus/minus grades are unambiguous KCSE grades in Kenya
    exact_pm_match = re.search(r'^([a-d][+-])$', norm_cleaned)
    if exact_pm_match:
        token = exact_pm_match.group(1).lower()
        if token in KCSE_GRADE_MAP:
            kcse_enum = KCSE_GRADE_MAP[token]
            return AcademicGradeResult(
                original_value=raw_str,
                normalized_classification=kcse_enum.value,
                grading_system=GradingSystem.KCSE,
                numeric_value=None,
                numeric_scale=None,
                status=NormalizationStatus.NORMALIZED,
                message=f"KCSE grade '{kcse_enum.value}' recognized."
            )

    # ------------------------------------------------------------------------
    # 4. Numeric GPA with Declared Scale
    # ------------------------------------------------------------------------
    # Pattern: "3.8/4.0", "3.8 / 4.0", "3.8 out of 4", "GPA 3.8/4.0", "-1.5/4.0"
    gpa_scale_match = re.search(
        r'(?:gpa[:\s]*)?(-?\d+(?:\.\d+)?)\s*(?:\/|\bout\s+of\b)\s*(-?\d+(?:\.\d+)?)',
        norm_cleaned
    )
    if gpa_scale_match:
        val_f = float(gpa_scale_match.group(1))
        scale_f = float(gpa_scale_match.group(2))
        if scale_f <= 0:
            return AcademicGradeResult(
                original_value=raw_str,
                normalized_classification=None,
                grading_system=GradingSystem.NUMERIC_GPA,
                numeric_value=val_f,
                numeric_scale=scale_f,
                status=NormalizationStatus.INVALID,
                message="GPA scale must be strictly positive."
            )
        if val_f < 0:
            return AcademicGradeResult(
                original_value=raw_str,
                normalized_classification=None,
                grading_system=GradingSystem.NUMERIC_GPA,
                numeric_value=val_f,
                numeric_scale=scale_f,
                status=NormalizationStatus.INVALID,
                message=f"Numeric GPA {val_f} cannot be negative."
            )
        if val_f > scale_f:
            return AcademicGradeResult(
                original_value=raw_str,
                normalized_classification=None,
                grading_system=GradingSystem.NUMERIC_GPA,
                numeric_value=val_f,
                numeric_scale=scale_f,
                status=NormalizationStatus.INVALID,
                message=f"Numeric GPA {val_f} exceeds declared scale of {scale_f}."
            )
        return AcademicGradeResult(
            original_value=raw_str,
            normalized_classification=f"{val_f:.2f}/{scale_f:.1f}",
            grading_system=GradingSystem.NUMERIC_GPA,
            numeric_value=val_f,
            numeric_scale=scale_f,
            status=NormalizationStatus.NORMALIZED,
            message=f"Numeric GPA {val_f:.2f} on a {scale_f:.1f} scale recognized."
        )

    # Numeric GPA with caller-supplied scale argument
    bare_numeric_match = re.search(r'^(?:gpa[:\s]*)?(\d+(?:\.\d+)?)$', norm_cleaned)
    if bare_numeric_match:
        val_f = float(bare_numeric_match.group(1))
        if numeric_scale is not None and numeric_scale > 0:
            if val_f > numeric_scale:
                return AcademicGradeResult(
                    original_value=raw_str,
                    normalized_classification=None,
                    grading_system=GradingSystem.NUMERIC_GPA,
                    numeric_value=val_f,
                    numeric_scale=numeric_scale,
                    status=NormalizationStatus.INVALID,
                    message=f"Numeric GPA {val_f} exceeds declared scale of {numeric_scale}."
                )
            return AcademicGradeResult(
                original_value=raw_str,
                normalized_classification=f"{val_f:.2f}/{numeric_scale:.1f}",
                grading_system=GradingSystem.NUMERIC_GPA,
                numeric_value=val_f,
                numeric_scale=numeric_scale,
                status=NormalizationStatus.NORMALIZED,
                message=f"Numeric GPA {val_f:.2f} on declared {numeric_scale:.1f} scale recognized."
            )
        else:
            # Ambiguous numeric GPA without explicit scale
            return AcademicGradeResult(
                original_value=raw_str,
                normalized_classification=None,
                grading_system=GradingSystem.NUMERIC_GPA,
                numeric_value=val_f,
                numeric_scale=None,
                status=NormalizationStatus.AMBIGUOUS,
                message=f"Numeric GPA {val_f} provided without an explicit scale (e.g. /4.0 or /5.0)."
            )

    # ------------------------------------------------------------------------
    # 5. Single Bare Letter (e.g. "A", "B", "C", "D", "E")
    # ------------------------------------------------------------------------
    # A standalone single letter without plus/minus or "KCSE" prefix is ambiguous
    # between KCSE mean grade and standard American letter grade.
    if re.fullmatch(r'^[a-e]$', norm_cleaned):
        token_upper = norm_cleaned.upper()
        if grading_system == "KCSE":
            return AcademicGradeResult(
                original_value=raw_str,
                normalized_classification=token_upper,
                grading_system=GradingSystem.KCSE,
                numeric_value=None,
                numeric_scale=None,
                status=NormalizationStatus.NORMALIZED,
                message=f"KCSE plain grade '{token_upper}' recognized under explicit KCSE system."
            )
        return AcademicGradeResult(
            original_value=raw_str,
            normalized_classification=token_upper,
            grading_system=GradingSystem.UNKNOWN,
            numeric_value=None,
            numeric_scale=None,
            status=NormalizationStatus.AMBIGUOUS,
            message=f"Single letter '{token_upper}' is ambiguous between KCSE mean grade and letter grade."
        )

    # ------------------------------------------------------------------------
    # 6. Unrecognized or Unsupported Format
    # ------------------------------------------------------------------------
    return AcademicGradeResult(
        original_value=raw_str,
        normalized_classification=None,
        grading_system=GradingSystem.UNKNOWN,
        numeric_value=None,
        numeric_scale=None,
        status=NormalizationStatus.INVALID,
        message=f"Unrecognized academic grade or GPA format: '{raw_str}'."
    )


def normalize_county(value: Optional[str]) -> CountyResult:
    """
    Normalizes a Kenyan county name against the 47 official counties of Kenya.

    Guarantees:
    - Case-insensitive matching and whitespace trimming.
    - Strips 'County' prefix or suffix cleanly.
    - Recognizes common alternative orthographies (e.g. 'Homabay', 'Muranga', 'Trans-Nzoia').
    - Returns canonical name and official county number (1 to 47).
    - Preserves missing values as MISSING without hallucinating a county.
    """
    if value is None or not str(value).strip():
        return CountyResult(
            original_value=value,
            canonical_name=None,
            county_number=None,
            status=NormalizationStatus.MISSING,
            message="County of origin is missing or empty."
        )

    raw_str = str(value).strip()
    norm = raw_str.lower()

    # Clean optional 'County' prefix or suffix
    norm = re.sub(r'^(?:county\s+of\s+)', '', norm).strip()
    norm = re.sub(r'(?:\s+county)$', '', norm).strip()
    norm = re.sub(r'\s+', ' ', norm)

    # Direct match in canonical set (lowercased)
    canonical_lower_map = {c.lower(): c for c in KENYA_COUNTIES}
    if norm in canonical_lower_map:
        canon_name = canonical_lower_map[norm]
        return CountyResult(
            original_value=raw_str,
            canonical_name=canon_name,
            county_number=COUNTY_NUMBER_MAP[canon_name],
            status=NormalizationStatus.NORMALIZED,
            message=f"Canonical county '{canon_name}' (County #{COUNTY_NUMBER_MAP[canon_name]}) recognized."
        )

    # Match in alias dictionary
    if norm in COUNTY_ALIASES:
        canon_name = COUNTY_ALIASES[norm]
        return CountyResult(
            original_value=raw_str,
            canonical_name=canon_name,
            county_number=COUNTY_NUMBER_MAP[canon_name],
            status=NormalizationStatus.NORMALIZED,
            message=f"County alias '{raw_str}' normalized to canonical '{canon_name}' (County #{COUNTY_NUMBER_MAP[canon_name]})."
        )

    # Unrecognized county
    return CountyResult(
        original_value=raw_str,
        canonical_name=None,
        county_number=None,
        status=NormalizationStatus.INVALID,
        message=f"'{raw_str}' is not recognized as one of the 47 official Kenyan counties."
    )


def validate_graduation_year(
    value: Any,
    min_year: int = 1970,
    max_year: int = 2035
) -> GraduationYearResult:
    """
    Validates a student's graduation year.

    Guarantees:
    - Accepts valid integer years or 4-digit numeric strings.
    - Rejects malformed strings, floats, and non-numeric representations.
    - Validates against supported temporal range (default 1970 to 2035).
    - Preserves None / empty inputs as MISSING.
    - Never infers eligibility or standing.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return GraduationYearResult(
            original_value=value,
            year=None,
            status=NormalizationStatus.MISSING,
            message="Graduation year is not provided."
        )

    year_int: Optional[int] = None
    if isinstance(value, int) and not isinstance(value, bool):
        year_int = value
    elif isinstance(value, str):
        cleaned = value.strip()
        if re.fullmatch(r'\d{4}', cleaned):
            year_int = int(cleaned)
        else:
            return GraduationYearResult(
                original_value=value,
                year=None,
                status=NormalizationStatus.INVALID,
                message=f"Graduation year must be a 4-digit integer; got '{value}'."
            )
    else:
        return GraduationYearResult(
            original_value=value,
            year=None,
            status=NormalizationStatus.INVALID,
            message=f"Invalid graduation year type: {type(value).__name__}."
        )

    if year_int < min_year or year_int > max_year:
        return GraduationYearResult(
            original_value=value,
            year=None,
            status=NormalizationStatus.INVALID,
            message=f"Graduation year {year_int} is outside supported window ({min_year} - {max_year})."
        )

    return GraduationYearResult(
        original_value=value,
        year=year_int,
        status=NormalizationStatus.NORMALIZED,
        message=f"Valid graduation year: {year_int}."
    )


def normalize_expected_graduation(
    value: Optional[str],
    min_year: int = 1970,
    max_year: int = 2035
) -> ExpectedGraduationResult:
    """
    Normalizes a student's expected graduation date into a standardized representation.

    Supported Formats:
    - Year-only: '2026' -> formatted '2026', month None
    - Year-Month ISO: '2026-12' -> formatted 'December 2026', month 12
    - Full or Abbreviated Month and Year: 'December 2026', 'Nov 2026' -> formatted 'November 2026', month 11
    - Slash Month/Year: '12/2026' -> formatted 'December 2026', month 12

    Guarantees:
    - Never invents an artificial day when only a month is provided.
    - Rejects invalid months (e.g. 13) and malformed dates.
    - Preserves None / empty inputs as MISSING.
    """
    if value is None or not str(value).strip():
        return ExpectedGraduationResult(
            original_value=value,
            year=None,
            month=None,
            formatted=None,
            status=NormalizationStatus.MISSING,
            message="Expected graduation date is missing."
        )

    raw_str = str(value).strip()
    norm = raw_str.lower()
    norm = re.sub(r'[\.,]', '', norm).strip()

    # 1. 4-digit Year Only (e.g. "2026")
    if re.fullmatch(r'\d{4}', norm):
        y = int(norm)
        if min_year <= y <= max_year:
            return ExpectedGraduationResult(
                original_value=raw_str,
                year=y,
                month=None,
                formatted=str(y),
                status=NormalizationStatus.NORMALIZED,
                message=f"Expected graduation year {y} recognized."
            )
        else:
            return ExpectedGraduationResult(
                original_value=raw_str,
                year=None,
                month=None,
                formatted=None,
                status=NormalizationStatus.INVALID,
                message=f"Expected graduation year {y} is outside supported window ({min_year} - {max_year})."
            )

    # 2. ISO Year-Month (e.g. "2026-12", "2026/05")
    iso_match = re.fullmatch(r'(\d{4})[-/](\d{1,2})', norm)
    if iso_match:
        y = int(iso_match.group(1))
        m = int(iso_match.group(2))
        if not (1 <= m <= 12):
            return ExpectedGraduationResult(
                original_value=raw_str,
                year=None,
                month=None,
                formatted=None,
                status=NormalizationStatus.INVALID,
                message=f"Month {m} is invalid (must be between 1 and 12)."
            )
        if not (min_year <= y <= max_year):
            return ExpectedGraduationResult(
                original_value=raw_str,
                year=None,
                month=None,
                formatted=None,
                status=NormalizationStatus.INVALID,
                message=f"Year {y} is outside supported window ({min_year} - {max_year})."
            )
        formatted = f"{INT_TO_MONTH_NAME[m]} {y}"
        return ExpectedGraduationResult(
            original_value=raw_str,
            year=y,
            month=m,
            formatted=formatted,
            status=NormalizationStatus.NORMALIZED,
            message=f"Expected graduation date '{formatted}' recognized."
        )

    # 3. Slash Month/Year (e.g. "12/2026", "5/2027")
    slash_match = re.fullmatch(r'(\d{1,2})[-/](\d{4})', norm)
    if slash_match:
        m = int(slash_match.group(1))
        y = int(slash_match.group(2))
        if not (1 <= m <= 12):
            return ExpectedGraduationResult(
                original_value=raw_str,
                year=None,
                month=None,
                formatted=None,
                status=NormalizationStatus.INVALID,
                message=f"Month {m} is invalid (must be between 1 and 12)."
            )
        if not (min_year <= y <= max_year):
            return ExpectedGraduationResult(
                original_value=raw_str,
                year=None,
                month=None,
                formatted=None,
                status=NormalizationStatus.INVALID,
                message=f"Year {y} is outside supported window ({min_year} - {max_year})."
            )
        formatted = f"{INT_TO_MONTH_NAME[m]} {y}"
        return ExpectedGraduationResult(
            original_value=raw_str,
            year=y,
            month=m,
            formatted=formatted,
            status=NormalizationStatus.NORMALIZED,
            message=f"Expected graduation date '{formatted}' recognized."
        )

    # 4. Text Month and Year (e.g. "December 2026", "Nov 2026", "2026 December")
    month_year_match = re.fullmatch(r'([a-z]+)\s+(\d{4})', norm)
    if not month_year_match:
        # Try reversed order: "2026 December"
        month_year_match = re.fullmatch(r'(\d{4})\s+([a-z]+)', norm)
        if month_year_match:
            y_str, m_str = month_year_match.group(1), month_year_match.group(2)
        else:
            y_str, m_str = None, None
    else:
        m_str, y_str = month_year_match.group(1), month_year_match.group(2)

    if m_str and y_str:
        if m_str not in MONTH_NAME_TO_INT:
            return ExpectedGraduationResult(
                original_value=raw_str,
                year=None,
                month=None,
                formatted=None,
                status=NormalizationStatus.INVALID,
                message=f"Unrecognized month name '{m_str}'."
            )
        m = MONTH_NAME_TO_INT[m_str]
        y = int(y_str)
        if not (min_year <= y <= max_year):
            return ExpectedGraduationResult(
                original_value=raw_str,
                year=None,
                month=None,
                formatted=None,
                status=NormalizationStatus.INVALID,
                message=f"Year {y} is outside supported window ({min_year} - {max_year})."
            )
        formatted = f"{INT_TO_MONTH_NAME[m]} {y}"
        return ExpectedGraduationResult(
            original_value=raw_str,
            year=y,
            month=m,
            formatted=formatted,
            status=NormalizationStatus.NORMALIZED,
            message=f"Expected graduation date '{formatted}' recognized."
        )

    return ExpectedGraduationResult(
        original_value=raw_str,
        year=None,
        month=None,
        formatted=None,
        status=NormalizationStatus.INVALID,
        message=f"Malformed expected graduation date format: '{raw_str}'."
    )


def validate_graduation_consistency(
    year_of_study: Optional[int],
    graduation_year: Optional[int],
    expected_graduation: Optional[str],
    current_year: Optional[int] = None
) -> GraduationConsistencyResult:
    """
    Cross-validates graduation attributes for internal consistency.

    Examines:
    - Current year of study (1 to 6)
    - Completed graduation year (historical)
    - Expected graduation date (forward-looking)

    Guarantees:
    - Never assumes every university course has the same duration.
    - Yields WARNING / NEEDS_VERIFICATION on contradictions; never automatically rejects.
    """
    if current_year is None:
        current_year = datetime.now().year

    warnings: List[str] = []

    # Validate individual components
    grad_res = validate_graduation_year(graduation_year)
    exp_res = normalize_expected_graduation(expected_graduation)

    has_grad = grad_res.status == NormalizationStatus.NORMALIZED
    has_exp = exp_res.status == NormalizationStatus.NORMALIZED

    # Scenario 1: Completely missing graduation information
    if not has_grad and not has_exp:
        return GraduationConsistencyResult(
            status=ConsistencyStatus.INCOMPLETE,
            is_consistent=True,
            warnings=["Neither graduation year nor expected graduation date is recorded."],
            inferred_standing="UNKNOWN"
        )

    # Scenario 2: Continuing student in early years claiming past completed graduation
    if year_of_study is not None and year_of_study in [1, 2]:
        if has_grad and grad_res.year is not None and grad_res.year < current_year:
            warnings.append(
                f"Student in Year {year_of_study} specifies a historical graduation year ({grad_res.year}) in the past."
            )

    # Scenario 3: Contradiction between graduation_year and expected_graduation
    if has_grad and has_exp and grad_res.year is not None and exp_res.year is not None:
        # A difference of more than 1 calendar year indicates a significant discrepancy
        if abs(grad_res.year - exp_res.year) > 1:
            warnings.append(
                f"Supplied graduation year ({grad_res.year}) conflicts with expected graduation year ({exp_res.year})."
            )

    # Scenario 4: Senior / finalist student with expected graduation date excessively far in the future
    if year_of_study is not None and year_of_study >= 4 and has_exp and exp_res.year is not None:
        if exp_res.year > current_year + 4:
            warnings.append(
                f"Year {year_of_study} student indicates an expected graduation year ({exp_res.year}) over 4 years in the future."
            )

    # Determine inferred standing
    if has_grad and grad_res.year is not None and grad_res.year <= current_year and (year_of_study is None or year_of_study >= 4):
        inferred = "GRADUATED_ALUMNI"
    elif year_of_study is not None and year_of_study < 4:
        inferred = "CONTINUING_STUDENT"
    elif has_exp and exp_res.year is not None and exp_res.year >= current_year:
        inferred = "FINALIST_OR_CONTINUING"
    else:
        inferred = "AMBIGUOUS"

    if warnings:
        return GraduationConsistencyResult(
            status=ConsistencyStatus.NEEDS_VERIFICATION,
            is_consistent=False,
            warnings=warnings,
            inferred_standing=inferred
        )

    return GraduationConsistencyResult(
        status=ConsistencyStatus.CONSISTENT,
        is_consistent=True,
        warnings=[],
        inferred_standing=inferred
    )
