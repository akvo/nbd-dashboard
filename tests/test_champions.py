from __future__ import annotations

import pandas as pd

from src.charts import build_ward_champions_chart
from src.metrics import champion_submissions, distinct_submitters, ward_champions
from src.transforms import filter_pollution_reporting_records


def _submission(submitter: str, ward: str, status: str = "APPROVED") -> dict[str, str]:
    return {"submitter": submitter, "ward": ward, "status": status}


def test_ward_champions_picks_the_top_submitter_in_each_ward():
    submissions = [
        _submission("wa-1", "Kimintet"),
        _submission("wa-1", "Kimintet"),
        _submission("wa-2", "Kimintet"),
        _submission("ussd-9", "Chebunyo"),
    ]

    result = ward_champions(submissions)

    assert result["ward"].tolist() == ["Kimintet", "Chebunyo"]
    assert result["champion"].tolist() == ["wa-1", "ussd-9"]
    assert result["reports"].tolist() == [2, 1]


def test_ward_champions_returns_one_row_per_ward():
    submissions = [_submission(f"wa-{index}", "Kimintet") for index in range(5)]

    result = ward_champions(submissions)

    assert len(result) == 1


def test_ward_champions_counts_only_approved_submissions():
    submissions = [
        _submission("wa-1", "Kimintet", status="PENDING"),
        _submission("wa-1", "Kimintet", status="REJECTED"),
        _submission("wa-2", "Kimintet"),
    ]

    result = ward_champions(submissions)

    assert result["champion"].tolist() == ["wa-2"]
    assert result["reports"].tolist() == [1]


def test_ward_champions_treats_status_case_insensitively():
    submissions = [_submission("wa-1", "Kimintet", status="approved")]

    result = ward_champions(submissions)

    assert result["reports"].tolist() == [1]


def test_ward_champions_ignores_rows_without_a_submitter():
    submissions = [
        {"submitter": None, "ward": "Kimintet", "status": "APPROVED"},
        {"submitter": "   ", "ward": "Kimintet", "status": "APPROVED"},
        _submission("wa-1", "Kimintet"),
    ]

    result = ward_champions(submissions)

    assert result["champion"].tolist() == ["wa-1"]
    assert result["reports"].tolist() == [1]


def test_ward_champions_breaks_ties_deterministically():
    submissions = [_submission("wa-b", "Kimintet"), _submission("wa-a", "Kimintet")]

    first = ward_champions(submissions)
    second = ward_champions(list(reversed(submissions)))

    assert first["champion"].tolist() == second["champion"].tolist() == ["wa-a"]


def test_ward_champions_falls_back_to_the_reported_location():
    submissions = [
        {"submitter": "wa-1", "ward": None, "reported_location": "Kilgoris", "status": "APPROVED"},
    ]

    result = ward_champions(submissions)

    assert result["ward"].tolist() == ["Kilgoris"]


def test_ward_champions_labels_placeless_rows_as_unknown():
    submissions = [{"submitter": "wa-1", "status": "APPROVED"}]

    result = ward_champions(submissions)

    assert result["ward"].tolist() == ["Unknown"]


def test_ward_champions_counts_every_row_when_no_status_column_exists():
    submissions = [{"submitter": "wa-1", "ward": "Kimintet"}]

    result = ward_champions(submissions)

    assert result["reports"].tolist() == [1]


def test_ward_champions_handles_empty_input():
    result = ward_champions([])

    assert result.empty
    assert list(result.columns) == ["ward", "champion", "reports"]


def test_ward_champions_does_not_mutate_the_caller_frame():
    frame = pd.DataFrame([_submission("wa-1", "Kimintet")])
    before = frame.copy()

    ward_champions(frame)

    pd.testing.assert_frame_equal(frame, before)


def test_distinct_submitters_counts_unique_approved_submitters():
    submissions = [
        _submission("wa-1", "Kimintet"),
        _submission("wa-1", "Chebunyo"),
        _submission("wa-2", "Kimintet"),
        _submission("wa-3", "Kimintet", status="PENDING"),
    ]

    assert distinct_submitters(submissions) == 2


def test_distinct_submitters_ignores_blank_submitters():
    submissions = [
        {"submitter": "   ", "ward": "Kimintet", "status": "APPROVED"},
        {"submitter": None, "ward": "Kimintet", "status": "APPROVED"},
    ]

    assert distinct_submitters(submissions) == 0


def test_distinct_submitters_handles_empty_input():
    assert distinct_submitters([]) == 0


def test_ward_champions_chart_labels_each_bar_with_its_champion():
    submissions = [_submission("wa-1", "Kimintet"), _submission("ussd-9", "Chebunyo")]

    fig = build_ward_champions_chart(ward_champions(submissions))

    assert fig.data[0].customdata is not None
    assert set(fig.data[0].text) == {"wa-1", "ussd-9"}


def test_ward_champions_chart_handles_empty_input():
    fig = build_ward_champions_chart(ward_champions([]))

    assert fig is not None


def test_ward_champions_chart_leaves_room_for_the_longest_label():
    submissions = [_submission("wa-1", "Kimintet")] * 30 + [_submission("ussd-9", "Chebunyo")]

    fig = build_ward_champions_chart(ward_champions(submissions))

    assert fig.layout.xaxis.range[1] > 30


def test_ward_champions_chart_grows_with_the_number_of_wards():
    few = ward_champions([_submission("wa-1", "Kimintet")])
    many = ward_champions([_submission(f"wa-{i}", f"Ward {i}") for i in range(20)])

    short = build_ward_champions_chart(few).layout.height
    tall = build_ward_champions_chart(many).layout.height

    assert tall > short


def test_ward_champions_handles_data_without_a_submitter_column():
    submissions = [{"ward": "Kimintet", "status": "APPROVED"}]

    assert ward_champions(submissions).empty
    assert distinct_submitters(submissions) == 0


def test_ward_champions_handles_data_with_no_approved_rows():
    submissions = [_submission("wa-1", "Kimintet", status="PENDING")]

    assert ward_champions(submissions).empty
    assert distinct_submitters(submissions) == 0


def test_champions_are_counted_only_from_pollution_reports():
    """Non-pollution forms carry non-person submitters such as a quarter label."""
    records = [
        {"form_name": "Pollution Reporting Form", "form_id": 1, "uuid": "u1", "status": "APPROVED",
         "submitter": "wa-1", "ward": "Kimintet"},
        {"form_name": "Monthly Wetland Sampling", "form_id": 2, "uuid": "u2", "status": "APPROVED",
         "submitter": "2026-Q2", "ward": "Kimintet"},
        {"form_name": "Lab QA Report", "form_id": 4, "uuid": "u3", "status": "APPROVED",
         "submitter": "lab-tech", "ward": "Kimintet"},
    ]

    pollution_only = filter_pollution_reporting_records(records)

    assert distinct_submitters(pollution_only) == 1
    assert ward_champions(pollution_only)["champion"].tolist() == ["wa-1"]
    assert ward_champions(pollution_only)["reports"].tolist() == [1]


def test_champion_submissions_returns_the_rows_behind_a_champion_bar():
    submissions = [
        _submission("wa-1", "Kimintet"),
        _submission("wa-1", "Kimintet"),
        _submission("wa-2", "Kimintet"),
        _submission("wa-1", "Chebunyo"),
    ]

    result = champion_submissions(submissions, ward="Kimintet", champion="wa-1")

    assert len(result) == 2
    assert result["ward"].tolist() == ["Kimintet", "Kimintet"]
    assert result["submitter"].tolist() == ["wa-1", "wa-1"]


def test_champion_submissions_row_count_matches_the_bar_it_was_clicked_from():
    submissions = [
        _submission("wa-1", "Kimintet"),
        _submission("wa-1", "Kimintet"),
        _submission("wa-1", "Kimintet", status="PENDING"),
        _submission("ussd-9", "Chebunyo"),
    ]
    champions = ward_champions(submissions)

    for _, row in champions.iterrows():
        rows = champion_submissions(submissions, ward=row["ward"], champion=row["champion"])
        assert len(rows) == int(row["reports"])


def test_champion_submissions_excludes_reports_that_are_not_approved():
    submissions = [
        _submission("wa-1", "Kimintet"),
        _submission("wa-1", "Kimintet", status="PENDING"),
        _submission("wa-1", "Kimintet", status="REJECTED"),
    ]

    result = champion_submissions(submissions, ward="Kimintet", champion="wa-1")

    assert len(result) == 1


def test_champion_submissions_matches_wards_recorded_as_a_reported_location():
    submissions = [
        {"submitter": "wa-1", "ward": None, "reported_location": "Kilgoris", "status": "APPROVED"},
    ]

    result = champion_submissions(submissions, ward="Kilgoris", champion="wa-1")

    assert len(result) == 1


def test_champion_submissions_matches_placeless_rows_through_the_unknown_ward():
    submissions = [{"submitter": "wa-1", "status": "APPROVED"}]

    result = champion_submissions(submissions, ward="Unknown", champion="wa-1")

    assert len(result) == 1


def test_champion_submissions_keeps_the_original_columns():
    submissions = [
        {
            "submitter": "wa-1",
            "ward": "Kimintet",
            "status": "APPROVED",
            "incident_type_name": "Solid waste",
        }
    ]

    result = champion_submissions(submissions, ward="Kimintet", champion="wa-1")

    assert result["incident_type_name"].tolist() == ["Solid waste"]


def test_champion_submissions_ignores_surrounding_whitespace():
    submissions = [{"submitter": " wa-1 ", "ward": " Kimintet ", "status": "APPROVED"}]

    result = champion_submissions(submissions, ward="Kimintet", champion="wa-1")

    assert len(result) == 1


def test_champion_submissions_returns_nothing_for_an_unknown_champion():
    submissions = [_submission("wa-1", "Kimintet")]

    assert champion_submissions(submissions, ward="Kimintet", champion="wa-9").empty


def test_champion_submissions_handles_empty_input():
    result = champion_submissions([], ward="Kimintet", champion="wa-1")

    assert result.empty


def test_champion_submissions_handles_a_missing_selection():
    submissions = [_submission("wa-1", "Kimintet")]

    assert champion_submissions(submissions, ward=None, champion=None).empty


def test_champion_submissions_does_not_mutate_the_caller_frame():
    frame = pd.DataFrame([_submission("wa-1", "Kimintet")])
    before = frame.copy()

    champion_submissions(frame, ward="Kimintet", champion="wa-1")

    pd.testing.assert_frame_equal(frame, before)
