"""
Unit tests for Academic and Demographic Profile Normalization Utilities.

Phase 2 — Stage 2.2A Implementation.
Covers:
1. Academic grade & GPA normalization (Honours, KCSE, numeric GPA with scale, percentages, invalid/missing/ambiguous).
2. Kenyan county normalization (all 47 canonical counties, aliases, suffix removal, invalid, missing).
3. Graduation year validation (integer parsing, bounds check, invalid types, missing).
4. Expected graduation normalization (year-only, month-year text, ISO format, slash format, invalid months, malformed).
5. Cross-field graduation consistency validation (contradictions, early year with past graduation, missing data).
"""

import pytest
from app.services.academic_profile_normalization import (
    KENYA_COUNTIES,
    COUNTY_NUMBER_MAP,
    NormalizationStatus,
    GraduationYearResult,
    GraduationConsistencyResult,
    ExpectedGraduationResult,
    CountyResult,
    AcademicGradeResult,
    GradingSystem,
    CanonicalHonours,
    CanonicalKCSE,
    ConsistencyStatus,
    normalize_academic_grade,
    normalize_county,
    validate_graduation_year,
    normalize_expected_graduation,
    validate_graduation_consistency,
)


# ============================================================================
# 1. ACADEMIC GRADE & GPA NORMALIZATION TESTS
# ============================================================================

class TestAcademicGradeNormalization:
    """Tests for normalize_academic_grade covering Honours, KCSE, GPA and error cases."""

    @pytest.mark.parametrize("input_val", [
        "First Class",
        "First Class Honours",
        "first class honors",
        "1st Class Honours",
        "1st class",
        "First",
        "1:1",
        "1.1",
        "Distinction",
        "Summa Cum Laude",
        "BSc in Computer Science (First Class Honours)",
    ])
    def test_first_class_aliases(self, input_val):
        """Scenario 1: Recognize all recognized aliases for First Class Honours."""
        res = normalize_academic_grade(input_val)
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.grading_system == GradingSystem.KENYAN_UNIVERSITY_HONOURS
        assert res.normalized_classification == CanonicalHonours.FIRST_CLASS.value
        assert res.numeric_value is None

    @pytest.mark.parametrize("input_val", [
        "Upper Second",
        "Second Class Upper",
        "Second Class Honours Upper Division",
        "Second Class Honours (Upper Division)",
        "Second Upper",
        "upper second class",
        "2:1",
        "2.1",
        "2nd Upper",
        "Magna Cum Laude",
        "Second Class - Upper Division",
    ])
    def test_upper_second_aliases(self, input_val):
        """Scenario 2: Recognize all recognized aliases for Upper Second Class Honours."""
        res = normalize_academic_grade(input_val)
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.grading_system == GradingSystem.KENYAN_UNIVERSITY_HONOURS
        assert res.normalized_classification == CanonicalHonours.UPPER_SECOND.value
        assert res.numeric_value is None

    @pytest.mark.parametrize("input_val", [
        "Lower Second",
        "Second Class Lower",
        "Second Class Honours Lower Division",
        "Second Class Honours (Lower Division)",
        "Second Lower",
        "lower second class",
        "2:2",
        "2.2",
        "2nd Lower",
        "Cum Laude",
        "Second Class - Lower Division",
    ])
    def test_lower_second_aliases(self, input_val):
        """Scenario 3: Recognize all recognized aliases for Lower Second Class Honours."""
        res = normalize_academic_grade(input_val)
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.grading_system == GradingSystem.KENYAN_UNIVERSITY_HONOURS
        assert res.normalized_classification == CanonicalHonours.LOWER_SECOND.value
        assert res.numeric_value is None

    @pytest.mark.parametrize("input_val", [
        "Pass",
        "Pass Degree",
        "Ordinary Pass",
        "General Pass",
    ])
    def test_pass_aliases(self, input_val):
        """Scenario 4: Recognize all recognized aliases for Pass classification."""
        res = normalize_academic_grade(input_val)
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.grading_system == GradingSystem.KENYAN_UNIVERSITY_HONOURS
        assert res.normalized_classification == CanonicalHonours.PASS.value
        assert res.numeric_value is None

    @pytest.mark.parametrize("input_val,expected_kcse", [
        ("KCSE A", "A"),
        ("KCSE: A-", "A-"),
        ("KCSE Grade B+", "B+"),
        ("Mean Grade B", "B"),
        ("B+ (Plus)", "B+"),
        ("A- (Minus)", "A-"),
        ("B Plain", "B"),
        ("C Minus", "C-"),
        ("D+", "D+"),
        ("A-", "A-"),
        ("B+", "B+"),
        ("C-", "C-"),
    ])
    def test_kcse_grade_recognition(self, input_val, expected_kcse):
        """Scenario 5: Recognize KCSE secondary school grades and qualifiers."""
        res = normalize_academic_grade(input_val)
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.grading_system == GradingSystem.KCSE
        assert res.normalized_classification == expected_kcse

    @pytest.mark.parametrize("input_val,expected_val,expected_scale", [
        ("3.8/4.0", 3.8, 4.0),
        ("3.5 / 4.0", 3.5, 4.0),
        ("GPA 3.9 out of 4.0", 3.9, 4.0),
        ("4.5/5.0", 4.5, 5.0),
        ("2.8 / 4", 2.8, 4.0),
    ])
    def test_valid_numeric_gpa_with_declared_scale(self, input_val, expected_val, expected_scale):
        """Scenario 6: Valid numeric GPA values with an explicitly declared scale."""
        res = normalize_academic_grade(input_val)
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.grading_system == GradingSystem.NUMERIC_GPA
        assert res.numeric_value == expected_val
        assert res.numeric_scale == expected_scale
        assert res.normalized_classification == f"{expected_val:.2f}/{expected_scale:.1f}"

    def test_valid_numeric_gpa_with_caller_supplied_scale(self):
        """Scenario 6b: Valid numeric GPA with caller-supplied scale argument."""
        res = normalize_academic_grade("3.65", numeric_scale=4.0)
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.grading_system == GradingSystem.NUMERIC_GPA
        assert res.numeric_value == 3.65
        assert res.numeric_scale == 4.0

    @pytest.mark.parametrize("input_val", [
        "4.8/4.0",      # Exceeds scale
        "-1.5/4.0",     # Negative
        "3.5/0.0",      # Zero scale
        "6.0 out of 5", # Exceeds scale
    ])
    def test_invalid_numeric_gpa(self, input_val):
        """Scenario 7: Reject numeric GPA values exceeding their scale or with negative/zero scale."""
        res = normalize_academic_grade(input_val)
        assert res.status == NormalizationStatus.INVALID
        assert res.grading_system == GradingSystem.NUMERIC_GPA

    @pytest.mark.parametrize("missing_val", [None, "", "   ", "\t\n"])
    def test_missing_grade(self, missing_val):
        """Scenario 8: Missing grade values remain MISSING without assuming a failing grade."""
        res = normalize_academic_grade(missing_val)
        assert res.status == NormalizationStatus.MISSING
        assert res.normalized_classification is None
        assert res.numeric_value is None

    @pytest.mark.parametrize("unknown_val", [
        "Unknown Grade",
        "Very Good Student",
        "Top Performer",
        "xyz-abc-123",
    ])
    def test_unknown_classification(self, unknown_val):
        """Scenario 9: Unrecognized grade inputs are marked INVALID."""
        res = normalize_academic_grade(unknown_val)
        assert res.status == NormalizationStatus.INVALID
        assert res.grading_system == GradingSystem.UNKNOWN
        assert res.normalized_classification is None

    def test_incompatible_grading_systems(self):
        """Scenario 10: Incompatible or ambiguous inputs are properly flagged."""
        # Bare letter 'B' without KCSE system flag is ambiguous
        res = normalize_academic_grade("B")
        assert res.status == NormalizationStatus.AMBIGUOUS
        assert res.grading_system == GradingSystem.UNKNOWN
        # When explicitly declared as KCSE
        res_kcse = normalize_academic_grade("B", grading_system="KCSE")
        assert res_kcse.status == NormalizationStatus.NORMALIZED
        assert res_kcse.grading_system == GradingSystem.KCSE
        assert res_kcse.normalized_classification == "B"

    def test_no_unsupported_gpa_to_honours_conversion(self):
        """Scenario 11: Critical rule - pure normalization never auto-converts GPA to honours."""
        res = normalize_academic_grade("3.85/4.0")
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.grading_system == GradingSystem.NUMERIC_GPA
        assert res.normalized_classification == "3.85/4.0"
        # Must NOT silently inject "FIRST_CLASS"
        assert res.normalized_classification != CanonicalHonours.FIRST_CLASS.value

    def test_percentage_grade_handling(self):
        """Edge Case: Percentage grade format (e.g. 78%)."""
        res = normalize_academic_grade("78%")
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.grading_system == GradingSystem.PERCENTAGE
        assert res.numeric_value == 78.0
        assert res.numeric_scale == 100.0


# ============================================================================
# 2. KENYAN COUNTY NORMALIZATION TESTS
# ============================================================================

class TestKenyanCountyNormalization:
    """Tests for normalize_county across all 47 counties, aliases, and edge cases."""

    def test_all_47_canonical_counties(self):
        """Scenario 12: Verify all 47 canonical Kenyan counties are recognized with exact code."""
        assert len(KENYA_COUNTIES) == 47
        for idx, county in enumerate(KENYA_COUNTIES, 1):
            res = normalize_county(county)
            assert res.status == NormalizationStatus.NORMALIZED, f"County {county} failed normalization."
            assert res.canonical_name == county
            assert res.county_number == idx
            assert COUNTY_NUMBER_MAP[county] == idx

    @pytest.mark.parametrize("input_val,expected_canonical", [
        ("nairobi", "Nairobi City"),
        ("NAIROBI", "Nairobi City"),
        ("kiambu", "Kiambu"),
        ("MOMBASA", "Mombasa"),
        ("kisumu", "Kisumu"),
        ("nakuru", "Nakuru"),
        ("TURKANA", "Turkana"),
    ])
    def test_case_insensitive_matching(self, input_val, expected_canonical):
        """Scenario 13: Case-insensitive county matching."""
        res = normalize_county(input_val)
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.canonical_name == expected_canonical

    @pytest.mark.parametrize("input_val,expected_canonical", [
        ("   Kiambu   ", "Kiambu"),
        ("\tMombasa\n", "Mombasa"),
        ("  Nairobi   City  ", "Nairobi City"),
    ])
    def test_whitespace_normalization(self, input_val, expected_canonical):
        """Scenario 14: Whitespace trimming and multi-space collapsing."""
        res = normalize_county(input_val)
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.canonical_name == expected_canonical

    @pytest.mark.parametrize("input_val,expected_canonical", [
        ("Kiambu County", "Kiambu"),
        ("County of Kiambu", "Kiambu"),
        ("NAIROBI COUNTY", "Nairobi City"),
        ("Homabay County", "Homa Bay"),
        ("Muranga County", "Murang'a"),
        ("county of Turkana", "Turkana"),
    ])
    def test_county_suffix_handling(self, input_val, expected_canonical):
        """Scenario 15: Clean 'County' and 'County of' prefixes and suffixes."""
        res = normalize_county(input_val)
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.canonical_name == expected_canonical

    @pytest.mark.parametrize("alias_val,expected_canonical", [
        ("Homabay", "Homa Bay"),
        ("homa-bay", "Homa Bay"),
        ("Muranga", "Murang'a"),
        ("Trans-Nzoia", "Trans Nzoia"),
        ("transnzoia", "Trans Nzoia"),
        ("Taita Taveta", "Taita/Taveta"),
        ("taita-taveta", "Taita/Taveta"),
        ("Tharaka Nithi", "Tharaka-Nithi"),
        ("Elgeyo Marakwet", "Elgeyo/Marakwet"),
        ("keiyo marakwet", "Elgeyo/Marakwet"),
        ("Nrb", "Nairobi City"),
    ])
    def test_county_aliases_and_orthographies(self, alias_val, expected_canonical):
        """Scenario 15b: Recognize common alternate orthographies and abbreviations."""
        res = normalize_county(alias_val)
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.canonical_name == expected_canonical

    @pytest.mark.parametrize("invalid_val", [
        "London",
        "Kampala",
        "California",
        "Unknown Region",
        "12345",
    ])
    def test_invalid_county(self, invalid_val):
        """Scenario 16: Reject unsupported or non-Kenyan geographical locations."""
        res = normalize_county(invalid_val)
        assert res.status == NormalizationStatus.INVALID
        assert res.canonical_name is None
        assert res.county_number is None

    @pytest.mark.parametrize("missing_val", [None, "", "   ", "\t"])
    def test_missing_county(self, missing_val):
        """Scenario 17: Return explicit MISSING status for empty or None county inputs."""
        res = normalize_county(missing_val)
        assert res.status == NormalizationStatus.MISSING
        assert res.canonical_name is None
        assert res.county_number is None


# ============================================================================
# 3. GRADUATION YEAR VALIDATION TESTS
# ============================================================================

class TestGraduationYearValidation:
    """Tests for validate_graduation_year."""

    @pytest.mark.parametrize("valid_input,expected_year", [
        (2024, 2024),
        (2026, 2026),
        ("2024", 2024),
        ("2027", 2027),
        ("  2025  ", 2025),
        (1995, 1995),
    ])
    def test_valid_graduation_year(self, valid_input, expected_year):
        """Scenario 18: Accept valid 4-digit integer years."""
        res = validate_graduation_year(valid_input)
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.year == expected_year

    @pytest.mark.parametrize("invalid_input", [
        "twenty twenty-four",
        "2024.5",
        2024.5,
        "24",
        "1850",  # Prior to minimum temporal bound (1970)
        "2099",  # Beyond maximum temporal bound (2035)
        True,    # Booleans inherit from int in Python but must be rejected
        [2024],
    ])
    def test_invalid_graduation_year(self, invalid_input):
        """Scenario 19: Reject malformed strings, floats, booleans, and out-of-range years."""
        res = validate_graduation_year(invalid_input)
        assert res.status == NormalizationStatus.INVALID
        assert res.year is None

    @pytest.mark.parametrize("missing_val", [None, "", "   "])
    def test_missing_graduation_year(self, missing_val):
        """Scenario 20: Missing graduation year returns MISSING status with None."""
        res = validate_graduation_year(missing_val)
        assert res.status == NormalizationStatus.MISSING
        assert res.year is None


# ============================================================================
# 4. EXPECTED GRADUATION NORMALIZATION TESTS
# ============================================================================

class TestExpectedGraduationNormalization:
    """Tests for normalize_expected_graduation."""

    @pytest.mark.parametrize("input_val,expected_year", [
        ("2026", 2026),
        ("2027", 2027),
        ("  2028  ", 2028),
    ])
    def test_year_only_expected_graduation(self, input_val, expected_year):
        """Scenario 21: Year-only expected graduation values."""
        res = normalize_expected_graduation(input_val)
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.year == expected_year
        assert res.month is None
        assert res.formatted == str(expected_year)

    @pytest.mark.parametrize("input_val,expected_year,expected_month,expected_formatted", [
        ("December 2026", 2026, 12, "December 2026"),
        ("december 2026", 2026, 12, "December 2026"),
        ("Dec 2026", 2026, 12, "December 2026"),
        ("Dec. 2026", 2026, 12, "December 2026"),
        ("Nov 2026", 2026, 11, "November 2026"),
        ("November 2026", 2026, 11, "November 2026"),
        ("July 2027", 2027, 7, "July 2027"),
        ("2026-12", 2026, 12, "December 2026"),
        ("2027-05", 2027, 5, "May 2027"),
        ("12/2026", 2026, 12, "December 2026"),
        ("5/2027", 2027, 5, "May 2027"),
    ])
    def test_month_and_year_expected_graduation(self, input_val, expected_year, expected_month, expected_formatted):
        """Scenario 22: Month-and-year expected graduation values across various formats."""
        res = normalize_expected_graduation(input_val)
        assert res.status == NormalizationStatus.NORMALIZED
        assert res.year == expected_year
        assert res.month == expected_month
        assert res.formatted == expected_formatted

    @pytest.mark.parametrize("invalid_month_val", [
        "2026-13",
        "2026-00",
        "13/2026",
        "0/2026",
        "Febtober 2026",
        "Smarch 2027",
    ])
    def test_invalid_month(self, invalid_month_val):
        """Scenario 23: Reject impossible months (> 12, 0, or invented month names)."""
        res = normalize_expected_graduation(invalid_month_val)
        assert res.status == NormalizationStatus.INVALID
        assert res.year is None
        assert res.month is None

    @pytest.mark.parametrize("malformed_val", [
        "Tomorrow",
        "Soon",
        "Graduating next year",
        "202",
        "1850-05", # Out of temporal range
        "2099",    # Out of temporal range
    ])
    def test_malformed_date(self, malformed_val):
        """Scenario 24: Reject malformed text, incomplete years, and out-of-range dates."""
        res = normalize_expected_graduation(malformed_val)
        assert res.status == NormalizationStatus.INVALID
        assert res.year is None

    @pytest.mark.parametrize("missing_val", [None, "", "   "])
    def test_missing_expected_graduation(self, missing_val):
        """Scenario 24b: Preserve missing expected graduation as MISSING."""
        res = normalize_expected_graduation(missing_val)
        assert res.status == NormalizationStatus.MISSING
        assert res.year is None
        assert res.month is None


# ============================================================================
# 5. GRADUATION CONSISTENCY VALIDATION TESTS
# ============================================================================

class TestGraduationConsistencyValidation:
    """Tests for validate_graduation_consistency."""

    def test_contradictory_early_year_with_past_graduation(self):
        """Scenario 25a: Continuing student in Year 1 claiming a past completed graduation year."""
        res = validate_graduation_consistency(
            year_of_study=1,
            graduation_year=2023,
            expected_graduation=None,
            current_year=2026
        )
        assert res.status == ConsistencyStatus.NEEDS_VERIFICATION
        assert res.is_consistent is False
        assert any("historical graduation year" in w for w in res.warnings)

    def test_contradictory_graduation_year_and_expected_date(self):
        """Scenario 25b: Discrepancy between historical graduation year and expected graduation date."""
        res = validate_graduation_consistency(
            year_of_study=3,
            graduation_year=2023,
            expected_graduation="December 2027",
            current_year=2026
        )
        assert res.status == ConsistencyStatus.NEEDS_VERIFICATION
        assert res.is_consistent is False
        assert any("conflicts with expected graduation year" in w for w in res.warnings)

    def test_consistent_continuing_student(self):
        """Scenario 25c: Consistent continuing Year 2 student expecting to graduate in 2028."""
        res = validate_graduation_consistency(
            year_of_study=2,
            graduation_year=None,
            expected_graduation="December 2028",
            current_year=2026
        )
        assert res.status == ConsistencyStatus.CONSISTENT
        assert res.is_consistent is True
        assert len(res.warnings) == 0
        assert res.inferred_standing == "CONTINUING_STUDENT"

    def test_consistent_graduated_alumni(self):
        """Scenario 25d: Consistent graduated student with graduation year 2024."""
        res = validate_graduation_consistency(
            year_of_study=None,
            graduation_year=2024,
            expected_graduation=None,
            current_year=2026
        )
        assert res.status == ConsistencyStatus.CONSISTENT
        assert res.is_consistent is True
        assert len(res.warnings) == 0
        assert res.inferred_standing == "GRADUATED_ALUMNI"

    def test_missing_graduation_information(self):
        """Scenario 26: Profile with missing graduation information returns INCOMPLETE without rejecting."""
        res = validate_graduation_consistency(
            year_of_study=2,
            graduation_year=None,
            expected_graduation=None,
            current_year=2026
        )
        assert res.status == ConsistencyStatus.INCOMPLETE
        assert res.is_consistent is True
        assert len(res.warnings) == 1
        assert "Neither graduation year nor expected graduation date" in res.warnings[0]
