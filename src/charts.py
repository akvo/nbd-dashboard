from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
import plotly.express as px


def build_champions_per_ward_chart(champions_per_ward: pd.DataFrame):
    """Create a horizontal bar chart for champions per ward."""
    if champions_per_ward.empty:
        return px.bar(pd.DataFrame(columns=["ward", "champions"]), x="champions", y="ward", orientation="h")

    return px.bar(
        champions_per_ward,
        x="champions",
        y="ward",
        orientation="h",
        title="Champions per Ward",
        color="champions",
        color_continuous_scale="Viridis",
    )


def build_cumulative_submissions_chart(cumulative_submissions: pd.DataFrame):
    """Create a line chart for cumulative submissions."""
    if cumulative_submissions.empty:
        return px.line(pd.DataFrame(columns=["submitted_at", "cumulative_submissions"]), x="submitted_at", y="cumulative_submissions")

    return px.line(
        cumulative_submissions,
        x="submitted_at",
        y="cumulative_submissions",
        title="Cumulative Submissions",
    )


def build_weekly_submissions_chart(weekly_submissions: pd.DataFrame):
    """Create a bar chart for weekly submissions."""
    if weekly_submissions.empty:
        return px.bar(pd.DataFrame(columns=["week", "submissions"]), x="week", y="submissions")

    return px.bar(
        weekly_submissions,
        x="week",
        y="submissions",
        title="Weekly Submissions",
        custom_data=["week"],
    )


def build_weekly_submissions_by_channel_chart(weekly_submissions_by_channel: pd.DataFrame):
    """Create a stacked bar chart for weekly submissions grouped by channel."""
    if weekly_submissions_by_channel.empty:
        return px.bar(
            pd.DataFrame(columns=["week", "channel", "submissions"]),
            x="week",
            y="submissions",
            color="channel",
            barmode="stack",
        )

    return px.bar(
        weekly_submissions_by_channel,
        x="week",
        y="submissions",
        color="channel",
        barmode="stack",
        title="Weekly Submissions by Channel",
        custom_data=["week", "channel"],
    )


def build_submissions_by_ward_chart(submissions_by_ward: pd.DataFrame):
    """Create a horizontal bar chart for submission totals by ward."""
    if submissions_by_ward.empty:
        return px.bar(pd.DataFrame(columns=["ward", "submissions"]), x="submissions", y="ward", orientation="h")

    return px.bar(
        submissions_by_ward,
        x="submissions",
        y="ward",
        orientation="h",
        title="Submissions by Ward",
        color="submissions",
        color_continuous_scale="Viridis",
        custom_data=["ward"],
    )


# Categorical hues assigned in a fixed order so an incident never changes colour
# when the filters change how many incidents are on screen. Each set is validated
# for colour-vision-deficiency separation and contrast against its own surface, so
# the dark steps are a deliberate selection rather than a flip of the light ones.
INCIDENT_TYPE_COLOURS: dict[str, tuple[str, ...]] = {
    "light": (
        "#2a78d6",  # blue
        "#eb6834",  # orange
        "#1baf7a",  # aqua
        "#eda100",  # yellow
        "#e87ba4",  # magenta
        "#008300",  # green
        "#4a3aa7",  # violet
        "#e34948",  # red
    ),
    "dark": (
        "#3987e5",  # blue
        "#d95926",  # orange
        "#199e70",  # aqua
        "#c98500",  # yellow
        "#d55181",  # magenta
        "#008300",  # green
        "#9085e9",  # violet
        "#e66767",  # red
    ),
}
DEFAULT_THEME = "light"
OTHER_INCIDENT_TYPE = "Other"
OTHER_INCIDENT_TYPE_COLOURS: dict[str, str] = {"light": "#7a7973", "dark": "#94938a"}

# Room left past the longest bar for the label drawn beyond its end.
LABEL_HEADROOM = 1.45
CHART_HEIGHT_PER_ROW = 34
MIN_CHART_HEIGHT = 320


def _palette(theme: str | None) -> tuple[str, ...]:
    return INCIDENT_TYPE_COLOURS.get(str(theme), INCIDENT_TYPE_COLOURS[DEFAULT_THEME])


def incident_type_colour_map(incident_types: Iterable[str], theme: str | None = DEFAULT_THEME) -> dict[str, str]:
    """Map each incident type to a fixed hue, keyed by name rather than rank.

    Pass the complete, unfiltered set of incident types so that an incident keeps
    the same hue whichever subset the active filters leave on screen.
    """
    palette = _palette(theme)
    named_types = sorted({str(name) for name in incident_types})
    colour_map = {name: palette[index] for index, name in enumerate(named_types[: len(palette)])}
    colour_map[OTHER_INCIDENT_TYPE] = OTHER_INCIDENT_TYPE_COLOURS.get(
        str(theme), OTHER_INCIDENT_TYPE_COLOURS[DEFAULT_THEME]
    )
    return colour_map


def _palette_incident_types(incident_types: Iterable[str], theme: str | None = DEFAULT_THEME) -> list[str]:
    """Return the incident names that get a hue of their own, in assignment order."""
    named_types = sorted({str(name) for name in incident_types})
    return named_types[: len(_palette(theme))]


def incident_types_for_label(
    label: str,
    incident_types: Iterable[str],
    theme: str | None = DEFAULT_THEME,
) -> set[str]:
    """Return the real incident names that a clicked bar stands for.

    Every bar maps to itself except the synthetic "Other" bar, which stands for
    the incidents that were folded into it because the palette ran out of hues.
    """
    named_types = sorted({str(name) for name in incident_types})
    palette_types = set(_palette_incident_types(named_types, theme))
    label = str(label)

    if label in palette_types or label != OTHER_INCIDENT_TYPE:
        return {label}

    return set(named_types) - palette_types


def _fold_extra_incident_types(
    submissions_by_incident_type: pd.DataFrame,
    colour_map: dict[str, str],
) -> pd.DataFrame:
    """Collapse incidents that have no hue of their own into a single "Other" row."""
    folded = submissions_by_incident_type.copy()
    folded["incident_type"] = folded["incident_type"].astype(str)

    if folded["incident_type"].isin(colour_map).all():
        return folded

    folded["incident_type"] = folded["incident_type"].map(
        lambda name: name if name in colour_map else OTHER_INCIDENT_TYPE
    )

    return (
        folded.groupby("incident_type", dropna=False)["submissions"]
        .sum()
        .reset_index()
        .sort_values("submissions", ascending=False)
        .reset_index(drop=True)
    )


def build_submissions_by_incident_type_chart(
    submissions_by_incident_type: pd.DataFrame,
    incident_types: Iterable[str] | None = None,
    theme: str | None = DEFAULT_THEME,
):
    """Create a horizontal bar chart of submission counts per incident type.

    ``incident_types`` is the complete, unfiltered list of incident types; it keeps
    the hues stable while the dashboard filters narrow the chart down. ``theme``
    selects the palette validated for the surface the chart is drawn on.
    """
    if submissions_by_incident_type.empty:
        return px.bar(
            pd.DataFrame(columns=["incident_type", "submissions"]),
            x="submissions",
            y="incident_type",
            color="incident_type",
            orientation="h",
        )

    if incident_types is None:
        incident_types = submissions_by_incident_type["incident_type"]

    colour_map = incident_type_colour_map(incident_types, theme)
    chart_df = _fold_extra_incident_types(submissions_by_incident_type, colour_map)

    figure = px.bar(
        chart_df,
        x="submissions",
        y="incident_type",
        orientation="h",
        title="Reported Incidents by Type",
        color="incident_type",
        color_discrete_map=colour_map,
        category_orders={"incident_type": chart_df["incident_type"].tolist()},
        text="submissions",
        custom_data=["incident_type"],
    )
    figure.update_traces(textposition="outside", cliponaxis=False)
    figure.update_layout(
        # Every bar is already named on the y axis, so a legend would repeat the
        # same labels; identity never rests on colour alone here.
        showlegend=False,
        xaxis_title="Submissions",
        yaxis_title="",
        bargap=0.3,
        margin={"l": 8, "r": 40},
    )
    figure.update_yaxes(automargin=True)
    return figure


def build_ward_champions_chart(ward_champions: pd.DataFrame):
    """Create a horizontal bar chart naming each ward's champion."""
    if ward_champions.empty:
        return px.bar(
            pd.DataFrame(columns=["ward", "reports"]),
            x="reports",
            y="ward",
            orientation="h",
        )

    figure = px.bar(
        ward_champions,
        x="reports",
        y="ward",
        orientation="h",
        title="Champions per Ward",
        color="reports",
        color_continuous_scale="Viridis",
        category_orders={"ward": ward_champions["ward"].astype(str).tolist()},
        text="champion",
        custom_data=["ward", "champion", "reports"],
    )
    figure.update_traces(
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{customdata[0]}</b><br>Champion: %{customdata[1]}<br>Approved reports: %{customdata[2]}<extra></extra>",
    )
    # The champion name is drawn past the end of its bar, so the x axis needs
    # headroom or the longest bar's label runs off the edge of the plot.
    most_reports = int(ward_champions["reports"].max())

    figure.update_layout(
        xaxis_title="Approved reports",
        yaxis_title="",
        bargap=0.3,
        margin={"l": 8, "r": 24},
        coloraxis_showscale=False,
        xaxis_range=[0, most_reports * LABEL_HEADROOM],
        height=max(MIN_CHART_HEIGHT, CHART_HEIGHT_PER_ROW * len(ward_champions)),
    )
    figure.update_yaxes(automargin=True)
    return figure
