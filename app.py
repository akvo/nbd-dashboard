import pandas as pd
import streamlit as st

from src.api import fetch_records, fetch_reference_records, load_api_config
from src.charts import (
    build_cumulative_submissions_chart,
    build_submissions_by_incident_type_chart,
    build_submissions_by_ward_chart,
    build_ward_champions_chart,
    build_weekly_submissions_by_channel_chart,
    build_weekly_submissions_chart,
    incident_types_for_label,
)
from src.filters import ALL_OPTION, apply_filters, select_options
from src.metrics import (
    champion_submissions,
    cumulative_submissions,
    distinct_submitters,
    normalize_incident_type_names,
    submissions_by_incident_type,
    submissions_by_ward,
    ward_champions,
    weekly_submissions,
    weekly_submissions_by_channel,
)
from src.spatial import (
    SUB_COUNTIES_ENDPOINT,
    annotate_spatial_columns,
    build_boundary_frame,
    county_names,
    sub_county_names,
    ward_names,
)
from src.transforms import build_dataset, filter_pollution_reporting_records


st.set_page_config(page_title="NBD Dashboard", layout="wide")


def _empty_statistics() -> dict[str, int]:
    return {
        "record_count": 0,
        "duplicate_submission_ids": 0,
        "missing_county": 0,
        "missing_ward": 0,
        "invalid_dates": 0,
    }


def _column_values(dataframe: pd.DataFrame, column_name: str) -> list[str]:
    if dataframe.empty or column_name not in dataframe.columns:
        return []

    return dataframe[column_name].dropna().astype(str).tolist()


def _observed_values(dataframe: pd.DataFrame, *column_names: str) -> list[str]:
    """Return the values of the first column that actually carries data."""
    for column_name in column_names:
        values = _column_values(dataframe, column_name)
        if values:
            return values

    return []


def _selection(value: str | None) -> str | None:
    return None if not value or value == ALL_OPTION else value


def _week_over_week_change(weekly_df: pd.DataFrame) -> float | None:
    if weekly_df.empty:
        return None

    current_week = int(weekly_df.iloc[-1]["submissions"])
    previous_week = int(weekly_df.iloc[-2]["submissions"]) if len(weekly_df) > 1 else 0

    if previous_week == 0:
        return None if current_week else 0.0

    return round(((current_week - previous_week) / previous_week) * 100, 2)


def _submission_channel(submitter: str | None) -> str:
    if not submitter:
        return "unknown"

    submitter_str = str(submitter)
    if submitter_str.startswith("wa-"):
        return "whatsapp"
    if submitter_str.startswith("ussd-"):
        return "ussd"
    return "unknown"


def _active_theme() -> str:
    """Return the theme Streamlit is currently rendering with.

    The chart palettes are validated per surface, so the chart needs to know
    which one it is being drawn on. Older Streamlit builds expose no theme at
    all, in which case the light palette is the safe default.
    """
    context = getattr(st, "context", None)
    theme = getattr(context, "theme", None)
    theme_type = getattr(theme, "type", None)

    return str(theme_type) if theme_type in ("light", "dark") else "light"


def _extract_plotly_selection_points(chart_event) -> list[dict[str, object]]:
    if chart_event is None:
        return []

    selection = getattr(chart_event, "selection", None)
    if selection is None:
        return []

    points = getattr(selection, "points", None)
    if points is None:
        return []

    return list(points)


def _extract_customdata(point: dict[str, object]) -> list[str]:
    raw_customdata = point.get("customdata")
    if raw_customdata is None:
        return []

    if isinstance(raw_customdata, (list, tuple)) and raw_customdata and isinstance(raw_customdata[0], (list, tuple)):
        raw_customdata = raw_customdata[0]

    if isinstance(raw_customdata, (list, tuple)):
        return [str(value) if value is not None else "" for value in raw_customdata]

    return [str(raw_customdata)]


def _extract_weekly_channel_selection(chart_event) -> dict[str, str] | None:
    for point in _extract_plotly_selection_points(chart_event):
        customdata = _extract_customdata(point)
        if len(customdata) >= 2:
            return {"week": customdata[0], "channel": customdata[1]}

    return None


def _extract_ward_selection(chart_event) -> dict[str, str] | None:
    for point in _extract_plotly_selection_points(chart_event):
        customdata = _extract_customdata(point)
        if customdata:
            return {"ward": customdata[0]}

    return None


def _extract_champion_selection(chart_event) -> dict[str, str] | None:
    for point in _extract_plotly_selection_points(chart_event):
        customdata = _extract_customdata(point)
        if len(customdata) >= 2:
            return {"ward": customdata[0], "champion": customdata[1]}

    return None


def _extract_incident_type_selection(chart_event) -> dict[str, str] | None:
    for point in _extract_plotly_selection_points(chart_event):
        customdata = _extract_customdata(point)
        if customdata:
            return {"incident_type": customdata[0]}

    return None


def _extract_week_selection(chart_event) -> dict[str, str] | None:
    for point in _extract_plotly_selection_points(chart_event):
        customdata = _extract_customdata(point)
        if customdata:
            return {"week": customdata[0]}

    return None


def _filter_selected_submissions(
    dataframe: pd.DataFrame,
    selected_week: dict[str, str] | None = None,
    selected_week_channel: dict[str, str] | None = None,
    selected_ward: dict[str, str] | None = None,
    selected_incident_type: dict[str, str] | None = None,
    selected_champion: dict[str, str] | None = None,
    incident_types: list[str] | None = None,
) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe

    selected_df = dataframe.copy()

    def _filter_by_week(df: pd.DataFrame, week_value: str | None) -> pd.DataFrame:
        if not week_value:
            return df

        week_start = pd.Timestamp(pd.to_datetime(week_value))
        week_end = week_start + pd.Timedelta(weeks=1)

        timestamp_column = "submitted_at" if "submitted_at" in df.columns else "created_at"
        if timestamp_column not in df.columns:
            return df

        timestamps = pd.to_datetime(df[timestamp_column], errors="coerce")
        return df[(timestamps >= week_start) & (timestamps < week_end)].copy()

    if selected_ward and selected_ward.get("ward"):
        ward = str(selected_ward["ward"])
        selected_df = selected_df[selected_df["reported_location"].fillna("").astype(str) == ward]

    if selected_incident_type and selected_incident_type.get("incident_type"):
        if "incident_type_name" in selected_df.columns:
            # Resolve the clicked bar through the same helpers the chart uses, so
            # the rows shown here always match the count the bar reported.
            incident_names = normalize_incident_type_names(selected_df["incident_type_name"])
            clicked_incidents = incident_types_for_label(
                selected_incident_type["incident_type"],
                incident_types if incident_types is not None else incident_names.unique().tolist(),
            )
            selected_df = selected_df[incident_names.isin(clicked_incidents)].copy()

    if selected_champion:
        selected_df = champion_submissions(
            selected_df,
            ward=selected_champion.get("ward"),
            champion=selected_champion.get("champion"),
        )

    if selected_week:
        selected_df = _filter_by_week(selected_df, selected_week.get("week"))

    if selected_week_channel:
        selected_df = _filter_by_week(selected_df, selected_week_channel.get("week"))

        channel = selected_week_channel.get("channel", "unknown")
        if channel != "unknown":
            selected_df = selected_df[selected_df["submitter"].map(_submission_channel) == channel].copy()

    return selected_df


@st.cache_data(ttl=900)
def load_dashboard_data():
    """Load normalized dashboard data from the NBD API where available."""
    config = load_api_config()

    champions_df = pd.DataFrame()
    submissions_df = pd.DataFrame()
    boundaries_df = build_boundary_frame([])
    champions_summary = _empty_statistics()
    submissions_summary = _empty_statistics()
    error_message = None

    if not config["configured"]:
        return {
            "config": config,
            "error": "NBD API secrets have not been configured yet.",
            "champions": champions_df,
            "submissions": submissions_df,
            "boundaries": boundaries_df,
            "champions_summary": champions_summary,
            "submissions_summary": submissions_summary,
            "loaded_at": pd.Timestamp.now(tz="UTC"),
        }

    if config.get("token_configured"):
        try:
            champion_records = fetch_records(
                "api/v1/users",
                api_url=config["NBD_API_URL"],
                api_token=config["NBD_API_TOKEN"],
            )
            champions_df, champions_summary = build_dataset(champion_records, key_field="champion_id")
        except Exception as exc:
            error_message = f"Unable to load champion data: {exc}"
    else:
        champions_df = pd.DataFrame()
        champions_summary = _empty_statistics()

    try:
        submission_records = fetch_records(
            "api/v1/submissions",
            api_url=config["NBD_API_URL"],
            api_token=config["NBD_API_TOKEN"],
        )
        filtered_submission_records = filter_pollution_reporting_records(submission_records)
        submissions_df, submissions_summary = build_dataset(filtered_submission_records, key_field="submission_id")
    except Exception as exc:
        error_message = f"{error_message or ''} Unable to load submission data: {exc}".strip()

    try:
        boundary_records = fetch_reference_records(
            SUB_COUNTIES_ENDPOINT,
            api_url=config["NBD_API_URL"],
            api_token=config["NBD_API_TOKEN"],
        )
        boundaries_df = build_boundary_frame(boundary_records)
    except Exception as exc:
        error_message = f"{error_message or ''} Unable to load the county reference list: {exc}".strip()

    # Submissions only name the place they were reported from, and champions
    # only name their ward, so the reference hierarchy supplies the county.
    submissions_df = annotate_spatial_columns(submissions_df, boundaries_df)
    champions_df = annotate_spatial_columns(champions_df, boundaries_df, location_column="ward")

    return {
        "config": config,
        "error": error_message,
        "champions": champions_df,
        "submissions": submissions_df,
        "boundaries": boundaries_df,
        "champions_summary": champions_summary,
        "submissions_summary": submissions_summary,
        "loaded_at": pd.Timestamp.now(tz="UTC"),
    }


st.title("NBD Pollution Reporting Summary")

weekly_submissions_chart = None

with st.spinner("Loading dashboard data..."):
    dashboard_data = load_dashboard_data()

if dashboard_data["error"]:
    st.warning(dashboard_data["error"])

st.caption(
    f"Phase 4 dashboard data loaded at {dashboard_data['loaded_at'].strftime('%Y-%m-%d %H:%M:%S UTC')}"
)

boundaries = dashboard_data["boundaries"]
champions = dashboard_data["champions"]
submissions = dashboard_data["submissions"]

with st.sidebar:
    st.header("Filters")

    selected_basin = st.selectbox(
        "Basin",
        select_options([], _observed_values(submissions, "basin_name")),
    )
    basin = _selection(selected_basin)

    basin_scope = apply_filters(submissions, {"basin_name": basin})

    selected_county = st.selectbox(
        "County",
        select_options(
            county_names(boundaries),
            [*_observed_values(basin_scope, "county"), *_observed_values(champions, "county")],
        ),
    )
    county = _selection(selected_county)

    county_scope = apply_filters(basin_scope, {"county": county})

    selected_sub_county = st.selectbox(
        "Sub-county",
        select_options(
            sub_county_names(boundaries, county=county),
            _observed_values(county_scope, "sub_county"),
        ),
    )
    sub_county = _selection(selected_sub_county)

    sub_county_scope = apply_filters(county_scope, {"sub_county": sub_county})

    selected_ward = st.selectbox(
        "Ward",
        select_options(
            ward_names(boundaries, county=county, sub_county=sub_county),
            _observed_values(sub_county_scope, "ward", "reported_location"),
        ),
    )
    ward = _selection(selected_ward)

    if st.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()

geography_filters = {
    "basin_name": basin,
    "county": county,
    "sub_county": sub_county,
    "ward": ward,
}

filtered_submissions = apply_filters(submissions, geography_filters)
valid_submissions = (
    filtered_submissions.dropna(subset=["submitted_at"]).copy()
    if "submitted_at" in filtered_submissions.columns
    else filtered_submissions.copy()
)

ward_champions_df = ward_champions(filtered_submissions)
weekly_submissions_df = weekly_submissions(valid_submissions)
weekly_submissions_by_channel_df = weekly_submissions_by_channel(valid_submissions)
submissions_by_ward_df = submissions_by_ward(valid_submissions)
submissions_by_incident_type_df = submissions_by_incident_type(valid_submissions)
# Hues are assigned from the unfiltered incident list so that narrowing the
# filters never repaints the incidents that remain on screen.
all_incident_types = submissions_by_incident_type(submissions)["incident_type"].tolist()
cumulative_submissions_df = cumulative_submissions(valid_submissions)

current_week_count = int(weekly_submissions_df.iloc[-1]["submissions"]) if not weekly_submissions_df.empty else 0
current_week_change = _week_over_week_change(weekly_submissions_df)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Submitters", distinct_submitters(filtered_submissions))

with col2:
    if "reported_location" in filtered_submissions.columns:
        active_locations = int(filtered_submissions["reported_location"].dropna().astype(str).nunique())
    else:
        active_locations = 0
    st.metric("Active locations", active_locations)

with col3:
    st.metric("Total submissions", len(valid_submissions))

with col4:
    if current_week_change is None:
        st.metric("Current week", current_week_count)
    else:
        st.metric("Current week", current_week_count, f"{current_week_change:+.2f}% vs previous week")

st.subheader("Weekly submission rate")
if valid_submissions.empty:
    st.write("No weekly submission data available for the selected filters.")
else:
    weekly_submissions_chart = st.plotly_chart(
        build_weekly_submissions_chart(weekly_submissions_df),
        on_select="rerun",
        key="weekly_submissions_chart",
        selection_mode="points",
        use_container_width=True,
    )

weekly_channel_chart = st.plotly_chart(
    build_weekly_submissions_by_channel_chart(weekly_submissions_by_channel_df),
    on_select="rerun",
    key="weekly_channel_chart",
    selection_mode="points",
    use_container_width=True,
)
ward_chart = st.plotly_chart(
    build_submissions_by_ward_chart(submissions_by_ward_df),
    on_select="rerun",
    key="ward_chart",
    selection_mode="points",
    use_container_width=True,
)

incident_type_chart = st.plotly_chart(
    build_submissions_by_incident_type_chart(
        submissions_by_incident_type_df,
        all_incident_types,
        theme=_active_theme(),
    ),
    on_select="rerun",
    key="incident_type_chart",
    selection_mode="points",
    use_container_width=True,
)

st.subheader("Champions per ward")
st.caption("The champion of a ward is the person with the most approved reports there.")
champion_chart = None
if ward_champions_df.empty:
    st.write("No champions available for the selected filters.")
else:
    champion_chart = st.plotly_chart(
        build_ward_champions_chart(ward_champions_df),
        on_select="rerun",
        key="champion_chart",
        selection_mode="points",
        use_container_width=True,
    )

selected_week_channel = _extract_weekly_channel_selection(weekly_channel_chart)
selected_ward_selection = _extract_ward_selection(ward_chart)
selected_week = _extract_week_selection(weekly_submissions_chart)
selected_incident_type = _extract_incident_type_selection(incident_type_chart)
selected_champion = _extract_champion_selection(champion_chart)
selected_submissions = _filter_selected_submissions(
    filtered_submissions,
    selected_week=selected_week,
    selected_week_channel=selected_week_channel,
    selected_ward=selected_ward_selection,
    selected_incident_type=selected_incident_type,
    selected_champion=selected_champion,
    incident_types=all_incident_types,
)

st.subheader("Cumulative submissions")
if valid_submissions.empty:
    st.write("No valid submissions available for the selected filters.")
else:
    st.plotly_chart(
        build_cumulative_submissions_chart(cumulative_submissions_df),
        use_container_width=True,
    )

st.subheader("Submissions")
if (
    selected_week
    or selected_week_channel
    or selected_ward_selection
    or selected_incident_type
    or selected_champion
):
    if selected_submissions.empty:
        st.write("No submissions match the selected chart item.")
    else:
        selected_columns = [
            "id",
            "created_at",
            "reported_location",
            "submitter",
            "status",
            "incident_type_name",
            "basin_name",
            "wetland_name",
            "site_name",
        ]
        display_columns = [column for column in selected_columns if column in selected_submissions.columns]
        st.dataframe(
            selected_submissions[display_columns],
            use_container_width=True,
            hide_index=True,
        )
        csv_download = selected_submissions[display_columns].to_csv(index=False)
        st.download_button(
            label="Export CSV",
            data=csv_download,
            file_name="submissions.csv",
            mime="text/csv",
        )
else:
    st.write("Click a chart item to inspect the underlying submissions.")
