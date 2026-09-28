# NBD Dashboard

A Streamlit dashboard for exploring NBD programme performance at county and ward level using public pollution-reporting submissions.

## Features

- Public-mode dashboard that reads from the NBD API without login or token requirements
- Focused on the Pollution Reporting Form only
- Uses approved submissions only and removes repeated API rows returned for the same submission
- Cascading basin, county, sub-county and ward filters built from the public spatial reference list
- Interactive chart drilldown: clicking a chart item reveals the underlying submissions in a table, with CSV export
- Data is cached for 15 minutes, with a **Refresh data** button in the sidebar to reload on demand

### KPI cards

| Card | Meaning |
| --- | --- |
| Total Submitters | Distinct people with an approved report under the active filters |
| Active locations | Distinct reported locations |
| Total submissions | Approved submissions carrying a valid timestamp |
| Current week | This week's submissions, with the percentage change against the previous week |

### Charts

| Chart | Clickable | Notes |
| --- | --- | --- |
| Daily submissions | Yes | Daily counts from the earliest submission onwards, with quiet days carried as zero. Clicking a point filters the table to that day |
| Weekly submissions by channel | Yes | WhatsApp and USSD, inferred from the `wa-` / `ussd-` submitter prefix |
| Submissions by ward | Yes | Filters the table to the clicked ward |
| Reported incidents by type | Yes | Donut chart with the total in the hole. Fixed per-incident hues that survive filtering, chosen per light/dark theme; each slice is named where it is drawn, so identity never rests on colour alone. Incidents beyond the palette fold into a single "Other" slice that still drills down to all of them |
| Champions per ward | Yes | One bar per ward, labelled with its champion — the person with the most approved reports there. Clicking a bar lists that champion's approved reports in that ward |
| Cumulative submissions | No | Running total over time |

Champions are derived from the submissions themselves rather than the protected users endpoint, so they are available in public mode.

## Project structure

- `app.py` — Streamlit application entry point: layout, sidebar filters, chart selection handling
- `src/api.py` — API client, configuration loading and authentication helpers
- `src/spatial.py` — Spatial reference hierarchy (basin → county → sub-county → ward)
- `src/filters.py` — Sidebar filter helpers
- `src/transforms.py` — Pollution-form filtering, deduplication, cleaning and dataframe preparation
- `src/metrics.py` — KPI and metric calculations, including ward champions and the champion drilldown
- `src/charts.py` — Plotly chart builders and the incident-type colour system
- `scripts/get_nbd_session.py` — Helper for obtaining an NBD API session via the Google auth flow
- `tests/` — pytest coverage for the data layer, metrics and charts

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

   Save this in `.streamlit/secrets.toml`. Both settings are also read from the
   environment, so `NBD_API_URL` and `NBD_API_TOKEN` work as environment variables.

   The dashboard runs in public mode by default. When `NBD_API_TOKEN` is empty, it loads the public submissions endpoint and skips the protected users/champions request.

4. Run the app:

   ```bash
   streamlit run app.py
   ```

## Tests

```bash
pytest -q                                  # full suite
pytest -q --cov=src --cov-report=term-missing   # with coverage
```

The suite covers the API client, transforms, spatial hierarchy, filters, metrics and
chart builders. `src/` coverage currently sits at 91%. The coverage run needs
`pytest-cov`, which is not in `requirements.txt` — install it separately if you want it.
