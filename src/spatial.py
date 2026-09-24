"""Spatial boundary helpers for the NBD reference hierarchy.

The API exposes every administrative boundary through a single endpoint,
``GET /api/v1/reference/sub-counties``, as a flat list of records shaped like
:class:`SpatialBoundary`::

    {"id": ..., "name": ..., "level": 2, "parent_id": ..., "basin_id": ...}

Levels are ``1=Region``, ``2=County``, ``3=Sub-county`` and ``4=Ward``. The
helpers here turn that flat list into a frame that carries the resolved
ancestry of every boundary so the dashboard can offer real county, sub-county
and ward filters, and can label submissions that only report a place name.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


SUB_COUNTIES_ENDPOINT = "api/v1/reference/sub-counties"

LEVEL_REGION = 1
LEVEL_COUNTY = 2
LEVEL_SUB_COUNTY = 3
LEVEL_WARD = 4

BOUNDARY_COLUMNS = [
    "boundary_id",
    "name",
    "level",
    "parent_id",
    "basin_id",
    "county",
    "sub_county",
    "ward",
]

# A boundary is at most four levels deep; the guard also breaks parent cycles.
_MAX_ANCESTRY_DEPTH = LEVEL_WARD


def _clean_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    return cleaned or None


def _clean_level(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None

    return value


def _valid_boundary(record: Any) -> dict[str, Any] | None:
    """Return a validated boundary, or ``None`` when the record is unusable."""
    if not isinstance(record, dict):
        return None

    boundary_id = _clean_name(record.get("id"))
    name = _clean_name(record.get("name"))
    level = _clean_level(record.get("level"))

    if boundary_id is None or name is None or level is None:
        return None

    return {
        "boundary_id": boundary_id,
        "name": name,
        "level": level,
        "parent_id": _clean_name(record.get("parent_id")),
        "basin_id": _clean_name(record.get("basin_id")),
    }


def _none_where_missing(series: pd.Series) -> pd.Series:
    return series.astype("object").where(series.notna(), None)


def _ancestry(boundary: dict[str, Any], boundaries_by_id: dict[str, dict[str, Any]]) -> dict[int, str]:
    """Map each level in a boundary's ancestry to the name at that level."""
    names_by_level: dict[int, str] = {}

    current: dict[str, Any] | None = boundary
    for _ in range(_MAX_ANCESTRY_DEPTH):
        if current is None:
            break

        names_by_level.setdefault(current["level"], current["name"])
        parent_id = current["parent_id"]
        current = boundaries_by_id.get(parent_id) if parent_id else None

    return names_by_level


def build_boundary_frame(records: list[Any] | None) -> pd.DataFrame:
    """Build a boundary frame with the county, sub-county and ward resolved."""
    boundaries = [
        boundary for boundary in (_valid_boundary(record) for record in records or []) if boundary is not None
    ]

    if not boundaries:
        return pd.DataFrame(columns=BOUNDARY_COLUMNS)

    boundaries_by_id = {boundary["boundary_id"]: boundary for boundary in boundaries}

    rows = []
    for boundary in boundaries:
        names_by_level = _ancestry(boundary, boundaries_by_id)
        rows.append(
            {
                **boundary,
                "county": names_by_level.get(LEVEL_COUNTY),
                "sub_county": names_by_level.get(LEVEL_SUB_COUNTY),
                "ward": names_by_level.get(LEVEL_WARD),
            }
        )

    frame = pd.DataFrame(rows, columns=BOUNDARY_COLUMNS)

    # pandas turns missing text into NaN; keep a single "missing" value so
    # callers can compare against None everywhere.
    for column in ("parent_id", "basin_id", "county", "sub_county", "ward"):
        frame[column] = _none_where_missing(frame[column])

    return frame


def _names_at_level(
    boundaries: pd.DataFrame,
    level: int,
    filters: dict[str, str | None],
) -> list[str]:
    if boundaries.empty:
        return []

    selected = boundaries[boundaries["level"] == level]

    for column, value in filters.items():
        if value:
            selected = selected[selected[column] == value]

    names = selected["name"].dropna().astype(str).unique().tolist()
    return sorted(names)


def county_names(boundaries: pd.DataFrame, basin_id: str | None = None) -> list[str]:
    """List every county, optionally limited to a single basin."""
    return _names_at_level(boundaries, LEVEL_COUNTY, {"basin_id": basin_id})


def sub_county_names(
    boundaries: pd.DataFrame,
    county: str | None = None,
    basin_id: str | None = None,
) -> list[str]:
    """List every sub-county, optionally limited to a county or basin."""
    return _names_at_level(boundaries, LEVEL_SUB_COUNTY, {"county": county, "basin_id": basin_id})


def ward_names(
    boundaries: pd.DataFrame,
    county: str | None = None,
    sub_county: str | None = None,
    basin_id: str | None = None,
) -> list[str]:
    """List every ward, optionally limited to a county, sub-county or basin."""
    return _names_at_level(
        boundaries,
        LEVEL_WARD,
        {"county": county, "sub_county": sub_county, "basin_id": basin_id},
    )


def _lookup_key(value: Any) -> str | None:
    cleaned = _clean_name(value)
    return cleaned.casefold() if cleaned else None


def build_location_lookup(boundaries: pd.DataFrame) -> dict[str, dict[str, str | None]]:
    """Map a boundary name to its county, sub-county and ward.

    Names are matched case-insensitively. A name used at more than one level
    (a sub-county and one of its wards can share a name) resolves to the most
    specific boundary, which keeps the county and sub-county unambiguous.
    """
    lookup: dict[str, dict[str, str | None]] = {}

    if boundaries.empty:
        return lookup

    ordered = boundaries.sort_values(["level", "boundary_id"], kind="stable")

    for row in ordered.to_dict("records"):
        key = _lookup_key(row.get("name"))
        if key is None:
            continue

        lookup[key] = {
            "county": row.get("county"),
            "sub_county": row.get("sub_county"),
            "ward": row.get("ward"),
        }

    return lookup


def annotate_spatial_columns(
    dataframe: pd.DataFrame,
    boundaries: pd.DataFrame,
    location_column: str = "reported_location",
) -> pd.DataFrame:
    """Return a copy of ``dataframe`` with county, sub-county and ward filled in.

    Values already present in the frame win over the resolved ones, so data
    that carries its own geography is never overwritten.
    """
    annotated = dataframe.copy()
    lookup = build_location_lookup(boundaries)

    if location_column in annotated.columns:
        keys = annotated[location_column].map(_lookup_key)
    else:
        keys = pd.Series([None] * len(annotated), index=annotated.index, dtype="object")

    for column in ("county", "sub_county", "ward"):
        resolved = keys.map(lambda key: lookup.get(key, {}).get(column) if key else None)

        if column in annotated.columns:
            existing = annotated[column].where(annotated[column].notna(), None)
            resolved = existing.combine_first(resolved)

        annotated[column] = _none_where_missing(resolved)

    return annotated
