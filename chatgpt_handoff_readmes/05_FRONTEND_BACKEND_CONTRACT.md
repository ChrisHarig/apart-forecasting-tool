# Sentinel Atlas Frontend Contract

Last updated: 2026-04-25

The backend returns direct FastAPI JSON objects with camelCase aliases accepted on input and snake_case currently emitted by the scaffold. Frontend adapters should map both forms while the API stabilizes.

## Country Selection

Call:

```text
GET /api/countries/{iso3}/coverage
```

Shape:

```json
{
  "country_iso3": "USA",
  "as_of_date": "2026-04-25",
  "overall_data_readiness_score": 0.42,
  "available_signal_categories": ["wastewater"],
  "missing_signal_categories": ["clinical_case_hospitalization", "aviation"],
  "features": [],
  "limitations": ["Availability is country-specific and source-specific."]
}
```

## Hover News Summary

Call:

```text
GET /api/countries/{iso3}/news/latest
```

Empty state:

```json
[]
```

Item:

```json
{
  "id": 1,
  "country_iso3": "USA",
  "event_date": "2026-04-24T00:00:00Z",
  "discovered_at": "2026-04-25T12:00:00Z",
  "headline": "Source-reported aggregate public-health mention",
  "summary": "Short source summary.",
  "source_name": "Example public source",
  "source_url": "https://example.test/story",
  "signal_category": "open_source_news",
  "severity": "info",
  "confidence": 0.6,
  "provenance": {"status": "source_mentioned"},
  "deduplication_key": "USA|2026-04-24|example|headline"
}
```

News records are event-based signals, not confirmed outbreak facts.

## Country Source Availability

Call:

```text
GET /api/countries/{iso3}/sources
```

Shape:

```json
[
  {
    "source": {
      "id": "who-flunet",
      "name": "WHO FluNet",
      "category": "pathogen_lab_surveillance",
      "official_url": "https://www.who.int/tools/flunet",
      "adapter_status": "placeholder",
      "reliability_tier": "official",
      "limitations": ["Reporting completeness varies by country and week."]
    },
    "coverageStatus": "unknown",
    "coverageNotes": "Placeholder connector; no live availability probe has run."
  }
]
```

## Source Catalog

Call:

```text
GET /api/sources
```

Each source includes:

```json
{
  "id": "user-upload",
  "name": "User-uploaded Aggregate Dataset",
  "category": "teammate_provided_data",
  "publisher": "Sentinel Atlas user",
  "access_type": "manual_upload",
  "license": "User-provided; must be supplied with upload provenance",
  "adapter_status": "implemented_manual_upload",
  "reliability_tier": "user_provided",
  "limitations": ["Only aggregate, non-PII public-health or infrastructure data are accepted."]
}
```

## Time-Series Availability

Call this before requesting chart rows:

```text
GET /api/countries/{iso3}/timeseries/available
GET /api/timeseries/available?countryIso3=USA
```

Empty state:

```json
{
  "country_iso3": "USA",
  "generated_at": "2026-04-25T18:00:00Z",
  "options": [],
  "warnings": [],
  "limitations": []
}
```

Populated example using explicit test/user-upload data only:

```json
{
  "country_iso3": "USA",
  "generated_at": "2026-04-25T18:00:00Z",
  "options": [
    {
      "source_id": "fixture_wastewater",
      "source_name": "fixture_wastewater",
      "signal_category": "wastewater",
      "metric": "viral_signal",
      "unit": "copies_ml",
      "record_count": 6,
      "start_date": "2026-04-01T00:00:00Z",
      "end_date": "2026-04-22T00:00:00Z",
      "latest_observed_at": "2026-04-22T00:00:00Z",
      "latest_value": 20.0,
      "quality_score": 0.84,
      "provenance_url": "https://example.test/f",
      "limitations": ["Created automatically for aggregate uploaded data."],
      "warnings": []
    }
  ],
  "warnings": [],
  "limitations": []
}
```

The response is emitted in snake_case. It is grouped by `country_iso3`, `source_id`, `signal_category`, `metric`, and `unit`, and it is generated only from stored normalized observations. If `options` is empty, no chart data exists for that country in the backend and the frontend should not fabricate records.

## Time-Series Values

Call:

```text
GET /api/timeseries?countryIso3=USA&sourceId=fixture_wastewater&metric=viral_signal&startDate=2026-04-01T00:00:00Z&endDate=2026-04-30T00:00:00Z
```

Shape:

```json
[
  {
    "id": 1,
    "source_id": "fixture_wastewater",
    "country_iso3": "USA",
    "observed_at": "2026-04-01T00:00:00Z",
    "reported_at": "2026-04-03T00:00:00Z",
    "signal_category": "wastewater",
    "metric": "viral_signal",
    "value": 10.0,
    "unit": "copies_ml",
    "normalized_value": 10.0,
    "quality_score": 0.8,
    "provenance_url": "https://example.test/a"
  }
]
```

## Upload Result

Call:

```text
POST /api/timeseries/upload
```

Multipart field:

```text
file=@aggregate.csv
```

Shape:

```json
{
  "inserted_count": 2,
  "rejected_count": 0,
  "dry_run": false,
  "observations": [],
  "errors": [],
  "warnings": [
    {
      "code": "test_or_user_data_only",
      "message": "Uploaded rows are treated as user-provided aggregate data and are not production source claims."
    }
  ]
}
```

## Model Readiness

Call:

```text
GET /api/countries/{iso3}/model-readiness
POST /api/model-runs/preview
```

Shape:

```json
{
  "country_iso3": "USA",
  "selected_model_id": "wastewater_trend_only",
  "eligible_models": [],
  "output_status": "complete",
  "features": [],
  "missing_features": ["forecast_or_nowcast"],
  "sources_used": ["fixture_wastewater"],
  "data_quality_score": 0.61,
  "warnings": [],
  "limitations": [],
  "explanation": "Selected wastewater_trend_only...",
  "generated_at": "2026-04-25T18:00:00Z"
}
```

If data is missing, `selected_model_id` is `insufficient_data`, `output_status` is `insufficient_data`, and the warning list explains that the backend refused to fabricate output.

## Model Outputs

Call:

```text
POST /api/model-runs
GET /api/model-runs/{id}
```

Shape:

```json
{
  "id": 1,
  "country_iso3": "USA",
  "selected_model_id": "wastewater_trend_only",
  "output_status": "complete",
  "explanation": "Selected wastewater_trend_only. Output is limited to trend summary...",
  "warnings": [],
  "output_points": [
    {
      "date": "2026-04-08",
      "metric": "observed_wastewater_relative_change",
      "value": 0.5,
      "unit": "relative_change"
    }
  ]
}
```

Outputs must include sources used, missing signals, data quality, uncertainty where available, limitations, and plain-language explanation in the run snapshots.

## Forecast Model Catalog

Call:

```text
GET /api/forecast-models
GET /api/forecast-models/{modelId}
```

Built-in model item:

```json
{
  "id": "statsforecast_autoets",
  "name": "StatsForecast AutoETS",
  "model_id": "statsforecast_autoets",
  "display_name": "StatsForecast AutoETS",
  "model_kind": "builtin_statsforecast",
  "model_family": "exponential_smoothing_ets",
  "implementation_source": "statsforecast",
  "benchmark_only": true,
  "builtin": true,
  "accepts_uploaded_code": false,
  "accepts_prediction_csv": false,
  "required_observation_count": 8,
  "supported_frequencies": ["daily", "weekly", "monthly"],
  "supports_prediction_intervals": "unknown",
  "dependency_status": "available",
  "description": "AutoETS benchmark fitted with the open-source Nixtla StatsForecast package.",
  "owner": "Sentinel Atlas",
  "status": "builtin",
  "limitations": ["Statistical time-series benchmark only; not an epidemiological model, public-health alert, or validated pandemic prediction."],
  "warnings": [
    {
      "code": "benchmark_only",
      "message": "Forecast benchmark outputs are historical metric evaluations only, not public-health alerts, risk scores, Rt/R0 estimates, or operational guidance.",
      "severity": "warning"
    }
  ]
}
```

If the optional `statsforecast` package is not installed, the same item is returned with `dependency_status: "missing_optional_dependency"` and explicit AutoETS benchmark requests return `model_unavailable`.

## Forecast Prediction Upload

Call:

```text
POST /api/forecast-models/predictions/upload
```

Multipart field:

```text
file=@forecast-predictions.csv
```

Minimum CSV columns:

```text
modelId,modelName,countryIso3,sourceId,metric,targetDate,predictedValue
```

Optional columns:

```text
unit,lower,upper,generatedAt,provenanceUrl,limitations
```

Shape:

```json
{
  "inserted_count": 2,
  "rejected_count": 0,
  "models": [
    {
      "id": "uploaded_baseline",
      "name": "Uploaded Baseline",
      "model_kind": "uploaded_predictions",
      "status": "uploaded_predictions",
      "provenance_url": "https://example.test/model",
      "limitations": ["Test fixture only"],
      "warnings": [
        {
          "code": "benchmark_only",
          "message": "Forecast benchmark outputs are historical metric evaluations only, not public-health alerts, risk scores, Rt/R0 estimates, or operational guidance.",
          "severity": "warning"
        }
      ]
    }
  ],
  "predictions": [
    {
      "model_id": "uploaded_baseline",
      "country_iso3": "USA",
      "source_id": "fixture_forecast_source",
      "metric": "aggregate_signal",
      "unit": "index",
      "target_date": "2025-02-16",
      "predicted_value": 16.0,
      "lower": 15.0,
      "upper": 17.0,
      "provenance_url": "https://example.test/model"
    }
  ],
  "errors": [],
  "warnings": [
    {
      "code": "benchmark_only",
      "message": "Forecast benchmark outputs are historical metric evaluations only, not public-health alerts, risk scores, Rt/R0 estimates, or operational guidance.",
      "severity": "warning"
    }
  ]
}
```

The backend accepts prediction values only. It rejects executable model artifacts and CSV fields that look like PII, medical records, or operational trace data.

## Forecast Benchmarks

Call:

```text
POST /api/forecast-benchmarks/preview
POST /api/forecast-benchmarks
GET /api/forecast-benchmarks/{id}
GET /api/countries/{iso3}/forecast-benchmarks
```

Request:

```json
{
  "country_iso3": "USA",
  "source_id": "fixture_forecast_source",
  "metric": "aggregate_signal",
  "unit": "index",
  "frequency": "weekly",
  "horizon_periods": 4,
  "model_ids": ["naive_last_value", "seasonal_naive", "statsforecast_autoets"]
}
```

Response:

```json
{
  "id": 1,
  "country_iso3": "USA",
  "source_id": "fixture_forecast_source",
  "metric": "aggregate_signal",
  "unit": "index",
  "frequency": "weekly",
  "horizon_periods": 4,
  "requested_model_ids": ["naive_last_value"],
  "output_status": "complete",
  "explanation": "Forecast benchmark completed using stored aggregate observations.",
  "warnings": [
    {
      "code": "benchmark_only",
      "message": "Forecast benchmark outputs are historical metric evaluations only, not public-health alerts, risk scores, Rt/R0 estimates, or operational guidance.",
      "severity": "warning"
    }
  ],
  "limitations": ["Benchmarks use stored aggregate observations only."],
  "comparison": [
    {
      "rank": 1,
      "model_id": "naive_last_value",
      "display_name": "Naive last value",
      "status": "complete",
      "mae": 1.25,
      "rmse": 1.5,
      "smape": 8.1,
      "n_train": 20,
      "n_test": 4,
      "train_start": "2025-01-05",
      "train_end": "2025-05-18",
      "test_start": "2025-05-25",
      "test_end": "2025-06-15",
      "benchmark_note": "Historical holdout performance is not proof of future public-health validity."
    }
  ],
  "data_quality_notes": [],
  "created_at": "2026-04-25T18:00:00Z",
  "results": [
    {
      "model_id": "naive_last_value",
      "model_name": "Naive last value",
      "model_kind": "builtin_baseline",
      "status": "complete",
      "mae": 1.25,
      "rmse": 1.5,
      "smape": 8.1,
      "n_train": 20,
      "n_test": 4,
      "train_start": "2025-01-05",
      "train_end": "2025-05-18",
      "test_start": "2025-05-25",
      "test_end": "2025-06-15",
      "warnings": [
        {
          "code": "benchmark_only",
          "message": "Forecast benchmark outputs are historical metric evaluations only, not public-health alerts, risk scores, Rt/R0 estimates, or operational guidance.",
          "severity": "warning"
        }
      ],
      "limitations": ["Baseline only; useful as a simple benchmark floor."],
      "data_quality_notes": [],
      "points": [
        {
          "date": "2025-05-25",
          "observed_value": 34.5,
          "predicted_value": 32.0,
          "unit": "index"
        }
      ]
    }
  ]
}
```

Forecast benchmark values are historical metric evaluations over a holdout window. They must not be presented as public-health alerts, risk scores, Rt/R0 estimates, or operational guidance. If no matching stored observations exist, preview returns `output_status: "insufficient_data"` and create returns HTTP 400. Model-specific statuses include `complete`, `insufficient_data`, `model_unavailable`, and `failed`.

## Data-Quality Warnings

The frontend should display:

- low `quality_score`,
- empty time-series availability `options`,
- forecast benchmark `insufficient_data`, `partial`, `model_unavailable`, or `failed` statuses,
- stale `latest_observation_at`,
- `missing_features`,
- source `limitations`,
- absent `provenance_url`,
- news `confidence`,
- `insufficient_data` model status.

The news endpoint returns `[]` when no event records exist. It must not be interpreted as confirmed absence of public-health activity.
