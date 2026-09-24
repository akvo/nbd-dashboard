from __future__ import annotations

import pandas as pd

from src.filters import ALL_OPTION, apply_filters, select_options


SUBMISSIONS = pd.DataFrame(
    [
        {"id": 1, "county": "Narok", "ward": "Kimintet", "basin_name": "Mara Basin"},
        {"id": 2, "county": "Narok", "ward": None, "basin_name": "Mara Basin"},
        {"id": 3, "county": "Busia", "ward": "Nambale Township", "basin_name": "Sio-Siteko Basin"},
    ]
)


def test_apply_filters_keeps_every_row_when_nothing_is_selected():
    result = apply_filters(SUBMISSIONS, {"county": ALL_OPTION, "ward": None})

    assert result["id"].tolist() == [1, 2, 3]


def test_apply_filters_narrows_rows_to_the_selected_value():
    result = apply_filters(SUBMISSIONS, {"county": "Narok"})

    assert result["id"].tolist() == [1, 2]


def test_apply_filters_combines_several_selections():
    result = apply_filters(SUBMISSIONS, {"county": "Narok", "ward": "Kimintet"})

    assert result["id"].tolist() == [1]


def test_apply_filters_excludes_rows_missing_the_filtered_value():
    result = apply_filters(SUBMISSIONS, {"ward": "Kimintet"})

    assert result["id"].tolist() == [1]


def test_apply_filters_ignores_columns_the_dataframe_does_not_have():
    result = apply_filters(SUBMISSIONS, {"sub_county": "Kilgoris"})

    assert result["id"].tolist() == [1, 2, 3]


def test_apply_filters_does_not_mutate_the_input():
    original = SUBMISSIONS.copy()

    apply_filters(SUBMISSIONS, {"county": "Narok"})

    pd.testing.assert_frame_equal(SUBMISSIONS, original)


def test_apply_filters_returns_an_empty_frame_unchanged():
    empty = pd.DataFrame()

    assert apply_filters(empty, {"county": "Narok"}).empty


def test_select_options_prefixes_the_all_option():
    assert select_options(["Narok", "Busia"]) == [ALL_OPTION, "Narok", "Busia"]


def test_select_options_falls_back_to_observed_values():
    assert select_options([], ["Kilgoris", "Chepalungu", "Kilgoris", None]) == [
        ALL_OPTION,
        "Chepalungu",
        "Kilgoris",
    ]


def test_select_options_returns_only_the_all_option_when_nothing_is_available():
    assert select_options([]) == [ALL_OPTION]
