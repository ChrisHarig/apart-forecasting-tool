# Sentinel Atlas

Sentinel Atlas is now a country-first public-health data aggregation dashboard. The app centers on a large interactive world map: analysts click a country to select it in place, inspect available source metadata for that country, and upload aggregate CSV/JSON time-series records when data exists.

The frontend still works as a local-only Vite app, and `backend/` now contains a first-pass FastAPI scaffold for future aggregate data ingestion, source availability, data quality, and cautious model-readiness APIs. There is still no live data pipeline, no scraping, and no fabricated disease or mobility data shown to users.

For the frontend/backend engineering handoff and maintenance protocol, see [DEVELOPER_README.md](DEVELOPER_README.md).

## Current Product Shape

- `World Dashboard`: large MapLibre world map with zoom, pan, reset, hover-ready state, and in-place country selection. United States is selected by default.
- `Sources`: country-centered source registry grouped by source category.
- `Time Series`: country/source/metric/date-range view for uploaded aggregate records.

The side navigation has exactly:

1. World Dashboard
2. Sources
3. Time Series

## What Changed In This Pivot

Removed from the user-facing app:

- Synthetic pathogen mode.
- Synthetic scenario controls and sliders.
- Disease-risk map shading.
- Rt-style model metrics.
- Generated historical/nowcast/forecast values.
- Fake airport, wastewater, and port markers.
- Country selector dropdown.
- Crowded three-column dashboard layout.

The app now prefers empty states and source metadata over fabricated values.

## Map

The primary map is implemented with MapLibre GL JS.

Files:

```text
src/components/Map/WorldMap.tsx
src/components/Map/mapConfig.ts
src/components/Map/countrySelectionLayer.ts
```

Map behavior:

- Uses Web Mercator through MapLibre.
- Uses OpenFreeMap as the default OpenStreetMap-based vector tile style.
- Supports `VITE_MAP_STYLE_URL` to override the style URL.
- Supports scroll-wheel zoom, drag pan, zoom buttons, and reset view.
- Overlays world-atlas country boundaries as a clickable GeoJSON layer.
- Converts country selection to ISO3 for state and source joins.
- Does not rely on fragile country-name matching.
- Highlights the selected country in red. Red means selected country, not risk.
- Clicking a country selects it in place and does not change the current view.

Default style:

```text
https://tiles.openfreemap.org/styles/positron
```

## Sources

Files:

```text
src/types/source.ts
src/data/sources/sourceCatalog.ts
src/data/sources/sourceCategories.ts
src/data/adapters/sourceRegistryAdapter.ts
src/components/Sources/
```

The source catalog preserves the original MVP sources and adds expanded port/maritime metadata. Categories include:

- Pathogen surveillance
- Wastewater
- Forecasts / nowcasts
- Mobility / air travel
- Ports / maritime / cargo
- Population / demographics
- Open-source news / event surveillance
- User-added sources

Included source families:

- WastewaterSCAN
- CDC FluSight current-week visualization
- CDC FluSight Forecast Hub
- Reich Lab FluSight dashboard
- CDC NWSS / wastewater program
- WHO FluNet
- OpenSky Network
- OurAirports
- IMF PortWatch
- NGA World Port Index
- USACE WCSC Navigation Facilities
- NOAA / BOEM Marine Cadastre AIS
- MARAD / BTS / USACE NTAD Principal Ports
- UNECE UN/LOCODE
- Future teammate-provided datasets
- Future country news backend

## Add A Source

In the Sources section, click `Add source`.

Fields:

- name
- URL
- category
- countries covered
- data type
- update cadence
- notes

User-added source metadata is persisted in `localStorage` under:

```text
sentinel-atlas:user-sources
```

User-added sources are labeled as not validated. The app rejects or warns on individual-level, PII, precise tracking, and operational trace-level terms.

## Time Series Uploads

Files:

```text
src/types/timeseries.ts
src/data/adapters/timeSeriesUploadAdapter.ts
src/components/TimeSeries/
src/utils/dateRange.ts
```

The Time Series section only renders uploaded or adapter-provided aggregate records.

Available source and metric controls are derived from actual local/uploaded records through `src/data/adapters/timeSeriesAvailabilityAdapter.ts`. Registry metadata alone does not create chartable time-series options.

Supported upload formats:

- CSV
- JSON

Required minimum normalized fields:

- `date`
- `value`
- `metric`
- `countryIso3` or a country name that can be mapped to ISO3

Optional fields:

- `sourceId`
- `unit`
- `locationName`
- `latitude`
- `longitude`
- `admin1`
- `admin2`
- `provenance`
- `notes`

Date range options:

- 2 weeks
- 1 month
- 3 months
- 6 months
- 1 year
- 2 years

If no uploaded records match the selected country/source/metric/range, the app shows an empty state.

## News Backend Placeholder

File:

```text
src/data/adapters/countryNewsAdapter.ts
```

The frontend does not scrape websites. The adapter returns an empty list until a backend endpoint is configured.

Future endpoint shape:

```text
GET /api/countries/:iso3/news/latest
```

Hover UI is ready to display country news metadata later, but currently shows:

```text
No news feed connected yet.
```

## State

File:

```text
src/state/DashboardContext.tsx
```

State now tracks:

- current view
- selected country, defaulting to United States / `USA`
- hover country
- source catalog
- user-added sources
- uploaded datasets
- active time-series source
- active metric
- active date range
- country news summaries

## Safety

Sentinel Atlas is aggregate-only.

It should not handle:

- individual-level identity data
- medical records
- diagnosis
- medical advice
- precise personal mobility traces
- operational public-alert instructions
- pathogen engineering guidance
- wet-lab guidance
- gain-of-function content
- evasion or dissemination guidance

## Run Locally

```bash
npm install
npm run dev
```

Local URL:

```text
http://localhost:5173/
```

Run tests:

```bash
npm test
```

Build:

```bash
npm run build
```

## Deployment

The Vite config uses a relative asset base for GitHub Pages.

```bash
npm run build
```

The repo includes a GitHub Pages workflow:

```text
.github/workflows/deploy.yml
```

The workflow runs `npm ci`, `npm run test`, `npm run build`, uploads `dist/`, and deploys with GitHub Pages.

## Verification

Current verification:

- `npm test` passes.
- `npm run build` succeeds.

The build still warns about large chunks because MapLibre, world-atlas, and charting libraries are bundled together. This is not a build blocker.

## Known Limitations

- Backend is a scaffold only; the frontend runs without it and no production ingestion pipeline is connected.
- No live data adapters.
- No scraper/news backend.
- No authenticated persistence.
- User-added sources and uploaded datasets use browser localStorage only.
- Uploaded file parsing is lightweight and intended for hackathon MVP use.
- Map selected-country red styling is selection-only and is not a risk layer.
- No marker clustering is currently needed because fake point overlays were removed.

## Removed Files / Surfaces

The user-facing synthetic dashboard implementation was removed or detached:

```text
src/features/syntheticScenario/
src/lib/simulation/
src/data/mock/
src/data/adapters/mock*.ts
src/components/Charts/ForecastChart.tsx
src/components/Charts/SignalOverlayChart.tsx
src/components/Panels/ControlPanel.tsx
src/components/Panels/SummaryPanel.tsx
src/components/Panels/DataSourceCatalog.tsx
```

## Future Backend Integration

Next backend-facing work:

- Implement source adapters for the registry entries.
- Add a country news endpoint.
- Store source registry and uploaded datasets server-side.
- Add provenance and data-quality metadata from real adapters.
- Add code splitting for MapLibre and source-heavy views.
