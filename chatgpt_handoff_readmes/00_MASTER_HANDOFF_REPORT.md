# Sentinel Atlas Master Handoff Report

Generated: 2026-04-25 18:19:09 -04:00

## Overall Verdict

Partial pass against the target product.

The current repo builds and tests successfully. It now reflects the country-first public-health data aggregation direction: large MapLibre world map, three-section navigation, country-centered Sources, uploaded/real-only Time Series behavior, optional backend scaffold, and aggregate-only safety constraints.

The main remaining verification gap is runtime browser interaction. The in-app browser/Node REPL path is still blocked by `Access is denied`, so live click/hover/zoom/pan checks could not be completed in-browser during this pass. The preview server did respond with HTTP 200, and static/source checks did not find removed simulator concepts in production source files.

## Handoff Files Read

I read the full `chatgpt_handoff_readmes/` package:

- `README.md`
- `01_PROJECT_README.md`
- `02_DEVELOPER_README.md`
- `03_BACKEND_README.md`
- `04_BACKEND_ARCHITECTURE.md`
- `05_FRONTEND_BACKEND_CONTRACT.md`
- `06_NEXT_CODEX_PROMPT_TASKS.md`
- `07_VERIFICATION_REPORT.md`

I also inspected current project files needed to verify the handoff against code:

- `package.json`
- `vite.config.ts`
- `.github/workflows/deploy.yml`
- `src/`
- `backend/`
- `backend/pyproject.toml`

## Current Product Features

### World Dashboard

- Opens to the `world` view by default.
- Uses `MapLibre GL JS` as the primary map implementation.
- Uses `world-atlas` country boundaries as a clickable GeoJSON overlay.
- Uses ISO numeric to ISO3 conversion for stable country joins.
- Defaults selected country to United States / `USA`.
- Supports country click selection without changing the current view.
- Supports hover country state.
- Triggers placeholder country-news loading on selected or hovered country.
- Supports zoom, pan, MapLibre navigation controls, and a `Reset view` button.
- Uses red only as selected-country styling, not risk shading.
- Has local fallback style support for restricted/offline map style loading.

Key files:

- `src/components/Map/WorldMap.tsx`
- `src/components/Map/mapConfig.ts`
- `src/components/Map/countrySelectionLayer.ts`
- `src/utils/countryCodes.ts`
- `src/state/DashboardContext.tsx`

### Navigation

Primary navigation has exactly three items:

1. World Dashboard
2. Sources
3. Time Series

No country selector dropdown exists in the inspected app code.

Key files:

- `src/components/Navigation/SideNav.tsx`
- `src/components/Layout/DashboardShell.tsx`
- `src/types/dashboard.ts`

### Sources

- Sources page requires a selected country.
- Registry entries are filtered by selected country ISO3.
- `GLOBAL` sources are treated as candidate/relevant for selected countries.
- Sources are grouped by:
  - Pathogen surveillance
  - Wastewater
  - Forecasts / nowcasts
  - Mobility / air travel
  - Ports / maritime / cargo
  - Population / demographics
  - Open-source news / event surveillance
  - User-added sources
- Coverage matrix is focused on the selected country.
- User can add source metadata locally.
- User-added sources persist in `localStorage`.
- User-added sources are labeled unvalidated/not validated.
- Validation rejects likely PII, medical-record, and individual-level terms.
- Operational trace-level terms produce warnings and must be aggregated before display.

Key files:

- `src/components/Sources/SourcesPage.tsx`
- `src/components/Sources/AddSourceModal.tsx`
- `src/components/Sources/SourceCoverageMatrix.tsx`
- `src/components/Sources/SourceCard.tsx`
- `src/data/sources/sourceCatalog.ts`
- `src/data/sources/sourceCategories.ts`
- `src/data/adapters/sourceRegistryAdapter.ts`
- `src/types/source.ts`

### Source Catalog

Current built-in catalog includes the required source families:

- WastewaterSCAN
- CDC FluSight current-week visualization
- CDC FluSight Forecast Hub
- Reich Lab FluSight dashboard
- CDC NWSS / wastewater program
- WHO FluNet
- OpenSky Network
- OurAirports
- IMF PortWatch / UN AIS-derived port activity
- NGA World Port Index
- USACE WCSC Navigation Facilities
- NOAA / BOEM Marine Cadastre AIS Vessel Traffic
- MARAD / BTS / USACE NTAD Principal Ports
- UNECE UN/LOCODE
- Future teammate-provided wastewater dataset
- Future teammate-provided mobility dataset
- Future teammate-provided ferry/cargo dataset
- Future teammate-provided population-density dataset
- Future country news / event surveillance backend

Catalog entries are metadata only. They do not imply live ingestion or current validated data availability.

### Time Series

- Time Series page requires selected country.
- If no country is selected, it tells the user to select a country on the map first.
- Source and metric controls are derived from uploaded/local records, not registry metadata alone.
- Supports uploaded CSV and JSON records.
- Filters records by selected country, source, metric, and date range.
- Supports date ranges:
  - 2 weeks
  - 1 month
  - 3 months
  - 6 months
  - 1 year
  - 2 years
- Shows clean empty states when no records exist.
- Does not generate values to fill gaps.
- Displays chart/table only when valid matching records exist.
- Upload validation rejects invalid files and likely PII or precise personal trace fields.

Required minimum upload fields:

- `date`
- `value`
- `metric`
- `countryIso3` or country name that maps to ISO3

Optional normalized fields:

- `sourceId`
- `unit`
- `locationName`
- `latitude`
- `longitude`
- `admin1`
- `admin2`
- `provenance`
- `notes`

Key files:

- `src/components/TimeSeries/TimeSeriesPage.tsx`
- `src/components/TimeSeries/TimeSeriesControls.tsx`
- `src/components/TimeSeries/UploadDatasetPanel.tsx`
- `src/components/TimeSeries/TimeSeriesChart.tsx`
- `src/data/adapters/timeSeriesUploadAdapter.ts`
- `src/data/adapters/timeSeriesAvailabilityAdapter.ts`
- `src/utils/dateRange.ts`
- `src/types/timeseries.ts`

### News / Hover Placeholder

- Frontend does not scrape websites.
- `countryNewsAdapter` returns a ready empty state with no items.
- Future endpoint contract is `GET /api/countries/:iso3/news/latest`.
- Empty/news-not-connected behavior is intentional until a backend is connected.

Key files:

- `src/data/adapters/countryNewsAdapter.ts`
- `src/types/news.ts`
- `backend/app/api/news.py`

### Theme

- Current theme is black, white, gray, and deep red accent.
- Old neon/cyan/magenta/amber product theme is not present in active frontend code.
- Docs mention those colors only as styles to avoid.

## Current Technical Methods

### App State Methods

`src/state/DashboardContext.tsx`

- `DEFAULT_SELECTED_COUNTRY`: default `USA` selected-country object.
- `applyCountrySelection(currentView, country)`: updates selected country while preserving current view.
- `DashboardProvider`: owns app state for view, selected country, hover country, sources, uploads, active source/metric/date range, and news summaries.
- `setSelectedCountry`: applies country selection and loads placeholder news for that country.
- `setHoverCountry`: tracks hover state and loads placeholder news for hovered country.
- `addUserSource`: validates, persists, and activates a user-added source.
- `addUploadedDataset`: persists uploaded datasets and selects first source/metric.
- `useDashboard`: context accessor.

### Map Methods

`src/components/Map/countrySelectionLayer.ts`

- `buildCountrySelectionGeoJson(coverageCounts)`: converts world-atlas TopoJSON countries into GeoJSON features with `iso3`, ISO numeric code, display name, and source coverage count.

`src/components/Map/WorldMap.tsx`

- Initializes MapLibre with `mapConfig.styleUrl`.
- Adds navigation control.
- Installs country fill, hover-line, selected-fill, and selected-line layers.
- Attaches mousemove, mouseleave, and click handlers to `sentinel-country-fill`.
- Updates selected-country filter when `selectedCountry.iso3` changes.
- Updates GeoJSON source when coverage counts change.
- Applies fallback style if external style loading stalls.
- Provides `resetMap()` through the Reset view button.

`src/components/Map/mapConfig.ts`

- `DEFAULT_MAP_STYLE_URL`: `https://tiles.openfreemap.org/styles/positron`.
- `VITE_MAP_STYLE_URL`: environment override.
- `fallbackBoundaryStyle`: local fallback style object.

### Country Code Methods

`src/utils/countryCodes.ts`

- `isoNumericToIso3`
- `iso3ToIsoNumeric`
- `iso3ToCountryName`
- `normalizeIso3`
- `countryNameToIso3`
- `getCountryReferenceFromNumeric`

These methods keep map/source/time-series joins on stable ISO3 values.

### Source Registry Methods

`src/data/adapters/sourceRegistryAdapter.ts`

- `validateSourceInput(input)`: validates required fields, URL shape, country coverage, aggregate-only language, and sensitive terms.
- `normalizeCoverageCountries(rawCountries)`: maps ISO aliases/country names to ISO3 and preserves `GLOBAL`.
- `createUserSource(input)`: creates a local unvalidated source metadata object.
- `sourceRegistryAdapter.listBaseSources()`
- `sourceRegistryAdapter.loadUserSources()`
- `sourceRegistryAdapter.saveUserSources(sources)`
- `sourceRegistryAdapter.listAllSources()`
- `sourceRegistryAdapter.addUserSource(input)`
- `sourceRegistryAdapter.getSnapshot()`
- `sourceRegistryAdapter.removeUserSource(sourceId)`
- `sourceRegistryAdapter.clearUserSources()`
- `validateUserSourceInput(input)`
- `createUserSourceMetadata(input, existingSources)`
- `sourceSupportsCountry(source, iso3)`
- `getSourcesForCountry(sources, iso3)`

Persistence key:

- `sentinel-atlas:user-sources`

### Time-Series Methods

`src/data/adapters/timeSeriesUploadAdapter.ts`

- `normalizeUploadedTimeSeries(text, fileName, fallbackSourceId)`: current UI upload path for CSV/JSON into `TimeSeriesRecord[]`.
- `normalizeTimeSeriesUpload(input)`: richer aggregate normalization path that produces an `AggregateTimeSeriesDataset`.
- `saveTimeSeriesDataset(dataset)`
- `loadPersistedTimeSeriesDataset()`
- `clearPersistedTimeSeriesDataset()`
- `timeSeriesUploadAdapter.createDataset(...)`
- `timeSeriesUploadAdapter.loadDatasets()`
- `timeSeriesUploadAdapter.saveDatasets(...)`

Persistence keys:

- `sentinel-atlas:uploaded-datasets`
- `sentinel-atlas:uploaded-time-series`

`src/data/adapters/timeSeriesAvailabilityAdapter.ts`

- `getUploadedDatasetRecords(datasets)`
- `getPersistedAggregateRecords(dataset)`
- `normalizeBackendTimeSeriesRecord(record)`
- `deriveAvailableTimeSeriesOptions(records, countryIso3, sourceNames, provenance)`
- `getTimeSeriesRecordsForSelection(selection)`
- `getLocalTimeSeriesAvailability(countryIso3, uploadedDatasets)`
- `getAvailableTimeSeriesForCountry(countryIso3, options)`

Backend integration flag:

- `includeBackend`

Backend base URL env var:

- `VITE_SENTINEL_API_BASE_URL`

`src/utils/dateRange.ts`

- `getDateRangeBounds`
- `filterRecordsByDateRange`
- `normalizeDateInput`
- `compareIsoDates`
- `getAggregateRecordDateRange`
- `isDateInAggregateRange`
- `filterAggregateRecordsByDateRange`
- `sortAggregateRecordsByDate`

### Backend Methods And Contracts

Backend stack:

- FastAPI
- SQLAlchemy
- SQLite local fallback
- Postgres/PostGIS-ready `SENTINEL_DATABASE_URL`
- Alembic scaffold
- Pydantic schemas
- Connector placeholders

Entrypoint:

- `backend/app/main.py`

Routers:

- `backend/app/api/countries.py`
- `backend/app/api/sources.py`
- `backend/app/api/timeseries.py`
- `backend/app/api/locations.py`
- `backend/app/api/news.py`
- `backend/app/api/model_runs.py`

Core backend endpoints:

- `GET /health`
- `GET /api/countries`
- `GET /api/countries/{iso3}`
- `GET /api/countries/{iso3}/coverage`
- `GET /api/countries/{iso3}/sources`
- `GET /api/countries/{iso3}/timeseries/available`
- `GET /api/countries/{iso3}/data-quality`
- `GET /api/countries/{iso3}/features`
- `GET /api/countries/{iso3}/model-readiness`
- `GET /api/sources`
- `GET /api/sources/{sourceId}`
- `POST /api/sources`
- `PATCH /api/sources/{sourceId}`
- `GET /api/sources/{sourceId}/coverage`
- `POST /api/sources/{sourceId}/validate`
- `GET /api/timeseries`
- `GET /api/timeseries/available`
- `POST /api/timeseries/upload`
- `GET /api/metrics`
- `GET /api/locations`
- `GET /api/ports`
- `GET /api/airports`
- `GET /api/wastewater-sites`
- `GET /api/countries/{iso3}/news/latest`
- `POST /api/ingest/news`
- `GET /api/news`
- `POST /api/model-runs/preview`
- `POST /api/model-runs`
- `GET /api/model-runs/{id}`

Backend services:

- `SourceRegistry`
- `normalize_time_series_records`
- `parse_csv_observations`
- `normalize_observation_record`
- `get_timeseries_availability`
- `assess_data_quality`
- `assess_feature_availability`
- `evaluate_model_eligibility`

Backend safety behavior:

- Rejects individual identifiers and operational trace fields in uploads.
- Returns missingness and `insufficient_data` instead of fabricated model outputs.
- Uses placeholder connector metadata without fabricating live observations.

## Commands Run

### Plain npm Check

```powershell
npm --version
```

Result: failed in this PowerShell environment.

Reason: `npm` is not on `PATH`.

### Frontend Tests

```powershell
$nodeDir = 'C:\Users\ASUS\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin'; $env:PATH = "$nodeDir;$env:PATH"; & (Join-Path $nodeDir 'node.exe') 'C:\Users\ASUS\Desktop\Vidur\CriticalOps\.codex-tools\npm\bin\npm-cli.js' test
```

Result: passed.

- Vitest: v2.1.9
- Test files: 9 passed
- Tests: 35 passed
- Duration: 5.57s

### Frontend Build

```powershell
$nodeDir = 'C:\Users\ASUS\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin'; $env:PATH = "$nodeDir;$env:PATH"; & (Join-Path $nodeDir 'node.exe') 'C:\Users\ASUS\Desktop\Vidur\CriticalOps\.codex-tools\npm\bin\npm-cli.js' run build
```

Result: passed.

Build output:

- `dist/index.html`: 0.68 kB, gzip 0.41 kB
- `dist/assets/index-2ciZWtzK.css`: 90.39 kB, gzip 14.37 kB
- `dist/assets/index-Cd291kYq.js`: 2,437.90 kB, gzip 704.79 kB
- Build duration: 13.83s

Warning remains:

- Some chunks are larger than 500 kB after minification.

### Backend Tests

```powershell
& 'C:\Users\ASUS\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest
```

Working directory:

```text
C:\Users\ASUS\Desktop\Apart AixBio\backend
```

Result: passed.

- Python: 3.12.13
- Pytest: 9.0.3
- Tests: 19 passed
- Duration: 2.94s

### Preview Smoke Check

```powershell
Invoke-WebRequest -UseBasicParsing 'http://localhost:4174/' | Select-Object StatusCode,Content
```

Result: passed.

- HTTP status: 200

### Browser Smoke Attempt

Attempted in-app browser runtime via Browser Use / Node REPL.

Result: failed.

```text
failed to execute Node: Access is denied. (os error 5)
```

Impact: manual browser verification of map click/hover/zoom/pan remains unverified in this environment.

### Static Removed-Term Scan

Command:

```powershell
Get-ChildItem -Recurse -File -LiteralPath '.\src' | Select-String -Pattern 'synthetic|scenario|R0|\bRt\b|risk score|outbreak forecast|pathogen mode|country selector|fake' -CaseSensitive:$false
```

Result:

- Matches appeared only in tests that assert removed UI is absent.

Additional docs scan:

- README and developer docs contain removed simulator terms only as removed-history or explicit "do not reintroduce" guidance.

Built bundle scan note:

- The minified JS bundle contains short-token false positives such as `R0`, `Rt`, and `fake` from bundled/minified library code.
- Production source scan excluding tests did not identify user-facing synthetic simulator copy.

### Git Status

```powershell
git status --short
```

Result: failed.

Reason: this workspace is not a Git repository.

## Test Coverage Summary

Frontend tests currently cover:

- Dashboard view type shape and legacy overview removal.
- Default selected country.
- Country selection state preserving view.
- Navigation limited to three items.
- No country selector dropdown contract in map/shell source.
- Removed simulator/fake-risk terms absent from visible component source.
- Source filtering by ISO3 and `GLOBAL`.
- Country name/alias normalization.
- Source validation rejecting individual/medical-record content.
- User-added source persistence and unvalidated labeling.
- Source catalog categories and required entries.
- Built-in source entries aggregate-only.
- Time-series upload normalization for valid CSV and JSON.
- Upload validation errors instead of filling missing values.
- PII/medical-record/precise trace field rejection.
- Time-series availability from actual uploaded records.
- Filtering by selected country/source/metric/date range.
- No leakage from other countries.
- Empty availability when no real records exist.
- Future backend record shape normalization.
- Map country joins through ISO numeric to ISO3.

Backend tests currently cover:

- Source registry placeholder metadata.
- Source create/patch.
- Time-series availability empty state.
- Availability summaries from uploaded observations.
- Availability alias endpoint.
- Country isolation for availability.
- Fetch filters matching availability options.
- Invalid ISO3 validation.
- Upload rejection of operational trace fields.
- USA default empty endpoints.
- Model preview refusing to fabricate without data.
- Model run using uploaded wastewater only for limited trend summary.
- CSV upload normalization into aggregate rows.
- Upload rejection of individual identifiers.
- Feature availability missingness and uploaded signals.
- Hover news empty endpoint.
- Data-quality score bounds.
- Recency degradation for stale data.
- Quality report avoiding prediction claims.

## Current Failures And Gaps

### Blocking

None found in build or tests.

### High

1. Browser interaction verification is blocked.
   - Area: runtime smoke testing.
   - Failure: Node REPL/browser runtime returns `Access is denied`.
   - Impact: live verification of map click, hover, zoom, pan, reset, and UI console logs could not be completed in this environment.
   - Status: not fixed.

2. No automated browser/E2E smoke test suite exists.
   - Area: test coverage.
   - Impact: map and navigation regressions are not covered through a real browser runner.
   - Status: next task already documented in `06_NEXT_CODEX_PROMPT_TASKS.md`.

### Medium

1. Main frontend bundle is large.
   - Area: build output.
   - Current JS: 2,437.90 kB minified, 704.79 kB gzip.
   - Impact: Vite emits chunk warning over 500 kB.
   - Likely cause: MapLibre, world-atlas, Recharts, and app code bundled together.
   - Status: not fixed.

2. Frontend/backend adapter contracts exist but are not fully integrated.
   - Area: `timeSeriesAvailabilityAdapter`, `countryNewsAdapter`, backend docs/routes.
   - Impact: frontend still primarily uses localStorage/local adapters. Backend integration is ready conceptually but not connected by default.
   - Status: expected scaffold gap.

3. Time-series persistence has two compatibility keys.
   - Area: upload/local persistence.
   - Keys: `sentinel-atlas:uploaded-datasets` and `sentinel-atlas:uploaded-time-series`.
   - Impact: docs note these should be reconciled into one server-backed dataset model later.
   - Status: not fixed.

4. Add-source and time-series upload workflows lack UI-level tests.
   - Area: frontend tests.
   - Impact: adapters are covered, but modal/file-upload behavior is not tested through rendered UI.
   - Status: next tasks documented.

### Low

1. Plain `npm` is not on PATH in this Codex PowerShell environment.
   - Area: local environment.
   - Impact: normal `npm test`/`npm run build` commands fail unless bundled Node/npm path is used.
   - Status: environment-specific.

2. No separate `lint` or `typecheck` scripts exist in `package.json`.
   - Area: project scripts.
   - Impact: type checking runs through `npm run build` via `tsc -b`, but there is no standalone lint/typecheck command.
   - Status: not fixed.

3. Workspace is not a Git repository.
   - Area: project metadata.
   - Impact: cannot produce git status/diff from this directory.
   - Status: environment/project-copy condition.

## Data Integrity Review

Confirmed current design:

- Does not fabricate time-series records.
- Does not display fake predictions.
- Does not show fake pathogen risk scores.
- Does not expose fake Rt/R0 user-facing metrics.
- Does not show synthetic outbreak simulation controls.
- Does not use country-level fake risk shading.
- Uses empty states when records/news are unavailable.
- Source catalog entries are metadata and adapter-readiness notes, not claims of live data.
- Time Series controls come from actual uploaded/local records.
- Backend model readiness returns `insufficient_data` when missing data prevents output.

## Safety And Privacy Review

Confirmed current design:

- App is framed as aggregate-only.
- User-added sources are marked not validated/unvalidated.
- Source validation rejects likely PII, individual-level, patient, medical-record, SSN, phone, email, device ID, precise GPS, personal mobility, and trace-level terms.
- Time-series uploads reject likely PII, medical-record, individual identifier, and precise personal trace fields.
- Backend upload tests cover rejection of individual identifiers and operational trace fields.
- No workflow asks for individual medical records.
- No workflow provides medical advice, diagnosis, public-alert instructions, wet-lab guidance, pathogen engineering guidance, evasion guidance, or dissemination guidance.

Residual risk:

- Future adapters for aviation/maritime/news must preserve aggregation and provenance rules before exposing data to the frontend.
- Future backend model endpoints must keep refusing fabricated outputs when required signals are missing.

## Backend Readiness

The backend scaffold is materially useful but not production-complete.

Ready now:

- FastAPI app boots with registered routers.
- SQLite local fallback.
- SQLAlchemy models.
- Source connector registry placeholders.
- Country/source coverage endpoints.
- Time-series upload and normalization path.
- Time-series availability endpoint.
- News endpoint with empty state support.
- Feature availability and data-quality services.
- Cautious model-readiness and model-run endpoints.
- Tests pass.

Not ready yet:

- Live source ingestion.
- Production auth.
- Production migrations and geospatial indexes.
- PostGIS/TimescaleDB deployment hardening.
- News scraper implementation.
- Persistent team/user source management.
- Frontend default backend connection.

## Deployment Readiness

Current static deployment workflow:

- `.github/workflows/deploy.yml`
- Runs `npm ci`
- Runs `npm run test`
- Runs `npm run build`
- Uploads `dist/`
- Deploys GitHub Pages

Gap:

- Backend pytest is not part of the current GitHub Pages workflow.
- Browser smoke tests are not configured.

## Recommended Next Tasks

1. Add automated runtime/browser smoke coverage for map, navigation, removed UI terms, and no country selector.
2. Reduce frontend bundle size through code-splitting MapLibre/world-atlas/Recharts or manual chunks.
3. Add fuller typed frontend backend adapter contracts while keeping local fallback behavior.
4. Add UI-level tests for Add Source modal validation, save, unvalidated label, and persistence.
5. Add UI-level tests for Time Series upload, filtering, validation errors, PII rejection, and all date ranges.
6. Improve country hover/news adapter UX with compact loading/error/empty states and no fake headlines.
7. Align backend API contract naming and schemas with frontend types.
8. Clean up docs with a short PR verification checklist and normal-environment command notes.
9. Verify map fallback behavior when remote basemap tiles are unavailable.
10. Expand CI to run any new browser smoke tests and optionally backend pytest.

## Best Next Prompt For ChatGPT

Use this report plus `06_NEXT_CODEX_PROMPT_TASKS.md` to generate standalone Codex prompts. Each prompt should:

- Target exactly one task.
- Tell Codex to inspect relevant files before editing.
- Preserve aggregate-only safety constraints.
- Forbid fake public-health data, fake prediction, fake risk, fake Rt/R0, and synthetic simulator UI.
- Keep navigation to World Dashboard, Sources, Time Series.
- Keep country selection on the map, not a dropdown.
- Include exact acceptance criteria.
- Include commands to run and expected reporting format.

