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
- Forecast benchmark and challenge POC for stored aggregate time-series with naive, seasonal naive, ARIMA, SARIMA, optional StatsForecast AutoETS, uploaded prediction CSV baselines, built-in challenge predictions stored as internal prediction sets, scoring, leaderboards, and observed-vs-predicted comparison rows.
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
- `GET /api/forecast-models/predictions`
- `GET /api/forecast-models/predictions/{predictionSetId}`
- `DELETE /api/forecast-models/predictions/{predictionSetId}`
- `POST /api/forecast-benchmarks/datasets/preview`
- `POST /api/forecast-benchmarks/datasets`
- `GET /api/forecast-benchmarks/datasets/{datasetSnapshotId}`
- `GET /api/forecast-benchmarks/datasets/{datasetSnapshotId}/prediction-template`
- `POST /api/forecast-benchmarks/preview`
- `POST /api/forecast-benchmarks`
- `GET /api/forecast-benchmarks/{id}`
- `GET /api/countries/{iso3}/forecast-benchmarks`

Forecast challenges:

- `POST /api/forecast-challenges/preview`
- `POST /api/forecast-challenges`
- `GET /api/forecast-challenges`
- `GET /api/forecast-challenges/{challengeId}`
- `GET /api/countries/{iso3}/forecast-challenges`
- `GET /api/forecast-challenges/{challengeId}/prediction-template`
- `POST /api/forecast-challenges/{challengeId}/run-builtins`
- `POST /api/forecast-challenges/{challengeId}/predictions/upload`
- `POST /api/forecast-challenges/{challengeId}/score`
- `GET /api/forecast-challenges/{challengeId}/leaderboard?metric=smape`
- `GET /api/forecast-challenges/{challengeId}/comparison-points`
- `GET /api/forecast-challenges/{challengeId}/predictions`
- `GET /api/prediction-sets?countryIso3=&sourceId=&metric=&challengeId=`
- `GET /api/prediction-sets/{predictionSetId}`
- `PATCH /api/prediction-sets/{predictionSetId}/review`
- `GET /api/prediction-sets/{predictionSetId}/review`
- `GET /api/submitters`
- `GET /api/submitters/{submitterId}`

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

Production benchmark workflow:

1. Upload or ingest aggregate observations into `observations`.
2. Create a benchmark dataset snapshot from one country/source/metric series.
3. Download the prediction template for that snapshot.
4. Upload external model predictions as CSV values tied to the snapshot.
5. Run built-in benchmark models and uploaded prediction sets together.
6. Read the shared leaderboard and observed-vs-predicted comparison rows.

The snapshot stores the country, source, metric, unit, frequency, split strategy, train/test windows, target dates, observation IDs, dataset hash, warnings, limitations, and provenance notes. All built-in models and uploaded prediction CSVs are scored against those same target dates and observed holdout values.

Fairness limitation: the backend can verify that uploaded predictions match the snapshot scoring dates and series, but it cannot prove that an external model did not look at holdout values before upload. A future blind benchmark workflow would be needed for that.

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

When uploading predictions tied to a benchmark dataset snapshot, `modelId`, `modelName`, `countryIso3`, `sourceId`, `metric`, and `unit` may be supplied as multipart form metadata instead of repeated in every CSV row. The minimum tied CSV can be:

```text
targetDate,predictedValue
```

Useful optional columns:

```text
unit,lower,upper,generatedAt,provenanceUrl,limitations
```

Create a benchmark dataset snapshot:

```bash
curl -X POST http://127.0.0.1:8000/api/forecast-benchmarks/datasets ^
  -H "Content-Type: application/json" ^
  -d "{\"countryIso3\":\"USA\",\"sourceId\":\"fixture_forecast_source\",\"metric\":\"aggregate_signal\",\"unit\":\"index\",\"frequency\":\"weekly\",\"horizonPeriods\":4}"
```

Get a prediction template:

```bash
curl "http://127.0.0.1:8000/api/forecast-benchmarks/datasets/1/prediction-template?format=csv"
```

Upload external predictions tied to a snapshot:

```bash
curl -X POST http://127.0.0.1:8000/api/forecast-models/predictions/upload ^
  -F "benchmark_dataset_snapshot_id=1" ^
  -F "model_id=team_model_v1" ^
  -F "model_name=Team Model v1" ^
  -F "file=@team_predictions.csv"
```

Run built-ins plus uploaded predictions on the same snapshot:

```bash
curl -X POST http://127.0.0.1:8000/api/forecast-benchmarks/preview ^
  -H "Content-Type: application/json" ^
  -d "{\"datasetSnapshotId\":1,\"modelIds\":[\"naive_last_value\",\"seasonal_naive\",\"statsmodels_arima\",\"statsmodels_sarima\",\"statsforecast_autoets\"],\"uploadedPredictionSetIds\":[1]}"
```

Save and retrieve a benchmark run:

```bash
curl -X POST http://127.0.0.1:8000/api/forecast-benchmarks ^
  -H "Content-Type: application/json" ^
  -d "{\"datasetSnapshotId\":1,\"modelIds\":[\"naive_last_value\"],\"uploadedPredictionSetIds\":[1]}"

curl http://127.0.0.1:8000/api/forecast-benchmarks/1
curl http://127.0.0.1:8000/api/countries/USA/forecast-benchmarks
```

The benchmark service uses only stored normalized observations, creates a holdout from the last `horizonPeriods`, and reports `mae`, `rmse`, `smape`, `n_train`, `n_test`, train/test windows, warnings, limitations, `leaderboard`, `comparison_points`, and per-date observed/predicted values. If a series is missing or too short, the affected model returns `insufficient_data`; if an optional dependency is absent, the affected model returns `model_unavailable`; mismatched uploaded prediction sets return `invalid_predictions`.

## Forecast Challenges

Forecast challenge snapshots freeze the exact context for future challenge scoring. They are separate from benchmark runs: a challenge defines the target dates and data context, while benchmark runs and uploaded prediction sets can later use that context.

Modes:

- `retrospective_holdout`: uses historical stored observations, holds out the last `horizonPeriods` observations as truth, and can be benchmarked immediately.
- `prospective_challenge`: uses observations available at or before `cutoffAt`, generates future target dates, and stores predictions now for scoring later when aggregate truth arrives.

Create a retrospective challenge preview:

```bash
curl -X POST http://127.0.0.1:8000/api/forecast-challenges/preview ^
  -H "Content-Type: application/json" ^
  -d "{\"mode\":\"retrospective_holdout\",\"countryIso3\":\"USA\",\"sourceId\":\"fixture_challenge_source\",\"metric\":\"aggregate_signal\",\"unit\":\"index\",\"frequency\":\"weekly\",\"horizonPeriods\":4}"
```

Create a prospective challenge:

```bash
curl -X POST http://127.0.0.1:8000/api/forecast-challenges ^
  -H "Content-Type: application/json" ^
  -d "{\"mode\":\"prospective_challenge\",\"countryIso3\":\"USA\",\"sourceId\":\"fixture_challenge_source\",\"metric\":\"aggregate_signal\",\"unit\":\"index\",\"frequency\":\"weekly\",\"horizonPeriods\":4,\"cutoffAt\":\"2026-04-01T00:00:00Z\"}"
```

Get the prediction template:

```bash
curl "http://127.0.0.1:8000/api/forecast-challenges/1/prediction-template?format=csv"
```

Template rows include `targetDate`, blank `modelId`, blank `modelName`, blank `predictedValue`, optional interval columns, unit, country, source, metric, optional signal category, generated timestamp, and provenance URL. Retrospective templates intentionally omit observed holdout values. Prospective templates have no observed truth yet.

Run built-in baseline predictions for a challenge:

```bash
curl -X POST http://127.0.0.1:8000/api/forecast-challenges/1/run-builtins ^
  -H "Content-Type: application/json" ^
  -d "{\"modelIds\":[\"naive_last_value\",\"seasonal_naive\",\"statsmodels_arima\",\"statsmodels_sarima\",\"statsforecast_autoets\"],\"overwriteExisting\":false}"
```

Successful built-ins are stored as `PredictionSet` rows with `prediction_source: "built_in"`, `submission_track: "internal_baseline"`, `review_status: "approved"`, and `validation_status: "valid_for_snapshot"`. Their `PredictionPoint` rows use exactly the challenge target dates. Prospective challenge prediction sets use `scoring_status: "pending_truth"` until matching aggregate truth arrives; retrospective prediction sets can be scored immediately through the challenge scoring endpoint.

Model-specific run statuses are `complete`, `insufficient_data`, `model_unavailable`, and `failed`. One unavailable or failed built-in does not fail the whole run.

Challenge statuses:

- `open`: prospective challenge with enough training observations.
- `closed`: retrospective holdout with enough training and target observations.
- `insufficient_data`: not enough aggregate observations or target periods.
- `pending_truth`: predictions exist but no target-date truth is available yet.
- `partially_scored`: some target-date truth is available.
- `scored`: all target-date truth is available and scores were computed.
- `draft` and `scoring`: reserved for challenge lifecycle steps.

The backend does not execute submitted model code for challenges. It accepts prediction CSV values only through the existing prediction upload pathway.

Upload external predictions for a challenge:

```bash
curl -X POST http://127.0.0.1:8000/api/forecast-challenges/1/predictions/upload ^
  -F "model_id=team_model_v1" ^
  -F "model_name=Team Model v1" ^
  -F "file=@team_predictions.csv"
```

Minimum challenge prediction CSV columns:

```text
modelId,modelName,targetDate,predictedValue
```

`countryIso3`, `sourceId`, and `metric` may come from the challenge context or CSV columns. Optional metadata includes `signalCategory`, `unit`, `lower`, `upper`, `generatedAt`, `provenanceUrl`, `limitations`, `methodSummary`, `modelUrl`, `codeUrl`, `submitterName`, `submitterEmail`, `organization`, `submissionTrack`, `visibility`, and `disclosureNotes`. Submitter email is allowed only as submission metadata; an `email` data column is rejected as PII-like input. `modelUrl` and `codeUrl` are stored as metadata only and are never fetched or executed.

Submission tracks:

- `internal_baseline`: backend-owned built-ins, approved by default.
- `public`: public hackathon submissions, unreviewed by default.
- `verified_group`: labeled group submissions, unreviewed by default unless reviewed later. This is metadata only, not cryptographic identity verification.

Review statuses:

- `unreviewed`
- `approved`
- `rejected`
- `needs_changes`

Public and verified-group uploads require `submitterName`. `organization` and `methodSummary` are recommended, especially for verified-group submissions. Submitter email is stored only as optional metadata and is not returned in public leaderboard rows or submitter list responses.

Challenge upload validation requires exact target-date matches, numeric predictions, no duplicate target dates, no missing or extra target dates, matching country/source/metric, and `lower <= predicted <= upper` when intervals are supplied. Unit mismatches are stored as `overlay_only` and are not scored or ranked. Metric mismatches are invalid unless explicitly allowed for overlay-only comparison.

Score all prediction sets for a challenge:

```bash
curl -X POST http://127.0.0.1:8000/api/forecast-challenges/1/score ^
  -H "Content-Type: application/json" ^
  -d "{\"rankingMetric\":\"smape\"}"
```

Read leaderboard and observed-vs-predicted rows:

```bash
curl "http://127.0.0.1:8000/api/forecast-challenges/1/leaderboard?metric=smape"
curl http://127.0.0.1:8000/api/forecast-challenges/1/comparison-points
```

Leaderboard filters:

```text
metric=smape|rmse|mae
submissionTrack=all|internal_baseline|public|verified_group
reviewStatus=all|approved|unreviewed|rejected|needs_changes
includeUnreviewed=true|false
```

Ranking supports `smape`, `rmse`, and `mae`. Scored and partially scored prediction sets are ranked; `pending_truth`, `overlay_only`, invalid, unavailable, failed, rejected, or needs-changes sets remain visible when filters allow them but unranked.

Review a prediction set:

```bash
curl -X PATCH http://127.0.0.1:8000/api/prediction-sets/12/review ^
  -H "Content-Type: application/json" ^
  -d "{\"reviewStatus\":\"approved\",\"reviewerName\":\"Hackathon reviewer\",\"reviewNotes\":\"Metadata reviewed for demo.\"}"
```

## Frontend Integration

The frontend should:

- call `/api/countries/{iso3}/coverage` after map selection,
- call `/api/countries/{iso3}/sources` for country-specific source availability,
- call `/api/countries/{iso3}/timeseries/available` to list chartable source/metric/unit/date ranges,
- call `/api/timeseries` for uploaded/ingested aggregate records,
- call `/api/forecast-benchmarks/datasets/preview` or `/api/forecast-benchmarks/datasets` to create a reproducible train/test split,
- call `/api/forecast-benchmarks/datasets/{id}/prediction-template` before asking users for external predictions,
- call `/api/forecast-challenges/preview` or `/api/forecast-challenges` when the product needs retrospective/prospective challenge snapshots,
- call `/api/forecast-challenges/{id}/prediction-template` for challenge submission templates,
- call `/api/forecast-challenges/{id}/run-builtins` to generate internal baseline prediction sets for challenge target dates,
- call `/api/forecast-challenges/{id}/predictions/upload` to upload user prediction CSVs tied to a challenge,
- call `/api/forecast-challenges/{id}/score` after new truth arrives or after retrospective submissions,
- call `/api/forecast-challenges/{id}/leaderboard?metric=smape` for ranked benchmark results,
- call `/api/forecast-challenges/{id}/comparison-points` for observed-vs-predicted overlays,
- call `/api/forecast-challenges/{id}/predictions` or `/api/prediction-sets` to list stored challenge prediction sets,
- call `/api/prediction-sets/{id}/review` for lightweight hackathon review decisions,
- call `/api/submitters` for public submitter labels without email addresses,
- call `/api/forecast-benchmarks/preview` before showing benchmark results,
- call `/api/forecast-models/predictions/upload` only for prediction CSVs, never executable artifacts,
- call `/api/forecast-models/predictions` to list stored prediction sets,
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

Forecast challenge built-ins are also benchmark-only metric forecasts. They are persisted as internal prediction sets so future scoring can compare built-in and user-submitted predictions on the same frozen challenge target dates. They are not epidemiological models, public-health alerts, Rt/R0 estimates, or operational recommendations.

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
