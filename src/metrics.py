from __future__ import annotations

from typing import Any

import pandas as pd


UNKNOWN_INCIDENT_TYPE = "Unknown"


def normalize_incident_type_names(values: pd.Series) -> pd.Series:
    """Return incident names with blank and missing values folded to "Unknown".

    Both the chart and the drill-down table normalize through here so that a bar's
    count and the rows behind it can never disagree.
    """
    return values.fillna(UNKNOWN_INCIDENT_TYPE).map(
        lambda value: str(value).strip() or UNKNOWN_INCIDENT_TYPE
    )


def _resolve_timestamp_column(df: pd.DataFrame) -> str | None:
    for column in ("submitted_at", "created_at"):
        if column in df.columns:
            return column
    return None


def total_champions(champions: list[dict[str, Any]] | pd.DataFrame) -> int:
    """Return the number of unique champions in a dataframe-like input."""
    df = champions if isinstance(champions, pd.DataFrame) else pd.DataFrame(champions)
    if df.empty or "champion_id" not in df.columns:
        return 0
    return int(df["champion_id"].dropna().nunique())


def champions_per_ward(champions: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    """Return champions aggregated per county and ward."""
    df = champions if isinstance(champions, pd.DataFrame) else pd.DataFrame(champions)
    if df.empty or "champion_id" not in df.columns:
        return pd.DataFrame(columns=["county", "ward", "champions"])

    result = (
        df.groupby(["county", "ward"], dropna=False)["champion_id"]
        .nunique()
        .reset_index(name="champions")
        .sort_values("champions", ascending=False)
    )
    result["ward"] = result["ward"].fillna("Unknown")
    return result


def cumulative_submissions(submissions: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    """Return cumulative submissions over valid submission timestamps."""
    df = submissions if isinstance(submissions, pd.DataFrame) else pd.DataFrame(submissions)
    if df.empty:
        return pd.DataFrame(columns=["submitted_at", "submissions", "cumulative_submissions"])

    timestamp_column = _resolve_timestamp_column(df)
    if timestamp_column is None:
        return pd.DataFrame(columns=["submitted_at", "submissions", "cumulative_submissions"])

    valid_df = df.dropna(subset=[timestamp_column]).copy()
    if valid_df.empty:
        return pd.DataFrame(columns=["submitted_at", "submissions", "cumulative_submissions"])

    valid_df["submitted_at"] = pd.to_datetime(valid_df[timestamp_column], errors="coerce")
    valid_df = valid_df.dropna(subset=["submitted_at"])

    if valid_df.empty:
        return pd.DataFrame(columns=["submitted_at", "submissions", "cumulative_submissions"])

    weekly = (
        valid_df.groupby("submitted_at", dropna=False)
        .size()
        .reset_index(name="submissions")
    )
    weekly["cumulative_submissions"] = weekly["submissions"].cumsum()
    return weekly


def daily_submissions(submissions: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    """Return one row per calendar day, from the earliest submission onwards.

    Days on which nobody reported are carried as zero rather than dropped: a
    line drawn straight from one busy day to the next would otherwise read as
    steady reporting across a silent stretch.
    """
    empty = pd.DataFrame(columns=["date", "submissions"])

    df = submissions if isinstance(submissions, pd.DataFrame) else pd.DataFrame(submissions)
    if df.empty:
        return empty

    timestamp_column = _resolve_timestamp_column(df)
    if timestamp_column is None:
        return empty

    # Timestamps arrive with mixed offsets, so they are read as UTC before the
    # day is taken; otherwise two rows an hour apart can land on separate days.
    parsed_dates = pd.to_datetime(df[timestamp_column], errors="coerce", utc=True)
    days = parsed_dates.dropna().dt.tz_convert(None).dt.normalize()

    if days.empty:
        return empty

    counts = days.value_counts().sort_index()
    every_day = pd.date_range(counts.index.min(), counts.index.max(), freq="D")

    return pd.DataFrame(
        {
            "date": every_day,
            "submissions": counts.reindex(every_day, fill_value=0).to_numpy(dtype=int),
        }
    )


def weekly_submissions(submissions: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    """Return weekly submissions grouped by ISO week."""
    df = submissions if isinstance(submissions, pd.DataFrame) else pd.DataFrame(submissions)
    if df.empty:
        return pd.DataFrame(columns=["week", "submissions"])

    timestamp_column = _resolve_timestamp_column(df)
    if timestamp_column is None:
        return pd.DataFrame(columns=["week", "submissions"])

    df = df.copy()
    parsed_dates = pd.to_datetime(df[timestamp_column], errors="coerce")

    if getattr(parsed_dates.dt, "tz", None) is not None:
        parsed_dates = parsed_dates.dt.tz_localize(None)

    df["week"] = parsed_dates.dt.to_period("W").dt.start_time
    df = df.dropna(subset=["week"])

    if df.empty:
        return pd.DataFrame(columns=["week", "submissions"])

    weekly = df.groupby("week", dropna=False).size().reset_index(name="submissions")
    return weekly


def _channel_from_submitter(submitter: str | None) -> str:
    if not submitter:
        return "unknown"

    submitter_str = str(submitter)
    if submitter_str.startswith("wa-"):
        return "whatsapp"
    if submitter_str.startswith("ussd-"):
        return "ussd"
    return "unknown"


def weekly_submissions_by_channel(submissions: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    """Return weekly submissions broken down by submission channel."""
    df = submissions if isinstance(submissions, pd.DataFrame) else pd.DataFrame(submissions)
    if df.empty:
        return pd.DataFrame(columns=["week", "channel", "submissions"])

    timestamp_column = _resolve_timestamp_column(df)
    if timestamp_column is None:
        return pd.DataFrame(columns=["week", "channel", "submissions"])

    working_df = df.copy()
    working_df["channel"] = working_df["submitter"].map(_channel_from_submitter)

    parsed_dates = pd.to_datetime(working_df[timestamp_column], errors="coerce")
    if getattr(parsed_dates.dt, "tz", None) is not None:
        parsed_dates = parsed_dates.dt.tz_localize(None)

    working_df["week"] = parsed_dates.dt.to_period("W").dt.start_time
    working_df = working_df.dropna(subset=["week"])

    if working_df.empty:
        return pd.DataFrame(columns=["week", "channel", "submissions"])

    result = (
        working_df.groupby(["week", "channel"], dropna=False)
        .size()
        .reset_index(name="submissions")
        .sort_values(["week", "channel"])
    )
    return result


def submissions_by_ward(submissions: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    """Return submission counts grouped by reported ward/location."""
    df = submissions if isinstance(submissions, pd.DataFrame) else pd.DataFrame(submissions)
    if df.empty:
        return pd.DataFrame(columns=["ward", "submissions"])

    working_df = df.copy()
    if "reported_location" in working_df.columns:
        working_df["ward"] = working_df["reported_location"]
    else:
        working_df["ward"] = "Unknown"

    result = (
        working_df.groupby("ward", dropna=False)
        .size()
        .reset_index(name="submissions")
        .sort_values("submissions", ascending=False)
    )

    result["ward"] = result["ward"].fillna("Unknown")
    return result


def submissions_by_incident_type(submissions: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    """Return submission counts grouped by reported incident type."""
    df = submissions if isinstance(submissions, pd.DataFrame) else pd.DataFrame(submissions)
    if df.empty:
        return pd.DataFrame(columns=["incident_type", "submissions"])

    working_df = df.copy()
    if "incident_type_name" in working_df.columns:
        working_df["incident_type"] = working_df["incident_type_name"]
    else:
        working_df["incident_type"] = None

    working_df["incident_type"] = normalize_incident_type_names(working_df["incident_type"])

    return (
        working_df.groupby("incident_type", dropna=False)
        .size()
        .reset_index(name="submissions")
        .sort_values("submissions", ascending=False)
        .reset_index(drop=True)
    )


APPROVED_STATUS = "APPROVED"
UNKNOWN_WARD = "Unknown"


def _approved_submissions(df: pd.DataFrame) -> pd.DataFrame:
    """Return only the approved rows, with a real submitter attached.

    A champion is measured on approved reports only, so anything still pending
    or rejected must not count towards the tally.
    """
    if "submitter" not in df.columns:
        return df.iloc[0:0]

    approved = df.copy()

    if "status" in approved.columns:
        statuses = approved["status"].fillna("").astype(str).str.strip().str.upper()
        approved = approved[statuses == APPROVED_STATUS]

    submitters = approved["submitter"].fillna("").astype(str).str.strip()
    return approved[submitters != ""]


def _ward_labels(df: pd.DataFrame) -> pd.Series:
    """Return the ward each submission belongs to, however it is recorded."""
    labels = pd.Series([None] * len(df), index=df.index, dtype="object")

    for column in ("ward", "reported_location"):
        if column in df.columns:
            labels = labels.combine_first(df[column])

    return labels.fillna(UNKNOWN_WARD).astype(str).str.strip().replace("", UNKNOWN_WARD)


def ward_champions(submissions: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    """Return each ward's champion: the person with the most approved reports.

    Ties are broken on the submitter name so that the same data always names the
    same champion.
    """
    empty = pd.DataFrame(columns=["ward", "champion", "reports"])

    df = submissions if isinstance(submissions, pd.DataFrame) else pd.DataFrame(submissions)
    if df.empty:
        return empty

    approved = _approved_submissions(df)
    if approved.empty:
        return empty

    tally = approved.assign(
        ward=_ward_labels(approved),
        champion=approved["submitter"].astype(str).str.strip(),
    )

    counts = (
        tally.groupby(["ward", "champion"], dropna=False)
        .size()
        .reset_index(name="reports")
        .sort_values(["reports", "champion"], ascending=[False, True])
    )

    return (
        counts.drop_duplicates(subset="ward", keep="first")
        .sort_values(["reports", "ward"], ascending=[False, True])
        .reset_index(drop=True)
    )


def champion_submissions(
    submissions: list[dict[str, Any]] | pd.DataFrame,
    ward: str | None,
    champion: str | None,
) -> pd.DataFrame:
    """Return the approved reports behind one ward champion.

    The champions chart counts approved reports per ward, so the drill-down
    resolves the ward and the submitter through the same helpers the tally uses.
    That keeps the rows shown here in step with the number the clicked bar
    reported.
    """
    df = submissions if isinstance(submissions, pd.DataFrame) else pd.DataFrame(submissions)
    if df.empty or not ward or not champion:
        return df.iloc[0:0]

    approved = _approved_submissions(df)
    if approved.empty:
        return approved

    labelled = approved.assign(ward=_ward_labels(approved))
    submitters = labelled["submitter"].astype(str).str.strip()

    return labelled[
        (labelled["ward"] == str(ward).strip()) & (submitters == str(champion).strip())
    ].copy()


def distinct_submitters(submissions: list[dict[str, Any]] | pd.DataFrame) -> int:
    """Return how many distinct people have an approved report in the data.

    This counts everyone who reported, which is a wider group than the ward
    champions: a champion is the single top submitter within one ward.
    """
    df = submissions if isinstance(submissions, pd.DataFrame) else pd.DataFrame(submissions)
    if df.empty:
        return 0

    approved = _approved_submissions(df)
    if approved.empty:
        return 0

    return int(approved["submitter"].astype(str).str.strip().nunique())
