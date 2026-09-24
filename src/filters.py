"""Sidebar filter helpers.

The dashboard filters are plain "one value or everything" selections, so the
logic is kept here as pure functions over dataframes and option lists.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


ALL_OPTION = "All"


def _is_selected(value: Any) -> bool:
    return bool(value) and value != ALL_OPTION


def apply_filters(dataframe: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    """Return the rows of ``dataframe`` that match every selected filter.

    Filters naming a column the frame does not carry are skipped, because the
    dataset simply does not describe that dimension.
    """
    filtered = dataframe

    for column, value in filters.items():
        if not _is_selected(value) or column not in filtered.columns:
            continue

        filtered = filtered[filtered[column].fillna("").astype(str) == str(value)]

    return filtered.copy()


def select_options(reference_names: list[str] | None, observed_values: list[Any] | None = None) -> list[str]:
    """Build selectbox options, preferring the reference list over the data.

    The reference endpoints describe the full hierarchy, so they give a stable
    option list. Values observed in the data are a fallback for when a
    reference lookup is unavailable.
    """
    names = [str(name) for name in reference_names or [] if name is not None and str(name).strip()]

    if not names:
        unique_observed = {
            str(value).strip()
            for value in observed_values or []
            if value is not None and str(value).strip()
        }
        names = sorted(unique_observed)

    return [ALL_OPTION, *names]
