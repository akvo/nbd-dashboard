from __future__ import annotations

import pandas as pd

from src.transforms import (
    build_data_quality_summary,
    build_dataset,
    filter_pollution_reporting_records,
    normalize_raw_records,
)


def test_normalize_raw_records_returns_empty_dataframe_for_empty_input():
    result = normalize_raw_records([])

    assert len(result) == 0


def test_normalize_raw_records_returns_dataframe_for_records():
    records = [
        {"champion_id": "c1", "county": "Nairobi", "ward": "Westlands"},
        {"champion_id": "c2", "county": "Nairobi", "ward": "Westlands"},
    ]

    result = normalize_raw_records(records)

    assert len(result) == 2
    assert list(result.columns) == ["champion_id", "county", "ward"]


def test_normalize_raw_records_cleans_text_and_parses_dates():
    records = [
        {
            "champion_id": " c1 ",
            "county": " nairobi ",
            "ward": " westlands ",
            "created_at": "2026-09-01T00:00:00Z",
        }
    ]

    result = normalize_raw_records(records)

    assert result["champion_id"].iloc[0] == "c1"
    assert result["county"].iloc[0] == "Nairobi"
    assert result["ward"].iloc[0] == "Westlands"
    assert pd.api.types.is_datetime64_any_dtype(result["created_at"])


def test_build_data_quality_summary_reports_duplicates_and_missing_values():
    records = [
        {"submission_id": "s1", "county": "Nairobi", "ward": "Westlands", "submitted_at": "2026-09-01T00:00:00Z"},
        {"submission_id": "s1", "county": "Nairobi", "ward": "Westlands", "submitted_at": "2026-09-02T00:00:00Z"},
        {"submission_id": "s2", "county": None, "ward": None, "submitted_at": "invalid-date"},
    ]

    result = build_data_quality_summary(records, key_field="submission_id")

    assert result["record_count"] == 3
    assert result["duplicate_submission_ids"] == 1
    assert result["missing_county"] == 1
    assert result["missing_ward"] == 1
    assert result["invalid_dates"] == 1


def test_build_dataset_returns_normalized_dataframe_and_summary():
    records = [
        {"submission_id": " s1 ", "county": " nairobi ", "ward": " westlands ", "submitted_at": "2026-09-01T00:00:00Z"},
    ]

    dataset, summary = build_dataset(records, key_field="submission_id")

    assert len(dataset) == 1
    assert dataset["submission_id"].iloc[0] == "s1"
    assert dataset["county"].iloc[0] == "Nairobi"
    assert dataset["ward"].iloc[0] == "Westlands"
    assert summary["record_count"] == 1


def test_filter_pollution_reporting_records_keeps_only_approved_pollution_form_records():
    records = [
        {"form_name": "Pollution Reporting Form", "submission_id": "s1", "status": "APPROVED"},
        {"form_name": "Monthly Wetland Sampling", "submission_id": "s2", "status": "APPROVED"},
        {"form_id": 1, "submission_id": "s3", "status": "PENDING"},
        {"form_id": 1, "submission_id": "s4", "status": "APPROVED"},
    ]

    result = filter_pollution_reporting_records(records)

    assert [item["submission_id"] for item in result] == ["s1", "s4"]


def test_filter_pollution_reporting_records_deduplicates_repeated_approved_submissions():
    records = [
        {"form_id": 1, "uuid": "u1", "submission_id": "s1", "status": "APPROVED"},
        {"form_id": 1, "uuid": "u1", "submission_id": "s1", "status": "APPROVED"},
        {"form_id": 1, "uuid": "u2", "submission_id": "s2", "status": "PENDING"},
        {"form_id": 1, "uuid": "u3", "submission_id": "s3", "status": "APPROVED"},
    ]

    result = filter_pollution_reporting_records(records)

    assert len(result) == 2
    assert {item["uuid"] for item in result} == {"u1", "u3"}


def test_filter_pollution_reporting_records_excludes_the_other_live_forms():
    """The live API returns three forms, each carrying both form fields."""
    records = [
        {"form_name": "Pollution Reporting Form", "form_id": 1, "uuid": "u1", "status": "APPROVED"},
        {"form_name": "Monthly Wetland Sampling", "form_id": 2, "uuid": "u2", "status": "APPROVED"},
        {"form_name": "Lab QA Report", "form_id": 4, "uuid": "u3", "status": "APPROVED"},
    ]

    result = filter_pollution_reporting_records(records)

    assert [item["uuid"] for item in result] == ["u1"]
    assert {item["form_id"] for item in result} == {1}
