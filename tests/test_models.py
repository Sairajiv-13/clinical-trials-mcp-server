"""Tests for parsing raw API study dicts into tool output models."""

from __future__ import annotations

from typing import Any

from clinical_trials_mcp.models import parse_detail, parse_summary
from tests.conftest import load_fixture


def test_parse_summary_recruiting_study() -> None:
    summary = parse_summary(load_fixture("study_recruiting.json"))
    assert summary.nct_id == "NCT06001122"
    assert summary.title == "Metformin XR in Adults With Type 2 Diabetes"
    assert summary.status == "RECRUITING"
    assert summary.phases == ["PHASE2"]
    assert summary.conditions == ["Type 2 Diabetes Mellitus"]
    assert summary.interventions == ["Metformin XR 1500 mg", "Placebo"]
    assert summary.lead_sponsor == "University Medical Center"
    assert summary.start_date == "2025-03-01"
    assert summary.last_update_posted == "2026-01-15"


def test_parse_detail_recruiting_study() -> None:
    detail = parse_detail(load_fixture("study_recruiting.json"))
    assert detail.nct_id == "NCT06001122"
    assert detail.official_title is not None and "Phase 2" in detail.official_title
    assert detail.status == "RECRUITING"
    assert [i.name for i in detail.interventions] == ["Metformin XR 1500 mg", "Placebo"]
    assert detail.interventions[0].type == "DRUG"
    assert detail.eligibility.sex == "ALL"
    assert detail.eligibility.minimum_age == "18 Years"
    assert detail.eligibility.maximum_age == "75 Years"
    assert detail.eligibility.healthy_volunteers is False
    assert detail.eligibility.criteria_text is not None
    assert "HbA1c between 7.0% and 10.5%" in detail.eligibility.criteria_text
    assert detail.locations_count == 4
    # Two sites carry RECRUITING, one has no status and inherits the study's
    # RECRUITING status, one is NOT_YET_RECRUITING.
    assert detail.recruiting_locations_count == 3
    assert detail.lead_sponsor == "University Medical Center"
    assert detail.collaborators == [
        "National Institute of Diabetes and Digestive and Kidney Diseases (NIDDK)"
    ]
    assert detail.enrollment_count == 240
    assert detail.start_date == "2025-03-01"
    assert detail.primary_completion_date == "2027-06-30"
    assert detail.completion_date == "2027-12-31"


def test_parse_detail_site_without_own_status_inherits_study_status() -> None:
    detail = parse_detail(load_fixture("study_female_only.json"))
    assert detail.status == "ACTIVE_NOT_RECRUITING"
    assert detail.locations_count == 1
    assert detail.recruiting_locations_count == 0
    assert detail.phases == ["PHASE3"]


def test_parse_detail_observational_study_without_phases() -> None:
    detail = parse_detail(load_fixture("study_open_age.json"))
    assert detail.phases == []
    assert detail.conditions == ["Hypertension"]
    assert detail.locations_count == 0
    assert detail.eligibility.minimum_age is None
    assert detail.eligibility.maximum_age is None


def test_parse_summary_handles_empty_study() -> None:
    summary = parse_summary({})
    assert summary.nct_id == ""
    assert summary.status == "UNKNOWN"
    assert summary.phases == []
    assert summary.interventions == []


def test_parse_detail_handles_partial_study(any_study: dict[str, Any]) -> None:
    detail = parse_detail(any_study)
    assert detail.nct_id.startswith("NCT")
    assert detail.brief_title
