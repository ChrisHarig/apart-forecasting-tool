# Sentinel Atlas Frontend Contract

Last updated: 2026-04-26

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
GET /api/forecast-models?includeExperimental=true
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
  "experimental": false,
  "enabled_by_default": true,
  "feature_flag_enabled": true,
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

Experimental model visibility:

- `GET /api/forecast-models` omits disabled experimental models by default.
- `GET /api/forecast-models?includeExperimental=true` includes `experimental_tabpfn_ts`.
- `GET /api/forecast-models/experimental_tabpfn_ts` returns metadata even when the feature flag is disabled.

Experimental TabPFN-Time-Series metadata uses:

```json
{
  "id": "experimental_tabpfn_ts",
  "display_name": "Experimental TabPFN-Time-Series",
  "model_family": "foundation_time_series_experimental",
  "status": "experimental",
  "experimental": true,
  "enabled_by_default": false,
  "feature_flag_enabled": false,
  "dependency_status": "missing_optional_dependency",
  "benchmark_only": true,
  "builtin": true,
  "accepts_uploaded_code": false,
  "accepts_prediction_csv": false,
  "limitations": [
    "Experimental statistical/foundation time-series benchmark only; not an epidemiological model, public-health alert, or validated pandemic prediction."
  ],
  "safety_notes": [
    "Experimental statistical/foundation time-series benchmark only.",
    "Not a validated epidemiological model.",
    "Not a public-health alert.",
    "No user model code is executed.",
    "No remote inference is used by default."
  ]
}
```

The experimental model is excluded from default built-in runs. If explicitly requested while disabled, `/api/forecast-challenges/{challengeId}/run-builtins` and benchmark preview responses return `experimental_disabled`. If enabled but the optional dependency is missing, they return `model_unavailable`. Frontend surfaces must label this as experimental benchmark-only output and must not describe it as a validated public-health forecast.

## Benchmark Dataset Snapshots

Create a reproducible train/test split before running built-ins or comparing uploaded predictions.

Calls:

```text
POST /api/forecast-benchmarks/datasets/preview
POST /api/forecast-benchmarks/datasets
GET /api/forecast-benchmarks/datasets/{datasetSnapshotId}
GET /api/forecast-benchmarks/datasets/{datasetSnapshotId}/prediction-template
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
  "split_strategy": "last_n_periods"
}
```

Preview response:

```json
{
  "dataset_snapshot": {
    "id": null,
    "country_iso3": "USA",
    "source_id": "fixture_forecast_source",
    "metric": "aggregate_signal",
    "unit": "index",
    "frequency": "weekly",
    "horizon_periods": 4,
    "split_strategy": "last_n_periods",
    "train_start": "2025-01-05",
    "train_end": "2025-05-18",
    "test_start": "2025-05-25",
    "test_end": "2025-06-15",
    "target_dates": ["2025-05-25", "2025-06-01", "2025-06-08", "2025-06-15"],
    "n_train": 20,
    "n_test": 4,
    "dataset_hash": "sha256...",
    "status": "ready",
    "warnings": [],
    "limitations": ["Benchmark dataset snapshots do not pad, interpolate, or fabricate missing observation dates."]
  },
  "train_preview": [],
  "target_template": [
    {
      "target_date": "2025-05-25",
      "model_id": null,
      "model_name": null,
      "country_iso3": "USA",
      "source_id": "fixture_forecast_source",
      "metric": "aggregate_signal",
      "predicted_value": null,
      "unit": "index"
    }
  ]
}
```

The prediction-template endpoint returns JSON by default. Add `?format=csv` for CSV headers and target dates. The template intentionally does not expose holdout observed values.

## Forecast Challenge Snapshots

Forecast challenges freeze a series context for user submissions. They are used for challenge setup, not for public-health alerts.

Calls:

```text
POST /api/forecast-challenges/preview
POST /api/forecast-challenges
GET /api/forecast-challenges?countryIso3=USA&mode=prospective_challenge
GET /api/forecast-challenges/{challengeId}
GET /api/countries/{iso3}/forecast-challenges
GET /api/forecast-challenges/{challengeId}/prediction-template
POST /api/forecast-challenges/{challengeId}/run-builtins
POST /api/forecast-challenges/{challengeId}/predictions/upload
POST /api/forecast-challenges/{challengeId}/score
GET /api/forecast-challenges/{challengeId}/leaderboard?metric=smape
GET /api/forecast-challenges/{challengeId}/comparison-points
GET /api/forecast-challenges/{challengeId}/predictions
GET /api/prediction-sets?countryIso3=USA&sourceId=fixture_challenge_source&metric=aggregate_signal
GET /api/prediction-sets/{predictionSetId}
PATCH /api/prediction-sets/{predictionSetId}/review
GET /api/prediction-sets/{predictionSetId}/review
GET /api/submitters
GET /api/submitters/{submitterId}
```

Retrospective request:

```json
{
  "mode": "retrospective_holdout",
  "country_iso3": "USA",
  "source_id": "fixture_challenge_source",
  "metric": "aggregate_signal",
  "unit": "index",
  "frequency": "weekly",
  "horizon_periods": 4,
  "split_strategy": "last_n_periods"
}
```

Prospective request:

```json
{
  "mode": "prospective_challenge",
  "country_iso3": "USA",
  "source_id": "fixture_challenge_source",
  "metric": "aggregate_signal",
  "unit": "index",
  "frequency": "weekly",
  "horizon_periods": 4,
  "cutoff_at": "2026-04-01T00:00:00Z"
}
```

Preview response:

```json
{
  "challenge_snapshot": {
    "id": null,
    "mode": "prospective_challenge",
    "country_iso3": "USA",
    "source_id": "fixture_challenge_source",
    "signal_category": null,
    "metric": "aggregate_signal",
    "unit": "index",
    "frequency": "weekly",
    "horizon_periods": 4,
    "split_strategy": "last_n_periods",
    "cutoff_at": "2026-04-01T00:00:00Z",
    "train_start": "2026-01-01",
    "train_end": "2026-04-01",
    "target_start": "2026-04-08",
    "target_end": "2026-04-29",
    "target_dates": ["2026-04-08", "2026-04-15", "2026-04-22", "2026-04-29"],
    "n_train": 14,
    "n_targets": 4,
    "dataset_hash": "sha256...",
    "status": "open",
    "warnings": [
      {
        "code": "prospective_truth_unavailable",
        "message": "Prospective challenge target observations do not exist yet and cannot be scored until aggregate truth arrives.",
        "severity": "info"
      }
    ],
    "limitations": [
      "Prediction templates do not include observed truth values."
    ]
  },
  "train_preview": [],
  "prediction_template": [
    {
      "model_id": null,
      "model_name": null,
      "target_date": "2026-04-08",
      "predicted_value": null,
      "lower": null,
      "upper": null,
      "unit": "index",
      "country_iso3": "USA",
      "source_id": "fixture_challenge_source",
      "metric": "aggregate_signal",
      "signal_category": null,
      "generated_at": null,
      "provenance_url": null
    }
  ]
}
```

Status values:

```text
draft | open | closed | scoring | pending_truth | partially_scored | scored | insufficient_data
```

Mode behavior:

- `retrospective_holdout` uses historical observations and freezes holdout observation IDs. Its prediction template omits observed holdout values.
- `prospective_challenge` uses observations at or before `cutoff_at`, generates future target dates, and has no truth values until later aggregate observations arrive.

The frontend should display warnings and limitations. It should not present challenge templates as public-health alerts, risk scores, Rt/R0 estimates, or operational guidance.

### Built-In Challenge Prediction Sets

Built-in models can be run against a persisted challenge snapshot. The backend stores each successful built-in output as an internal prediction set using the challenge's exact train rows and target dates.

Request:

```json
{
  "model_ids": [
    "naive_last_value",
    "seasonal_naive",
    "statsmodels_arima",
    "statsmodels_sarima",
    "statsforecast_autoets"
  ],
  "overwrite_existing": false
}
```

Response:

```json
{
  "challenge_id": 1,
  "prediction_sets": [
    {
      "id": 12,
      "challenge_id": 1,
      "model_id": "naive_last_value",
      "model_name": "Naive last value",
      "prediction_source": "built_in",
      "submission_track": "internal_baseline",
      "review_status": "approved",
      "validation_status": "valid_for_snapshot",
      "scoring_status": "pending_truth",
      "country_iso3": "USA",
      "source_id": "fixture_challenge_source",
      "signal_category": null,
      "metric": "aggregate_signal",
      "unit": "index",
      "frequency": "weekly",
      "horizon_periods": 4,
      "warnings": [
        {
          "code": "challenge_prediction_only",
          "message": "Built-in challenge prediction sets are benchmark-only metric forecasts, not public-health alerts, risk scores, Rt/R0 estimates, validated epidemiological predictions, or operational guidance.",
          "severity": "warning"
        }
      ],
      "limitations": [
        "Historical holdout benchmark performance is not proof of future public-health validity."
      ],
      "points": [
        {
          "id": 101,
          "prediction_set_id": 12,
          "target_date": "2026-04-08",
          "predicted_value": 42.0,
          "lower": null,
          "upper": null,
          "unit": "index",
          "generated_at": "2026-04-26T15:00:00Z",
          "provenance_url": null,
          "created_at": "2026-04-26T15:00:00Z"
        }
      ]
    }
  ],
  "results": [
    {
      "model_id": "naive_last_value",
      "status": "complete",
      "prediction_set_id": 12,
      "warnings": [],
      "limitations": []
    },
    {
      "model_id": "statsforecast_autoets",
      "status": "model_unavailable",
      "prediction_set_id": null,
      "warnings": [
        {
          "code": "missing_optional_dependency",
          "message": "Optional dependency statsforecast is not installed.",
          "severity": "warning"
        }
      ],
      "limitations": []
    }
  ]
}
```

Status meanings:

```text
complete | insufficient_data | model_unavailable | experimental_disabled | failed
```

Prediction set conventions:

- `prediction_source: "built_in"` and `submission_track: "internal_baseline"` identify backend-owned baselines.
- `validation_status: "valid_for_snapshot"` means the point dates match the challenge target dates.
- Prospective challenges return `scoring_status: "pending_truth"` because future observed values do not exist yet.
- `overwrite_existing: false` reuses an existing built-in prediction set instead of duplicating it.
- `overwrite_existing: true` replaces the previous built-in set for the same challenge/model.
- `experimental_disabled` means the model was explicitly requested but the required feature flag is false.
- Built-in prediction sets are benchmark-only metric forecasts, not public-health alerts or validated epidemiological predictions.

## Challenge Prediction Upload, Scoring, And Overlays

Challenge-tied uploads compare user prediction CSVs against the exact challenge target dates. They use the same scoring path as built-in prediction sets.

Call:

```text
POST /api/forecast-challenges/{challengeId}/predictions/upload
```

Minimum CSV columns:

```text
modelId,modelName,targetDate,predictedValue
```

Required by CSV columns or challenge/form metadata:

```text
countryIso3,sourceId,metric
```

Optional columns or form fields:

```text
signalCategory,unit,lower,upper,generatedAt,provenanceUrl,limitations,methodSummary,modelUrl,codeUrl,submitterName,submitterEmail,organization,submissionTrack,visibility,disclosureNotes
```

Submitter email is allowed as submission metadata, but `email` as a prediction data column is rejected. Submitter email is not emitted in public leaderboard rows or submitter list responses. `modelUrl` and `codeUrl` are stored as metadata only; the backend does not fetch or execute them. The backend also rejects executable model artifacts and PII-like, medical-record, or individual trace columns.

Submission tracks:

```text
internal_baseline | public | verified_group
```

Review statuses:

```text
unreviewed | approved | rejected | needs_changes
```

Public and verified-group uploads require `submitterName`. `verified_group` is hackathon metadata only and should not be presented as cryptographic identity verification.

Upload response:

```json
{
  "prediction_set_id": 123,
  "inserted_count": 4,
  "rejected_count": 0,
  "validation_status": "valid_for_snapshot",
  "scoring_status": "scored",
  "matched_challenge_id": 1,
  "warnings": [
    {
      "code": "external_training_unverified",
      "message": "Sentinel Atlas can verify prediction target dates but cannot verify external training data.",
      "severity": "warning"
    }
  ],
  "errors": []
}
```

Validation statuses:

```text
valid_for_snapshot | overlay_only | stored_unmatched | invalid
```

Scoring statuses:

```text
pending_truth | partially_scored | scored | unscored | invalid
```

Benchmark scoring requires matching country, source, metric, target dates, and unit when both units are present. If units do not match, the prediction set is stored as `overlay_only`; it is shown for visual overlay but has no MAE/RMSE/SMAPE and no rank. Metric mismatches are invalid unless the request explicitly allows overlay-only mode.

Score request:

```text
POST /api/forecast-challenges/{challengeId}/score
```

```json
{
  "ranking_metric": "smape"
}
```

Score response:

```json
{
  "challenge_id": 1,
  "status": "scored",
  "ranking_metric": "smape",
  "scores": [
    {
      "prediction_set_id": 123,
      "status": "scored",
      "mae": 1.2,
      "rmse": 1.8,
      "smape": 7.4,
      "n_scored": 4,
      "n_expected": 4,
      "rank_smape": 1,
      "rank_rmse": 1,
      "rank_mae": 1,
      "warnings": [],
      "limitations": [
        "Historical holdout benchmark performance is not proof of future public-health validity."
      ]
    }
  ],
  "warnings": [],
  "limitations": [
    "Historical holdout performance is not proof of future public-health validity."
  ]
}
```

Leaderboard call:

```text
GET /api/forecast-challenges/{challengeId}/leaderboard?metric=smape&submissionTrack=all&reviewStatus=all&includeUnreviewed=true
```

```json
{
  "challenge_id": 1,
  "ranking_metric": "smape",
  "leaderboard": [
    {
      "rank": 1,
      "prediction_set_id": 123,
      "model_id": "team_model_v1",
      "model_name": "Team Model v1",
      "prediction_source": "user_uploaded",
      "submission_track": "public",
      "review_status": "unreviewed",
      "submitter_display_name": "Team V1",
      "organization": "Example Org",
      "method_summary": "Short model summary supplied by the team.",
      "model_url": "https://example.test/model",
      "code_url": "https://example.test/code",
      "provenance_url": "https://example.test/provenance",
      "visibility": "public",
      "status": "scored",
      "mae": 1.2,
      "rmse": 1.8,
      "smape": 7.4,
      "n_scored": 4,
      "n_expected": 4,
      "warnings": [],
      "limitations": []
    }
  ],
  "warnings": [],
  "limitations": [
    "Historical holdout performance is not proof of future public-health validity."
  ]
}
```

Comparison points call:

```text
GET /api/forecast-challenges/{challengeId}/comparison-points
```

```json
[
  {
    "target_date": "2026-05-03T00:00:00Z",
    "observed_value": 100.0,
    "unit": "copies_ml",
    "predictions": [
      {
        "prediction_set_id": 123,
        "model_id": "team_model_v1",
        "model_name": "Team Model v1",
        "prediction_source": "user_uploaded",
        "predicted_value": 98.5,
        "lower": null,
        "upper": null,
        "absolute_error": 1.5,
        "percentage_error": 1.5,
        "unit": "copies_ml",
        "validation_status": "valid_for_snapshot",
        "scoring_status": "scored"
      }
    ]
  }
]
```

Leaderboard filters:

```text
metric=smape|rmse|mae
submissionTrack=all|internal_baseline|public|verified_group
reviewStatus=all|approved|unreviewed|rejected|needs_changes
includeUnreviewed=true|false
```

Ranking metrics are `smape`, `rmse`, and `mae`; default is `smape`. Only scored or partially scored prediction sets with at least one scored point are ranked. Pending-truth, overlay-only, invalid, unavailable, failed, rejected, and needs-changes rows remain visible when filters allow them but unranked. Built-in baselines remain `internal_baseline` and `approved`.

Review request:

```text
PATCH /api/prediction-sets/{predictionSetId}/review
```

```json
{
  "review_status": "approved",
  "reviewer_name": "Hackathon reviewer",
  "review_notes": "Metadata reviewed for demo."
}
```

Review response:

```json
{
  "id": 1,
  "prediction_set_id": 123,
  "review_status": "approved",
  "reviewer_name": "Hackathon reviewer",
  "review_notes": "Metadata reviewed for demo.",
  "created_at": "2026-04-26T17:00:00Z"
}
```

Submitter list item:

```json
{
  "id": 1,
  "display_name": "Team V1",
  "organization": "Example Org",
  "affiliation_type": "public",
  "verification_status": "unverified",
  "notes": null,
  "created_at": "2026-04-26T17:00:00Z",
  "updated_at": null
}
```

Submitter responses intentionally omit email addresses.

## Forecast Prediction Upload

Calls:

```text
POST /api/forecast-models/predictions/upload
GET /api/forecast-models/predictions?datasetSnapshotId=1
GET /api/forecast-models/predictions/{predictionSetId}
DELETE /api/forecast-models/predictions/{predictionSetId}
```

Standalone CSV minimum columns:

```text
modelId,modelName,countryIso3,sourceId,metric,targetDate,predictedValue
```

Snapshot-tied uploads may supply `benchmark_dataset_snapshot_id`, `model_id`, and `model_name` as multipart form fields, with a minimum CSV of:

```text
targetDate,predictedValue
```

Optional CSV columns:

```text
unit,lower,upper,generatedAt,provenanceUrl,limitations
```

Upload response:

```json
{
  "prediction_set_id": 456,
  "inserted_count": 4,
  "rejected_count": 0,
  "validation_status": "valid_for_snapshot",
  "matched_dataset_snapshot_id": 123,
  "models": [],
  "predictions": [],
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

Prediction set item:

```json
{
  "id": 456,
  "benchmark_dataset_snapshot_id": 123,
  "model_id": "team_model_v1",
  "model_name": "Team Model v1",
  "country_iso3": "USA",
  "source_id": "fixture_forecast_source",
  "metric": "aggregate_signal",
  "unit": "index",
  "validation_status": "valid_for_snapshot",
  "row_count": 4,
  "warnings": [],
  "limitations": [],
  "points": []
}
```

The backend accepts prediction values only. It rejects executable model artifacts and CSV fields that look like PII, medical records, or operational trace data.

## Forecast Benchmarks

Calls:

```text
POST /api/forecast-benchmarks/preview
POST /api/forecast-benchmarks
GET /api/forecast-benchmarks/{id}
GET /api/countries/{iso3}/forecast-benchmarks
```

Backward-compatible request:

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

Snapshot request:

```json
{
  "dataset_snapshot_id": 123,
  "model_ids": ["naive_last_value", "statsmodels_arima"],
  "uploaded_prediction_set_ids": [456]
}
```

Response:

```json
{
  "id": null,
  "dataset_snapshot_id": 123,
  "country_iso3": "USA",
  "source_id": "fixture_forecast_source",
  "metric": "aggregate_signal",
  "unit": "index",
  "frequency": "weekly",
  "horizon_periods": 4,
  "requested_model_ids": ["naive_last_value", "team_model_v1"],
  "uploaded_prediction_set_ids": [456],
  "output_status": "complete",
  "explanation": "Historical holdout benchmark completed using a fixed aggregate dataset snapshot.",
  "leaderboard": [
    {
      "rank": 1,
      "model_id": "team_model_v1",
      "display_name": "Team Model v1",
      "result_type": "uploaded_prediction_csv",
      "status": "complete",
      "mae": 1.2,
      "rmse": 1.8,
      "smape": 7.4,
      "n_train": null,
      "n_test": 4,
      "benchmark_note": "Historical holdout performance is not proof of future public-health validity."
    }
  ],
  "comparison_points": [
    {
      "target_date": "2025-05-25",
      "observed_value": 34.5,
      "unit": "index",
      "predictions": [
        {
          "model_id": "naive_last_value",
          "display_name": "Naive last value",
          "result_type": "builtin_model",
          "predicted_value": 32.0,
          "lower": null,
          "upper": null
        }
      ]
    }
  ],
  "dataset_snapshot": {
    "id": 123,
    "target_dates": ["2025-05-25", "2025-06-01", "2025-06-08", "2025-06-15"],
    "dataset_hash": "sha256..."
  },
  "results": []
}
```

Forecast benchmark values are historical metric evaluations over a holdout window. They must not be presented as public-health alerts, risk scores, Rt/R0 estimates, or operational guidance. If no matching stored observations exist, preview returns `output_status: "insufficient_data"` and create returns HTTP 400. Model-specific statuses include `complete`, `insufficient_data`, `model_unavailable`, `experimental_disabled`, `invalid_predictions`, and `failed`.

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
