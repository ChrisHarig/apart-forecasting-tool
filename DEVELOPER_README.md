# Sentinel Atlas Developer README

Last updated: 2026-04-25

This file is the engineering handoff for frontend and backend developers working on Sentinel Atlas. It should be updated whenever app behavior, data contracts, source metadata, setup steps, deployment steps, safety posture, or backend integration assumptions change.

## Product Summary

Sentinel Atlas is a country-first public-health data aggregation dashboard. Analysts start from a large interactive world map, click a country, inspect source coverage metadata, and view aggregate time-series data only when real or user-added records exist.

Current product stance:

- User-facing app is currently a Vite app with localStorage-backed MVP adapters.
- `backend/` now contains a runnable FastAPI scaffold with SQLite dev fallback, SQLAlchemy models, connector placeholders, upload normalization, readiness services, tests, and docs.
- No live data pipelines yet.
- No frontend scraping.
- No fabricated disease, outbreak, risk, Rt, synthetic scenario, airport, port, wastewater, or mobility values in the user-facing UI.
- Aggregate public-health data only.

Primary user flow:

1. Open World Dashboard.
2. Click a country on the map to select it without leaving the current view.
3. Open Sources manually to inspect source metadata for the selected country.
4. Open Time Series manually to upload or inspect aggregate CSV/JSON records for the selected country/source.

## Commands

Install dependencies:

```bash
npm install
```

Start local development:

```bash
npm run dev
```

Default local URL:

```text
http://localhost:5173/
```

Run tests:

```bash
npm test
```

Build production static assets:

```bash
npm run build
```

Preview a production build:

```bash
npm run preview
```

## Stack

- Vite
- React
- TypeScript
- Tailwind CSS
- MapLibre GL JS
- world-atlas country boundaries
- topojson-client
- i18n-iso-countries
- Recharts
- Vitest
- Browser localStorage for MVP persistence

The Vite config uses `base: "./"` so the static build is GitHub Pages compatible.

## Deployment

GitHub Pages deployment is scaffolded in:

```text
.github/workflows/deploy.yml
```

The workflow runs on pushes to `main` and on manual dispatch. It performs:

```text
npm ci
npm run test
npm run build
```

Then it uploads `dist/` with `actions/upload-pages-artifact` and deploys with `actions/deploy-pages`.

## App Structure

```text
src/App.tsx
src/main.tsx
src/state/DashboardContext.tsx
src/components/Layout/DashboardShell.tsx
src/components/Navigation/SideNav.tsx
src/components/Map/
src/components/Sources/
src/components/TimeSeries/
src/components/ui/
src/data/adapters/
src/data/sources/
src/types/
src/utils/
backend/
.github/workflows/deploy.yml
```

Key ownership boundaries:

- `src/state/DashboardContext.tsx`: app state and actions.
- `src/components/Layout/DashboardShell.tsx`: primary layout and view switching.
- `src/components/Map/`: MapLibre map, map config, country boundary GeoJSON conversion.
- `src/components/Sources/`: source registry UI, cards, coverage matrix, add-source modal.
- `src/components/TimeSeries/`: upload UI, controls, chart, table.
- `src/data/sources/`: built-in source metadata catalog and categories.
- `src/data/adapters/`: frontend adapter contracts and localStorage-backed MVP adapters.
- `src/types/`: source, time-series, news, and dashboard contracts.
- `src/utils/`: country code normalization, date filtering, localStorage helpers.
- `backend/`: FastAPI backend scaffold for source registry, aggregate observations, connector placeholders, feature availability, data quality, and cautious model readiness.
- `.github/workflows/deploy.yml`: static GitHub Pages build/deploy workflow.

## Backend Scaffold

The backend directory contains a runnable Python scaffold:

```text
backend/app/api/
backend/app/connectors/
backend/app/db/
backend/app/db/migrations/versions/
backend/app/schemas/
backend/app/services/
backend/app/tests/
backend/docs/
backend/pyproject.toml
backend/Dockerfile
backend/docker-compose.yml
```

Local backend setup:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

OpenAPI docs load at:

```text
http://127.0.0.1:8000/docs
```

Backend tests:

```bash
cd backend
pytest
```

Backend API handoff details now live in:

```text
backend/docs/frontend-contract.md
```

The pytest files in `backend/app/tests/` run against `app.main:app` and use tiny synthetic aggregate fixtures only. They do not present fixture data as production data.

## Navigation And State

The only primary views are:

```ts
type DashboardView = "world" | "sources" | "timeseries";
```

The side navigation renders exactly:

1. World Dashboard
2. Sources
3. Time Series

Country selection happens by clicking a country on the map. Do not add a country selector dropdown unless the product direction changes. United States / `USA` is selected by default on initial app load.

Current app state lives in `DashboardContext`:

- `view`
- `selectedCountry`
- `hoverCountry`
- `sources`
- `userAddedSources`
- `uploadedDatasets`
- `activeTimeSeriesSourceId`
- `activeMetric`
- `activeDateRange`
- `newsByCountry`

When `setSelectedCountry(country)` receives a country, it:

1. Stores the selected country.
2. Keeps the current view unchanged.
3. Starts the placeholder news load for that country.

## Map Implementation

Files:

```text
src/components/Map/WorldMap.tsx
src/components/Map/mapConfig.ts
src/components/Map/countrySelectionLayer.ts
```

The primary map is MapLibre GL JS using Web Mercator. It uses OpenFreeMap by default:

```text
https://tiles.openfreemap.org/styles/positron
```

Override the style URL with:

```text
VITE_MAP_STYLE_URL=<style-url>
```

The map also installs a local fallback style if the external basemap cannot load in a restricted environment. Country boundaries still render through the local world-atlas overlay, so the app remains usable even when remote map tiles fail.

Country selection is based on ISO3, not country-name matching. `countrySelectionLayer.ts` converts `world-atlas/countries-50m.json` TopoJSON into a GeoJSON layer and maps numeric country IDs to ISO3 via `src/utils/countryCodes.ts`.

Map behavior:

- Scroll-wheel zoom.
- Drag pan.
- Zoom controls.
- Reset view.
- Country hover.
- Country click selection.
- Selected-country red fill and outline.
- No permanent instructional, hover, selected-country, or basemap-warning cards over the map.

Red on the map means selected country only. It is not disease risk, outbreak risk, or forecast output. Source-coverage context may be used as restrained neutral styling, but it should not overpower the selected-country red state.

## Source Registry

Files:

```text
src/types/source.ts
src/data/sources/sourceCatalog.ts
src/data/sources/sourceCategories.ts
src/data/adapters/sourceRegistryAdapter.ts
src/components/Sources/
```

The built-in catalog is metadata only. It does not imply live ingestion, validation, or current availability for a country.

Source categories:

- `pathogen_surveillance`
- `wastewater`
- `forecasts_nowcasts`
- `mobility_air_travel`
- `ports_maritime_cargo`
- `population_demographics`
- `news_event_surveillance`
- `user_added`

Important source fields:

- `id`
- `name`
- `category`
- `description`
- `officialUrl`
- `owner`
- `geographicCoverage`
- `supportedCountries`
- `granularity`
- `temporalResolution`
- `updateCadence`
- `likelyFields`
- `fileFormats`
- `accessType`
- `licenseNotes`
- `provenanceNotes`
- `dataQualityNotes`
- `limitations`
- `adapterStatus`
- `mvpStatus`
- `countryAvailability`
- `lastVerifiedDate`
- `userAdded`

Country filtering uses `supportedCountries`. `GLOBAL` means the source is treated as potentially relevant to every selected country, but still may need country-level filtering in a real adapter.

## Add-Source Workflow

User-added source metadata is stored in localStorage under:

```text
sentinel-atlas:user-sources
```

The add-source form collects:

- name
- URL
- category
- countries covered
- data type
- update cadence
- notes

Validation lives in `sourceRegistryAdapter.ts`.

Validation rejects references to:

- individual-level data
- person-level records
- patient or medical records
- PII
- phone numbers or email addresses
- device IDs
- precise GPS
- trace-level contact tracing

Validation warns on operational detail that must be aggregated before display, such as:

- flight-level data
- vessel-level data
- vehicle-level data
- callsigns
- tail numbers
- raw trajectories

User-added sources must be labeled as not validated. Do not imply that a user-added source is official, verified, or adapter-connected.

## Time Series Uploads

Files:

```text
src/types/timeseries.ts
src/data/adapters/timeSeriesUploadAdapter.ts
src/data/adapters/timeSeriesAvailabilityAdapter.ts
src/components/TimeSeries/
src/utils/dateRange.ts
```

The Time Series view renders only uploaded or adapter-provided records. It does not fabricate values or generate fallback time-series data.

Available source and metric controls are derived from actual local/uploaded records through `timeSeriesAvailabilityAdapter.ts`. Source registry metadata does not create chartable time-series options by itself.

Current localStorage key for the active user-facing dataset flow:

```text
sentinel-atlas:uploaded-datasets
```

There is also an aggregate normalization API using:

```text
sentinel-atlas:uploaded-time-series
```

When adding backend support, reconcile these storage paths into a single server-backed dataset model.

`timeSeriesAvailabilityAdapter.ts` currently reads both local storage paths for compatibility. It can also normalize future backend rows that use either camelCase or snake_case fields such as `countryIso3` / `country_iso3`, `sourceId` / `source_id`, `observedAt` / `observed_at`, `signalCategory` / `signal_category`, and `provenanceUrl` / `provenance_url`.

Supported upload formats:

- CSV
- JSON

Minimum required normalized fields:

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

Time Series filtering depends on:

- selected country ISO3
- active source ID
- active metric
- active date range

Date range presets:

- `14d`
- `1m`
- `3m`
- `6m`
- `1y`
- `2y`
- `custom`

If no records match the selected country/source/metric/range, show an empty state. Do not invent data.

## News Backend Placeholder

Files:

```text
src/types/news.ts
src/data/adapters/countryNewsAdapter.ts
```

The frontend does not scrape websites. The current adapter returns an empty ready state.

Future endpoint shape:

```text
GET /api/countries/:iso3/news/latest
```

Expected future news item fields:

- headline
- date
- source
- country
- related signal, if available
- confidence/status
- provenance
- link, if available

Map hover UI is ready to show this metadata. If the backend is not connected, it should continue to show a clean empty state: `No news feed connected yet.`

## Backend Integration Plan

The backend should eventually provide:

- Persistent source registry storage.
- Authenticated user/team source management.
- Dataset upload storage.
- Dataset normalization and validation.
- Country-scoped time-series query endpoints.
- Source adapter jobs for public datasets.
- News/event surveillance endpoint.
- Provenance and data-quality metadata.

Recommended endpoint shapes:

```text
GET    /api/sources
POST   /api/sources
GET    /api/countries/:iso3/sources
POST   /api/datasets
GET    /api/countries/:iso3/timeseries?sourceId=&metric=&start=&end=
GET    /api/countries/:iso3/news/latest
```

Backend responses should preserve ISO3 as the primary country key.

Do not return individual-level records, raw personal mobility traces, medical records, or operational trace-level data to the frontend.

## Safety And Ethics Requirements

The product must stay aggregate-only.

Do not add:

- individual-level identity data
- medical records
- diagnosis or medical advice
- precise personal mobility traces
- operational public alert recommendations
- pathogen engineering guidance
- wet-lab guidance
- gain-of-function content
- evasion or dissemination guidance

Use cautious language:

- source coverage
- metadata
- aggregate records
- adapter status
- data quality
- provenance
- no data connected yet

Avoid certainty language and avoid claims of prediction unless backed by a real validated adapter and clearly labeled methodology.

## Styling And UX Direction

Theme:

- black
- near-black
- white
- gray
- deep red accent

Avoid:

- neon cyan
- magenta
- amber status clutter
- fake risk heatmaps
- dense three-column simulator layout

UX rules:

- Map is the focal point of World Dashboard.
- Country selection happens on the map.
- Sources and Time Series depend on selected country.
- Empty states are preferred over fake placeholders.
- Keep controls accessible with labels and visible focus states.

## Testing

Vitest config lives in `vite.config.ts`.

Current test entry:

```text
src/types/dashboard.test.ts
```

Test coverage currently focuses on:

- source filtering by selected country
- user-added source validation
- localStorage-compatible persistence behavior
- uploaded time-series normalization assumptions
- date range filtering
- no renderable data by default

When adding features, prefer small pure-function tests near adapters and utilities. Browser E2E is not configured as a formal test suite yet.

## Verification Checklist For Every Change

Run before handoff:

```bash
npm test
npm run build
```

For map or UI changes, also open the app locally and verify:

- the app loads at `http://localhost:5173/`
- side navigation has only World Dashboard, Sources, Time Series
- map displays and can zoom/pan
- United States is selected by default
- clicking a country updates selected country without changing the current view
- Sources is centered on selected country
- Time Series shows empty state when no uploaded records exist
- Time Series source and metric options appear only when uploaded/local records exist for the selected country
- no synthetic/mock/Rt/risk-score language appears in user-facing UI

Known build note:

- Vite may warn about large chunks because MapLibre, Recharts, and world-atlas are bundled. This is not currently a blocker, but future work should code-split map and chart-heavy views.

## Documentation Steward Protocol

This file is the repo's durable engineering context. Keep it updated at the end of every prompt or development task that changes behavior, structure, setup, APIs, data contracts, or limitations.

Required steward behavior:

1. Review changed files before final handoff.
2. Update `DEVELOPER_README.md` if the change affects developer understanding.
3. Update `README.md` if the user-facing project summary, commands, or deployment instructions changed.
4. Mention documentation updates in the final response.

Suggested Codex workflow:

1. At the start of a new implementation prompt, assign or spawn a documentation steward if subagents are available.
2. Keep the steward focused on documentation impact and avoid overlapping code edits.
3. Before final response, have the steward or main agent compare the final implementation against this file.
4. Apply any needed README updates before running final verification.

Current limitation:

- This repository cannot enforce a permanently running agent by itself. The protocol above is the standing instruction for future Codex work in this thread and should be followed whenever new changes are made.

## Removed User-Facing Surfaces

Do not reintroduce these unless the product direction explicitly changes:

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

The app may still use small test fixtures in clearly named test files, but no fake disease, risk, Rt, or synthetic scenario outputs should appear in the user-facing UI.

## Practical Notes For New Developers

Frontend developers should start with:

1. `src/components/Layout/DashboardShell.tsx`
2. `src/state/DashboardContext.tsx`
3. `src/components/Map/WorldMap.tsx`
4. `src/components/Sources/SourcesPage.tsx`
5. `src/components/TimeSeries/TimeSeriesPage.tsx`

Backend developers should start with:

1. `src/types/source.ts`
2. `src/types/timeseries.ts`
3. `src/types/news.ts`
4. `src/data/adapters/sourceRegistryAdapter.ts`
5. `src/data/adapters/timeSeriesUploadAdapter.ts`
6. `src/data/adapters/countryNewsAdapter.ts`

Data-source researchers should start with:

1. `src/data/sources/sourceCatalog.ts`
2. `src/data/sources/sourceCategories.ts`
3. source metadata fields in `src/types/source.ts`

When in doubt, prefer metadata, provenance, empty states, and adapter readiness notes over fabricated sample data.
