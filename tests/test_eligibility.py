"""Tests for the deterministic eligibility checks (age range and sex)."""

from __future__ import annotations

import pytest

from clinical_trials_mcp.eligibility import (
    evaluate_eligibility,
    normalize_sex,
    parse_age_to_years,
)
from tests.conftest import load_fixture


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("18 Years", 18.0),
        ("6 Months", 0.5),
        ("2 Weeks", pytest.approx(2 / 52)),
        ("90 Days", pytest.approx(90 / 365)),
        ("1 Year", 1.0),
        ("N/A", None),
        ("", None),
        (None, None),
        ("unknown", None),
    ],
)
def test_parse_age_to_years(raw: str | None, expected: float | None) -> None:
    assert parse_age_to_years(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("female", "female"),
        ("F", "female"),
        ("Male", "male"),
        ("m", "male"),
        ("ALL", None),
        (None, None),
        ("", None),
    ],
)
def test_normalize_sex(raw: str | None, expected: str | None) -> None:
    assert normalize_sex(raw) == expected


def check(result, criterion: str):
    return next(c for c in result.checks if c.criterion == criterion)


def test_adult_within_range_meets() -> None:
    study = load_fixture("study_recruiting.json")  # 18 to 75, ALL
    result = evaluate_eligibility(study, patient_age=45, patient_sex="female")
    assert result.verdict == "meets"
    assert check(result, "age").result == "pass"
    assert check(result, "sex").result == "pass"
    assert result.criteria_text is not None and "Inclusion Criteria" in result.criteria_text
    assert "not a final eligibility decision" in result.note


def test_age_below_minimum_does_not_meet() -> None:
    study = load_fixture("study_recruiting.json")
    result = evaluate_eligibility(study, patient_age=16, patient_sex=None)
    assert result.verdict == "does_not_meet"
    age_check = check(result, "age")
    assert age_check.result == "fail"
    assert "below the study minimum" in age_check.detail


def test_age_above_maximum_does_not_meet() -> None:
    study = load_fixture("study_recruiting.json")
    result = evaluate_eligibility(study, patient_age=80, patient_sex="male")
    assert result.verdict == "does_not_meet"
    assert "above the study maximum" in check(result, "age").detail


def test_age_at_bounds_passes() -> None:
    study = load_fixture("study_recruiting.json")
    assert evaluate_eligibility(study, patient_age=18, patient_sex=None).verdict != "does_not_meet"
    assert evaluate_eligibility(study, patient_age=75, patient_sex=None).verdict != "does_not_meet"


def test_sex_mismatch_does_not_meet() -> None:
    study = load_fixture("study_female_only.json")  # FEMALE, 18 to 45
    result = evaluate_eligibility(study, patient_age=30, patient_sex="male")
    assert result.verdict == "does_not_meet"
    sex_check = check(result, "sex")
    assert sex_check.result == "fail"
    assert "female" in sex_check.detail


def test_sex_match_female_only_meets() -> None:
    study = load_fixture("study_female_only.json")
    result = evaluate_eligibility(study, patient_age=30, patient_sex="female")
    assert result.verdict == "meets"


def test_missing_patient_sex_cannot_determine() -> None:
    study = load_fixture("study_female_only.json")
    result = evaluate_eligibility(study, patient_age=30, patient_sex=None)
    assert result.verdict == "cannot_determine"
    assert check(result, "sex").result == "unknown"


def test_missing_patient_age_cannot_determine() -> None:
    study = load_fixture("study_recruiting.json")
    result = evaluate_eligibility(study, patient_age=None, patient_sex="male")
    assert result.verdict == "cannot_determine"
    assert check(result, "age").result == "unknown"


def test_child_study_months_minimum() -> None:
    study = load_fixture("study_child.json")  # 6 Months to 12 Years
    assert evaluate_eligibility(study, patient_age=0.25, patient_sex=None).verdict == (
        "does_not_meet"
    )
    assert evaluate_eligibility(study, patient_age=5, patient_sex=None).verdict == "meets"
    assert evaluate_eligibility(study, patient_age=13, patient_sex=None).verdict == (
        "does_not_meet"
    )


def test_study_without_age_bounds_passes_age() -> None:
    study = load_fixture("study_open_age.json")  # no stated bounds
    result = evaluate_eligibility(study, patient_age=97, patient_sex="female")
    assert check(result, "age").result == "pass"
    assert result.verdict == "meets"


def test_fail_wins_over_unknown() -> None:
    study = load_fixture("study_female_only.json")
    result = evaluate_eligibility(study, patient_age=10, patient_sex=None)
    assert result.verdict == "does_not_meet"
