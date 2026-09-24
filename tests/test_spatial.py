from __future__ import annotations

import pandas as pd

from src.spatial import (
    LEVEL_COUNTY,
    LEVEL_SUB_COUNTY,
    LEVEL_WARD,
    annotate_spatial_columns,
    build_boundary_frame,
    build_location_lookup,
    county_names,
    sub_county_names,
    ward_names,
)


MARA_BASIN = "basin-mara"
SIO_BASIN = "basin-sio"

BOUNDARY_RECORDS = [
    {"id": "r1", "name": "Mara Region", "level": 1, "parent_id": None, "basin_id": MARA_BASIN},
    {"id": "c1", "name": "Narok", "level": 2, "parent_id": "r1", "basin_id": MARA_BASIN},
    {"id": "s1", "name": "Kilgoris", "level": 3, "parent_id": "c1", "basin_id": MARA_BASIN},
    {"id": "w1", "name": "Kimintet", "level": 4, "parent_id": "s1", "basin_id": MARA_BASIN},
    {"id": "r2", "name": "Sio-Siteko Region", "level": 1, "parent_id": None, "basin_id": SIO_BASIN},
    {"id": "c2", "name": "Busia", "level": 2, "parent_id": "r2", "basin_id": SIO_BASIN},
    {"id": "s2", "name": "Nambale", "level": 3, "parent_id": "c2", "basin_id": SIO_BASIN},
    {"id": "w2", "name": "Nambale Township", "level": 4, "parent_id": "s2", "basin_id": SIO_BASIN},
]


def test_build_boundary_frame_returns_empty_frame_for_empty_input():
    frame = build_boundary_frame([])

    assert frame.empty
    assert list(frame.columns) == [
        "boundary_id",
        "name",
        "level",
        "parent_id",
        "basin_id",
        "county",
        "sub_county",
        "ward",
    ]


def test_build_boundary_frame_resolves_the_full_ancestry_of_a_ward():
    frame = build_boundary_frame(BOUNDARY_RECORDS)

    ward_row = frame[frame["boundary_id"] == "w1"].iloc[0]

    assert ward_row["county"] == "Narok"
    assert ward_row["sub_county"] == "Kilgoris"
    assert ward_row["ward"] == "Kimintet"
    assert ward_row["level"] == LEVEL_WARD


def test_build_boundary_frame_labels_counties_and_sub_counties():
    frame = build_boundary_frame(BOUNDARY_RECORDS).set_index("boundary_id")

    assert frame.loc["c1", "county"] == "Narok"
    assert frame.loc["c1", "sub_county"] is None
    assert frame.loc["c1", "level"] == LEVEL_COUNTY

    assert frame.loc["s1", "county"] == "Narok"
    assert frame.loc["s1", "sub_county"] == "Kilgoris"
    assert frame.loc["s1", "level"] == LEVEL_SUB_COUNTY


def test_build_boundary_frame_leaves_regions_without_a_county():
    frame = build_boundary_frame(BOUNDARY_RECORDS).set_index("boundary_id")

    assert frame.loc["r1", "county"] is None


def test_build_boundary_frame_skips_malformed_records():
    records = [
        *BOUNDARY_RECORDS,
        "not-a-record",
        {"name": "No identifier", "level": 2},
        {"id": "x1", "level": 2},
        {"id": "x2", "name": "Bad level", "level": "two"},
    ]

    frame = build_boundary_frame(records)

    assert len(frame) == len(BOUNDARY_RECORDS)


def test_build_boundary_frame_tolerates_a_parent_cycle():
    records = [
        {"id": "a", "name": "A", "level": 3, "parent_id": "b", "basin_id": MARA_BASIN},
        {"id": "b", "name": "B", "level": 2, "parent_id": "a", "basin_id": MARA_BASIN},
    ]

    frame = build_boundary_frame(records).set_index("boundary_id")

    assert frame.loc["a", "county"] == "B"


def test_county_names_returns_sorted_unique_counties():
    frame = build_boundary_frame(BOUNDARY_RECORDS)

    assert county_names(frame) == ["Busia", "Narok"]


def test_county_names_can_be_limited_to_one_basin():
    frame = build_boundary_frame(BOUNDARY_RECORDS)

    assert county_names(frame, basin_id=MARA_BASIN) == ["Narok"]


def test_county_names_returns_empty_list_for_empty_frame():
    assert county_names(build_boundary_frame([])) == []


def test_sub_county_names_can_be_limited_to_one_county():
    frame = build_boundary_frame(BOUNDARY_RECORDS)

    assert sub_county_names(frame, county="Narok") == ["Kilgoris"]
    assert sub_county_names(frame) == ["Kilgoris", "Nambale"]


def test_ward_names_can_be_limited_to_county_and_sub_county():
    frame = build_boundary_frame(BOUNDARY_RECORDS)

    assert ward_names(frame, county="Narok") == ["Kimintet"]
    assert ward_names(frame, county="Busia", sub_county="Nambale") == ["Nambale Township"]
    assert ward_names(frame, county="Busia", sub_county="Kilgoris") == []


def test_annotate_spatial_columns_adds_county_and_sub_county():
    frame = build_boundary_frame(BOUNDARY_RECORDS)
    submissions = pd.DataFrame(
        [
            {"id": 1, "reported_location": "Kimintet"},
            {"id": 2, "reported_location": "Kilgoris"},
            {"id": 3, "reported_location": "Unknown place"},
            {"id": 4, "reported_location": None},
        ]
    )

    annotated = annotate_spatial_columns(submissions, frame)

    assert annotated["county"].tolist() == ["Narok", "Narok", None, None]
    assert annotated["sub_county"].tolist() == ["Kilgoris", "Kilgoris", None, None]
    assert annotated["ward"].tolist() == ["Kimintet", None, None, None]


def test_annotate_spatial_columns_does_not_mutate_the_input():
    frame = build_boundary_frame(BOUNDARY_RECORDS)
    submissions = pd.DataFrame([{"id": 1, "reported_location": "Kimintet"}])

    annotate_spatial_columns(submissions, frame)

    assert "county" not in submissions.columns


def test_annotate_spatial_columns_matches_names_case_insensitively():
    frame = build_boundary_frame(BOUNDARY_RECORDS)
    submissions = pd.DataFrame([{"reported_location": "  kimintet "}])

    annotated = annotate_spatial_columns(submissions, frame)

    assert annotated.loc[0, "county"] == "Narok"


def test_annotate_spatial_columns_prefers_the_most_specific_duplicate_name():
    records = [
        *BOUNDARY_RECORDS,
        {"id": "s3", "name": "Bumula", "level": 3, "parent_id": "c2", "basin_id": SIO_BASIN},
        {"id": "w3", "name": "Bumula", "level": 4, "parent_id": "s3", "basin_id": SIO_BASIN},
    ]
    frame = build_boundary_frame(records)
    submissions = pd.DataFrame([{"reported_location": "Bumula"}])

    annotated = annotate_spatial_columns(submissions, frame)

    assert annotated.loc[0, "county"] == "Busia"
    assert annotated.loc[0, "sub_county"] == "Bumula"
    assert annotated.loc[0, "ward"] == "Bumula"


def test_annotate_spatial_columns_handles_missing_location_column():
    frame = build_boundary_frame(BOUNDARY_RECORDS)
    submissions = pd.DataFrame([{"id": 1}])

    annotated = annotate_spatial_columns(submissions, frame)

    assert annotated["county"].isna().all()


def test_annotate_spatial_columns_returns_input_when_boundaries_are_missing():
    submissions = pd.DataFrame([{"reported_location": "Kimintet"}])

    annotated = annotate_spatial_columns(submissions, build_boundary_frame([]))

    assert annotated["county"].isna().all()
    assert annotated["reported_location"].tolist() == ["Kimintet"]


def test_annotate_spatial_columns_keeps_an_existing_county_value():
    frame = build_boundary_frame(BOUNDARY_RECORDS)
    submissions = pd.DataFrame(
        [
            {"reported_location": "Kimintet", "county": "Already Set"},
            {"reported_location": "Nambale Township", "county": None},
        ]
    )

    annotated = annotate_spatial_columns(submissions, frame)

    assert annotated["county"].tolist() == ["Already Set", "Busia"]


def test_build_location_lookup_skips_boundaries_without_a_name():
    frame = pd.DataFrame(
        [
            {
                "boundary_id": "c1",
                "name": None,
                "level": LEVEL_COUNTY,
                "parent_id": None,
                "basin_id": MARA_BASIN,
                "county": None,
                "sub_county": None,
                "ward": None,
            }
        ]
    )

    assert build_location_lookup(frame) == {}
