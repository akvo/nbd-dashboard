from __future__ import annotations

from typing import Any

import pandas as pd


def _clean_text(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, str):
        stripped = value.strip()
        return stripped

    return value


def filter_pollution_reporting_records(records: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Return only unique approved pollution reporting form records."""
    if not records:
        return []

    latest_by_uuid: dict[str, dict[str, Any]] = {}

    for record in records:
        if not isinstance(record, dict):
            continue

        form_name = record.get("form_name")
        form_id = record.get("form_id")
        if form_name != "Pollution Reporting Form" and form_id != 1:
            continue

        if str(record.get("status", "")).upper() != "APPROVED":
            continue

        uuid = record.get("uuid")
        if uuid:
            existing = latest_by_uuid.get(uuid)
            if existing is None or (record.get("published_version_id") or 0) > (existing.get("published_version_id") or 0):
                latest_by_uuid[uuid] = record
            continue

        latest_by_uuid.setdefault(record.get("id", id(record)), record)

    return list(latest_by_uuid.values())


def normalize_raw_records(records: list[dict[str, Any]] | None) -> pd.DataFrame:
    """Return a normalized DataFrame from raw API records.

    This Phase 1 implementation trims string values, normalizes geography text,
    and parses known timestamp fields into pandas datetime columns.
    """
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    if df.empty:
        return df

    for column in df.columns:
        df[column] = df[column].map(_clean_text)

    for column in ["county", "ward", "champion_name", "county_id", "ward_id"]:
        if column in df.columns:
            df[column] = df[column].map(lambda value: value.title() if isinstance(value, str) else value)

    for column in ["created_at", "submitted_at", "registration_date"]:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce")

    return df


def build_data_quality_summary(records: list[dict[str, Any]] | None, key_field: str) -> dict[str, int]:
    """Build a data-quality summary for submissions or champions.

    This Phase 2 helper quantifies duplicate keys, missing geography fields, and
    invalid dates so the dashboard can display clear quality warnings.
    """
    if not records:
        return {
            "record_count": 0,
            "duplicate_submission_ids": 0,
            "missing_county": 0,
            "missing_ward": 0,
            "invalid_dates": 0,
        }

    df = normalize_raw_records(records)

    duplicate_count = int(df[key_field].duplicated().sum()) if key_field in df.columns else 0
    missing_county = int(df["county"].isna().sum()) if "county" in df.columns else 0
    missing_ward = int(df["ward"].isna().sum()) if "ward" in df.columns else 0

    invalid_dates = 0
    if "submitted_at" in df.columns:
        invalid_dates = int(df["submitted_at"].isna().sum())
    elif "created_at" in df.columns:
        invalid_dates = int(df["created_at"].isna().sum())

    return {
        "record_count": int(len(df)),
        "duplicate_submission_ids": duplicate_count,
        "missing_county": missing_county,
        "missing_ward": missing_ward,
        "invalid_dates": invalid_dates,
    }


def build_dataset(records: list[dict[str, Any]] | None, key_field: str) -> tuple[pd.DataFrame, dict[str, int]]:
    """Build the normalized dataset and a matching quality summary.

    This reusable Phase 2 workflow gives the dashboard one function to transform
    raw API records into the dataframe and quality metadata it needs.
    """
    dataset = normalize_raw_records(records)
    summary = build_data_quality_summary(records, key_field)
    return dataset, summary
