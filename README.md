# NBD Dashboard

A Streamlit dashboard for exploring NBD programme performance at county and ward level using public pollution-reporting submissions.

## Features

- Public-mode dashboard that reads from the NBD API without login or token requirements
- Focused on the Pollution Reporting Form only
- Uses approved submissions only and removes repeated API rows returned for the same submission
- Shows KPI cards, weekly trends, cumulative submissions, champions by ward, channel breakdown, and ward breakdown
- Supports interactive chart drilldown so clicking a chart item reveals the underlying submissions in a table
- Cascading basin, county, sub-county and ward filters built from the public spatial reference list

## Project structure

- `app.py` — Streamlit application entry point
- `src/api.py` — API client and authentication helpers
- `src/spatial.py` — Spatial reference hierarchy (region → county → sub-county → ward)
- `src/filters.py` — Sidebar filter helpers
- `src/transforms.py` — Data cleaning and dataframe preparation
- `src/metrics.py` — KPI and metric calculations
- `src/charts.py` — Plotly chart builders
- `tests/` — pytest coverage for the data layer and metrics

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Add local secrets:

   ```toml
   NBD_API_URL = "https://nbd.akvo.org"
   # Optional: only needed for protected endpoints such as users/champions
   NBD_API_TOKEN = ""
   ```

   Save this in `.streamlit/secrets.toml`.

   The dashboard runs in public mode by default. When `NBD_API_TOKEN` is empty, it loads the public submissions endpoint and skips the protected users/champions request.

4. Run the app:

   ```bash
   streamlit run app.py
   ```

