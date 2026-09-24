from __future__ import annotations

import pandas as pd

from src.charts import (
    INCIDENT_TYPE_COLOURS,
    OTHER_INCIDENT_TYPE,
    build_submissions_by_incident_type_chart,
    build_submissions_by_ward_chart,
    build_weekly_submissions_by_channel_chart,
    build_weekly_submissions_chart,
    incident_types_for_label,
)
from src.metrics import (
    champions_per_ward,
    cumulative_submissions,
    normalize_incident_type_names,
    submissions_by_incident_type,
    submissions_by_ward,
    total_champions,
    weekly_submissions,
    weekly_submissions_by_channel,
)


def test_total_champions_counts_unique_champion_ids():
    champions = [
        {"champion_id": "c1", "county": "Nairobi", "ward": "Westlands"},
        {"champion_id": "c2", "county": "Nairobi", "ward": "Westlands"},
        {"champion_id": "c1", "county": "Nairobi", "ward": "Westlands"},
    ]

    result = total_champions(champions)

    assert result == 2


def test_champions_per_ward_returns_sorted_counts():
    champions = [
        {"champion_id": "c1", "county": "Nairobi", "ward": "Westlands"},
        {"champion_id": "c2", "county": "Nairobi", "ward": "Westlands"},
        {"champion_id": "c3", "county": "Nairobi", "ward": "Kilimani"},
    ]

    result = champions_per_ward(champions)

    assert result["champions"].tolist() == [2, 1]


def test_cumulative_submissions_includes_running_total():
    submissions = [
        {"submitted_at": "2026-09-01T00:00:00Z", "submission_id": 1},
        {"submitted_at": "2026-09-02T00:00:00Z", "submission_id": 2},
    ]

    result = cumulative_submissions(submissions)

    assert result["cumulative_submissions"].tolist() == [1, 2]


def test_weekly_submissions_groups_by_iso_week():
    submissions = [
        {"submitted_at": "2026-09-01T00:00:00Z", "submission_id": 1},
        {"submitted_at": "2026-09-02T00:00:00Z", "submission_id": 2},
    ]

    result = weekly_submissions(submissions)

    assert result["submissions"].sum() == 2


def test_weekly_submissions_supports_created_at_column_for_public_data():
    submissions = [
        {"created_at": "2026-09-01T00:00:00Z", "submission_id": 1},
        {"created_at": "2026-09-02T00:00:00Z", "submission_id": 2},
    ]

    result = weekly_submissions(submissions)

    assert not result.empty
    assert result["submissions"].sum() == 2


def test_weekly_submissions_by_channel_groups_by_week_and_channel():
    submissions = [
        {"created_at": "2026-09-01T00:00:00Z", "submitter": "ussd-+254111111111"},
        {"created_at": "2026-09-01T00:00:00Z", "submitter": "wa-+254222222222"},
        {"created_at": "2026-09-08T00:00:00Z", "submitter": "ussd-+254111111111"},
    ]

    result = weekly_submissions_by_channel(submissions)

    assert result["submissions"].sum() == 3
    assert set(result["channel"]) == {"ussd", "whatsapp"}


def test_submissions_by_ward_returns_counts_by_reported_location():
    submissions = [
        {"reported_location": "Kilgoris", "submission_id": 1},
        {"reported_location": "Kilgoris", "submission_id": 2},
        {"reported_location": "Bunyala North", "submission_id": 3},
    ]

    result = submissions_by_ward(submissions)

    assert result["submissions"].tolist() == [2, 1]
    assert result["ward"].tolist() == ["Kilgoris", "Bunyala North"]


def test_weekly_channel_chart_exposes_selection_metadata():
    submissions = [
        {"created_at": "2026-09-01T00:00:00Z", "submitter": "ussd-+254111111111"},
        {"created_at": "2026-09-01T00:00:00Z", "submitter": "wa-+254222222222"},
        {"created_at": "2026-09-08T00:00:00Z", "submitter": "ussd-+254111111111"},
    ]

    fig = build_weekly_submissions_by_channel_chart(weekly_submissions_by_channel(submissions))

    assert len(fig.data) == 2
    assert all(trace.customdata is not None for trace in fig.data)


def test_weekly_submissions_chart_exposes_selection_metadata():
    submissions = [
        {"submitted_at": "2026-09-01T00:00:00Z", "submission_id": 1},
        {"submitted_at": "2026-09-02T00:00:00Z", "submission_id": 2},
    ]

    fig = build_weekly_submissions_chart(weekly_submissions(submissions))

    assert len(fig.data) == 1
    assert fig.data[0].customdata is not None


def test_ward_chart_exposes_selection_metadata():
    submissions = [
        {"reported_location": "Kilgoris", "submission_id": 1},
        {"reported_location": "Kilgoris", "submission_id": 2},
        {"reported_location": "Bunyala North", "submission_id": 3},
    ]

    fig = build_submissions_by_ward_chart(submissions_by_ward(submissions))

    assert len(fig.data) == 1
    assert fig.data[0].customdata is not None


def test_submissions_by_incident_type_returns_sorted_counts():
    submissions = [
        {"incident_type_name": "Low water level", "submission_id": 1},
        {"incident_type_name": "Water colour (darker/murkier)", "submission_id": 2},
        {"incident_type_name": "Water colour (darker/murkier)", "submission_id": 3},
    ]

    result = submissions_by_incident_type(submissions)

    assert result["incident_type"].tolist() == ["Water colour (darker/murkier)", "Low water level"]
    assert result["submissions"].tolist() == [2, 1]


def test_submissions_by_incident_type_labels_missing_values_as_unknown():
    submissions = [
        {"incident_type_name": None, "submission_id": 1},
        {"submission_id": 2},
    ]

    result = submissions_by_incident_type(submissions)

    assert result["incident_type"].tolist() == ["Unknown"]
    assert result["submissions"].tolist() == [2]


def test_submissions_by_incident_type_handles_empty_input():
    result = submissions_by_incident_type([])

    assert result.empty
    assert list(result.columns) == ["incident_type", "submissions"]


def test_incident_type_chart_exposes_selection_metadata():
    submissions = [
        {"incident_type_name": "Low water level", "submission_id": 1},
        {"incident_type_name": "Storm event", "submission_id": 2},
    ]

    fig = build_submissions_by_incident_type_chart(submissions_by_incident_type(submissions))

    assert len(fig.data) == 2
    assert all(trace.customdata is not None for trace in fig.data)


def test_incident_type_chart_colours_each_incident_distinctly():
    submissions = [
        {"incident_type_name": name, "submission_id": index}
        for index, name in enumerate(["Low water level", "Storm event", "No water"])
    ]

    fig = build_submissions_by_incident_type_chart(submissions_by_incident_type(submissions))

    colours = [trace.marker.color for trace in fig.data]
    assert len(set(colours)) == len(colours)


def test_incident_type_chart_keeps_colours_stable_when_filtered():
    all_types = ["Low water level", "No water", "Storm event"]
    full = submissions_by_incident_type(
        [{"incident_type_name": name, "submission_id": index} for index, name in enumerate(all_types)]
    )
    filtered = submissions_by_incident_type([{"incident_type_name": "Storm event", "submission_id": 1}])

    full_colours = {
        trace.name: trace.marker.color
        for trace in build_submissions_by_incident_type_chart(full, all_types).data
    }
    filtered_colours = {
        trace.name: trace.marker.color
        for trace in build_submissions_by_incident_type_chart(filtered, all_types).data
    }

    assert filtered_colours["Storm event"] == full_colours["Storm event"]


def test_incident_type_chart_folds_incidents_beyond_the_palette():
    all_types = [f"Incident {index}" for index in range(len(INCIDENT_TYPE_COLOURS["light"]) + 3)]
    counts = submissions_by_incident_type(
        [{"incident_type_name": name, "submission_id": index} for index, name in enumerate(all_types)]
    )

    fig = build_submissions_by_incident_type_chart(counts, all_types)

    trace_names = [trace.name for trace in fig.data]
    assert len(trace_names) == len(INCIDENT_TYPE_COLOURS["light"]) + 1
    assert OTHER_INCIDENT_TYPE in trace_names


def test_incident_type_chart_handles_empty_input():
    fig = build_submissions_by_incident_type_chart(submissions_by_incident_type([]))

    assert fig is not None


def test_incident_type_chart_uses_dark_palette_on_dark_theme():
    counts = submissions_by_incident_type(
        [{"incident_type_name": name, "submission_id": index} for index, name in enumerate(["Storm event", "No water"])]
    )

    light = build_submissions_by_incident_type_chart(counts, theme="light")
    dark = build_submissions_by_incident_type_chart(counts, theme="dark")

    light_colours = {trace.name: trace.marker.color for trace in light.data}
    dark_colours = {trace.name: trace.marker.color for trace in dark.data}

    assert light_colours != dark_colours
    assert set(dark_colours.values()) <= set(INCIDENT_TYPE_COLOURS["dark"])


def test_incident_type_chart_falls_back_to_light_palette_for_unknown_theme():
    counts = submissions_by_incident_type([{"incident_type_name": "Storm event", "submission_id": 1}])

    fig = build_submissions_by_incident_type_chart(counts, theme=None)

    assert fig.data[0].marker.color in INCIDENT_TYPE_COLOURS["light"]


def test_submissions_by_incident_type_handles_a_missing_incident_column():
    submissions = [{"submission_id": 1}, {"submission_id": 2}]

    result = submissions_by_incident_type(submissions)

    assert result["incident_type"].tolist() == ["Unknown"]
    assert result["submissions"].tolist() == [2]


def test_submissions_by_incident_type_treats_blank_names_as_unknown():
    submissions = [
        {"incident_type_name": "   ", "submission_id": 1},
        {"incident_type_name": "Storm event", "submission_id": 2},
    ]

    result = submissions_by_incident_type(submissions)

    assert set(result["incident_type"]) == {"Unknown", "Storm event"}


def test_normalize_incident_type_names_folds_blanks_and_missing_to_unknown():
    values = pd.Series(["Storm event", "  Storm event  ", "   ", None, float("nan")])

    result = normalize_incident_type_names(values)

    assert result.tolist() == ["Storm event", "Storm event", "Unknown", "Unknown", "Unknown"]


def test_incident_types_for_label_returns_the_clicked_incident():
    all_types = ["Low water level", "Storm event"]

    assert incident_types_for_label("Storm event", all_types) == {"Storm event"}


def test_incident_types_for_label_expands_other_to_the_folded_incidents():
    palette_size = len(INCIDENT_TYPE_COLOURS["light"])
    all_types = [f"Incident {index:02d}" for index in range(palette_size + 3)]

    folded = incident_types_for_label(OTHER_INCIDENT_TYPE, all_types)

    assert folded == set(sorted(all_types)[palette_size:])
    assert len(folded) == 3


def test_incident_types_for_label_prefers_a_real_incident_named_other():
    all_types = [OTHER_INCIDENT_TYPE, "Storm event"]

    assert incident_types_for_label(OTHER_INCIDENT_TYPE, all_types) == {OTHER_INCIDENT_TYPE}
