# Sentinel Atlas Backend

FastAPI backend scaffold for country-by-country public-health data readiness. It aggregates normalized, aggregate observations; records source provenance and limitations; exposes uneven data availability; and refuses to generate model outputs when required signals are missing.

This backend is not a pathogen engineering, wet-lab, gain-of-function, evasion, dissemination, or operational outbreak-action system. It accepts aggregate public-health/contextual data only.

## Architecture Summary

- FastAPI application with OpenAPI docs at `/docs`.
- SQLAlchemy ORM models with SQLite as the local development default.
- Postgres/PostGIS-ready database URL via `SENTINEL_DATABASE_URL`.
- Alembic scaffold for future migrations.
- Connector registry with metadata-only placeholders for public-health, wastewater, aviation, maritime, forecast, news, and user-upload sources.
- Normalization service for aggregate time-series CSV uploads.
- Forecast benchmark POC for stored aggregate time-series with naive, seasonal naive, ARIMA, SARIMA, optional StatsForecast AutoETS, and uploaded prediction CSV baselines.
- Feature availability, data quality, and model eligibility services that expose missingness instead of hiding it.
- Placeholder model-run behavior that produces only limited summaries when uploaded/test data supports them, otherwise `insufficient_data`.

## Uneven Country Data Handling

Sentinel Atlas does not assume all countries have the same signal coverage. For every country, the backend computes a source/feature profile from:

- normalized observations by signal category,
- source coverage records,
- news/event records,
- recency, lag, temporal coverage, spatial granularity, uncertainty, and source reliability.

Endpoints such as `/api/countries/{iso3}/coverage`, `/api/countries/{iso3}/features`, and `/api/countries/{iso3}/model-readiness` return both available and missing signals. Frontend views should display missing/stale/unknown statuses directly.

## API Endpoints

Countries:

- `GET /api/countries`
- `GET /api/countries/{iso3}`
- `GET /api/countries/{iso3}/coverage`
- `GET /api/countries/{iso3}/sources`
- `GET /api/countries/{iso3}/data-quality`
- `GET /api/countries/{iso3}/features`
- `GET /api/countries/{iso3}/model-readiness`

Sources:

- `GET /api/sources`
- `GET /api/sources/{sourceId}`
- `POST /api/sources`
- `PATCH /api/sources/{sourceId}`
- `GET /api/sources/{sourceId}/coverage`
- `POST /api/sources/{sourceId}/validate?country_iso3=USA`

Time series:

- `GET /api/countries/{iso3}/timeseries/available`
- `GET /api/timeseries/available?countryIso3=USA`
- `GET /api/timeseries?countryIso3=&sourceId=&metric=&startDate=&endDate=`
- `POST /api/timeseries/upload`
- `GET /api/metrics?countryIso3=&sourceId=`

Locations:

- `GET /api/locations?countryIso3=&type=`
- `GET /api/ports?countryIso3=`
- `GET /api/airports?countryIso3=`
- `GET /api/wastewater-sites?countryIso3=`

News:

- `GET /api/countries/{iso3}/news/latest`
- `POST /api/ingest/news`
- `GET /api/news?countryIso3=&startDate=&endDate=&signalCategory=`

Models:

- `POST /api/model-runs`
- `GET /api/model-runs/{id}`
- `GET /api/countries/{iso3}/model-readiness`
- `POST /api/model-runs/preview`

Forecast benchmarks:

- `GET /api/forecast-models`
- `GET /api/forecast-models/{modelId}`
- `POST /api/forecast-models/predictions/upload`
- `POST /api/forecast-benchmarks/preview`
- `POST /api/forecast-benchmarks`
- `GET /api/forecast-benchmarks/{id}`
- `GET /api/countries/{iso3}/forecast-benchmarks`

## Local Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Run tests:

```bash
cd backend
pytest
```

SQLite is used by default and creates `sentinel_atlas_dev.db` in the backend working directory. To use Postgres:

```bash
set SENTINEL_DATABASE_URL=postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinel_atlas
```

## Docker Compose

```bash
cd backend
docker compose up --build
```

The compose file starts the API plus Postgres with PostGIS-ready image. TimescaleDB is not enabled by default in this scaffold; add the extension in a deployment migration if the target database supports it.

## Uploading Aggregate Time-Series Data

CSV upload endpoint:

```bash
curl -F "file=@fixtures.csv" http://127.0.0.1:8000/api/timeseries/upload
```

Minimum required columns:

```text
sourceId,countryIso3,observedAt,signalCategory,metric,value
```

Useful optional columns:

```text
reportedAt,unit,normalizedValue,pathogen,sampleType,uncertaintyLower,uncertaintyUpper,qualityScore,provenanceUrl,rawPayloadRef,admin1,admin2,locationId
```

The upload path rejects likely PII, individual medical-record fields, and precise personal trace fields such as `person_id`, `patient_id`, `device_id`, or trajectory fields.

Discover chartable time-series options for a selected country before fetching rows:

```bash
curl http://127.0.0.1:8000/api/countries/USA/timeseries/available
```

The response is emitted in snake_case and is built only from stored normalized observations:

```json
{
  "country_iso3": "USA",
  "generated_at": "2026-04-25T18:00:00Z",
  "options": [],
  "warnings": [],
  "limitations": []
}
```

An empty `options` array means the frontend should show an empty state and must not fabricate chart data.

## Forecast Benchmarking

Forecast benchmarks are historical evaluations of stored aggregate metric values. They are not public-health alerts, risk scores, Rt/R0 estimates, or operational guidance.

Built-in benchmark models:

- `naive_last_value`
- `seasonal_naive`
- `statsmodels_arima`
- `statsmodels_sarima`
- `statsforecast_autoets`

`statsforecast_autoets` is the approved whitelisted open-source model for this stage. It uses Nixtla StatsForecast AutoETS as a statistical ETS benchmark only. It is not an epidemiological model, public-health alert, Rt/R0 estimate, risk score, or validated pandemic prediction.

Install the optional AutoETS dependency:

```bash
cd backend
pip install -e ".[dev,forecast]"
```

If `statsforecast` is not installed, `/api/forecast-models/statsforecast_autoets` still appears with `dependency_status: "missing_optional_dependency"`, and explicit benchmark requests return a structured `model_unavailable` result.

Preview a benchmark without saving it:

```bash
curl -X POST http://127.0.0.1:8000/api/forecast-benchmarks/preview ^
  -H "Content-Type: application/json" ^
  -d "{\"countryIso3\":\"USA\",\"sourceId\":\"fixture_forecast_source\",\"metric\":\"aggregate_signal\",\"frequency\":\"weekly\",\"horizonPeriods\":4}"
```

Preview AutoETS explicitly:

```bash
curl -X POST http://127.0.0.1:8000/api/forecast-benchmarks/preview ^
  -H "Content-Type: application/json" ^
  -d "{\"countryIso3\":\"USA\",\"sourceId\":\"fixture_forecast_source\",\"metric\":\"aggregate_signal\",\"frequency\":\"weekly\",\"horizonPeriods\":4,\"modelIds\":[\"statsforecast_autoets\"]}"
```

Uploaded model support accepts prediction CSVs only. It does not accept executable code, pickle/joblib artifacts, notebooks, containers, or model binaries.

Minimum forecast prediction CSV columns:

```text
modelId,modelName,countryIso3,sourceId,metric,targetDate,predictedValue
```

Useful optional columns:

```text
unit,lower,upper,generatedAt,provenanceUrl,limitations
```

The benchmark service uses only stored normalized observations, creates a holdout from the last `horizonPeriods`, and reports `mae`, `rmse`, `smape`, `n_train`, `n_test`, train/test windows, warnings, limitations, leaderboard comparison rows, and per-date observed/predicted values. If a series is missing or too short, the affected model returns `insufficient_data`; if an optional dependency is absent, the affected model returns `model_unavailable`.

## Frontend Integration

The frontend should:

- call `/api/countries/{iso3}/coverage` after map selection,
- call `/api/countries/{iso3}/sources` for country-specific source availability,
- call `/api/countries/{iso3}/timeseries/available` to list chartable source/metric/unit/date ranges,
- call `/api/timeseries` for uploaded/ingested aggregate records,
- call `/api/forecast-benchmarks/preview` before showing benchmark results,
- call `/api/forecast-models/predictions/upload` only for prediction CSVs, never executable artifacts,
- call `/api/countries/{iso3}/features` to enable/disable views,
- call `/api/countries/{iso3}/model-readiness` before offering model-run actions,
- display `warnings`, `limitations`, `missing_features`, provenance URLs, and source IDs.

More response examples are in `docs/frontend-contract.md`.

## Model Behavior

Implemented registry entries:

- `wastewater_trend_only`
- `forecast_hub_passthrough`
- `mobility_context_only`
- `news_event_signal`
- `multi_signal_ensemble`
- `insufficient_data`

No complex epidemiological model is implemented. The model-run endpoint stores an honest eligibility snapshot and produces numeric points only for narrow supported placeholder summaries, such as relative change over uploaded wastewater observations.

Forecast benchmark endpoints are separate from `/api/model-runs`. They compare baseline or uploaded prediction values against historical holdout observations and must be displayed as benchmark-only metric forecasts. Historical holdout performance is not proof of future public-health validity.

## Unimplemented

- Live ingestion from public APIs.
- Production migrations for PostGIS geometry and GiST spatial indexes.
- TimescaleDB hypertables and retention policies.
- Auth, rate limiting, and deployment hardening.
- Full source coverage backfill by country.
- Forecast hub normalization.
- Production-grade model registry security and authentication.
- News scraper implementation.
- Advanced epidemiological simulations.

## Safety And Privacy Assumptions

- Aggregate public-health and aggregate infrastructure data only.
- No individual-level tracking data.
- No PII, medical records, or precise personal mobility traces.
- Open-source news is a mention/signal stream, not confirmed public-health truth.
- Future scrapers must respect robots.txt, API terms, licenses, and source rate limits.
- Model copy must avoid certainty and operational public-alert language.
- The backend never outputs pathogen engineering, wet-lab, evasion, or dissemination guidance.
