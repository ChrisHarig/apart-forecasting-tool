from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
import csv
import hashlib
import importlib.util
from io import StringIO
from math import isfinite, sqrt
from statistics import mean
from typing import Iterable, Mapping

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.utils import ensure_country
from app.config import get_settings
from app.db import models
from app.schemas.forecast import (
    ForecastBenchmarkDatasetPreview,
    ForecastBenchmarkDatasetRead,
    ForecastBenchmarkDatasetRequest,
    ForecastBenchmarkPointRead,
    ForecastBenchmarkRead,
    ForecastBenchmarkRequest,
    ForecastBenchmarkResultRead,
    ForecastModelRead,
    ForecastPredictionTemplateRow,
    ForecastPredictionUploadResult,
    UploadedForecastPredictionRead,
    UploadedPredictionPointRead,
    UploadedPredictionSetRead,
)
from app.services.normalization import (
    AGGREGATE_ONLY_REJECT_FIELDS,
    OPERATIONAL_TRACE_WARNING_FIELDS,
    NormalizationError,
    coerce_date,
    coerce_float,
    normalize_iso3,
    serializable,
)
from app.services.submissions import normalize_submitter_metadata
from app.services.experimental_tabpfn_ts import (
    MIN_TRAIN_POINTS as TABPFN_MIN_TRAIN_POINTS,
    MODEL_ID as EXPERIMENTAL_TABPFN_TS_MODEL_ID,
    forecast_with_tabpfn_ts,
    get_tabpfn_dependency_status,
)


BENCHMARK_WARNING = {
    "code": "benchmark_only",
    "message": "Forecast benchmark outputs are historical metric evaluations only, not public-health alerts, risk scores, Rt/R0 estimates, or operational guidance.",
    "severity": "warning",
}

FAIRNESS_WARNING = {
    "code": "external_training_not_verifiable",
    "message": "Sentinel Atlas can enforce the scoring dates and observations, but cannot prove an external model did not train on holdout values.",
    "severity": "warning",
}

BENCHMARK_LIMITATIONS = [
    "Benchmarks use stored aggregate observations only.",
    "Built-in baselines are proof-of-concept forecasting references, not validated public-health prediction systems.",
    "Missing, short, or sparse series are returned as insufficient_data instead of fabricated outputs.",
    "Historical holdout performance is not proof of future public-health validity.",
]

SNAPSHOT_LIMITATIONS = [
    "Benchmark dataset snapshots do not pad, interpolate, or fabricate missing observation dates.",
    "Target dates are the exact stored holdout observation dates selected by the split strategy.",
]

REGISTRY_VERSION = "forecast-benchmark-registry-v3-2026-04-26"
SUPPORTED_FREQUENCIES = ("daily", "weekly", "monthly")
FREQUENCY_TO_PANDAS = {"daily": "D", "weekly": "W", "monthly": "MS"}
DEFAULT_SPLIT_STRATEGY = "last_n_periods"
MIN_TRAIN_POINTS = 8
MIN_TEST_POINTS = 2

EXECUTABLE_UPLOAD_SUFFIXES = (
    ".py",
    ".ipynb",
    ".pkl",
    ".pickle",
    ".joblib",
    ".onnx",
    ".pt",
    ".pth",
    ".h5",
    ".keras",
    ".bin",
    ".tar",
    ".zip",
    ".sh",
    ".bat",
    ".cmd",
    ".ps1",
)

EXECUTABLE_MODEL_REJECT_FIELDS = frozenset(
    {
        "code",
        "model_code",
        "python_code",
        "script",
        "shell_command",
        "command",
        "cmd",
        "dockerfile",
        "docker_image",
        "container_image",
        "model_binary",
        "model_artifact",
        "pickle",
        "joblib",
        "notebook",
        "model_url",
        "artifact_url",
        "execute_url",
        "remote_inference_url",
        "huggingface_token",
        "api_token",
    }
)


@dataclass(frozen=True)
class BuiltinForecastModel:
    id: str
    name: str
    model_kind: str
    model_family: str
    implementation_source: str
    description: str
    min_train_points: int
    limitations: tuple[str, ...]
    supported_frequencies: tuple[str, ...] = SUPPORTED_FREQUENCIES
    required_frequency_notes: str = "Uses the benchmark dataset snapshot frequency after duplicate observation dates are aggregated by mean."
    supports_prediction_intervals: str = "false"
    default_parameters: Mapping[str, object] | None = None
    safety_notes: tuple[str, ...] = (
        "Benchmark-only metric forecast; not a public-health alert or validated epidemiological prediction.",
        "Uses stored aggregate observations only.",
        "Uploaded executable model code is never accepted.",
    )
    citation_or_package_notes: str | None = None
    dependency_name: str | None = None
    warnings: tuple[str, ...] = ()
    status: str = "builtin"
    experimental: bool = False
    enabled_by_default: bool = True


@dataclass(frozen=True)
class SnapshotData:
    read: ForecastBenchmarkDatasetRead
    train: list[tuple[date, float]]
    test: list[tuple[date, float]]
    train_rows: list[dict[str, object]]
    test_rows: list[dict[str, object]]


BUILTIN_MODELS: dict[str, BuiltinForecastModel] = {
    "naive_last_value": BuiltinForecastModel(
        id="naive_last_value",
        name="Naive last value",
        model_kind="builtin_baseline",
        model_family="naive_baseline",
        implementation_source="sentinel_atlas_backend",
        description="Repeats the latest training value across the holdout window.",
        min_train_points=1,
        limitations=("Baseline only; useful as a simple benchmark floor.",),
        default_parameters={"strategy": "last_observed_training_value"},
    ),
    "seasonal_naive": BuiltinForecastModel(
        id="seasonal_naive",
        name="Seasonal naive",
        model_kind="builtin_baseline",
        model_family="naive_baseline",
        implementation_source="sentinel_atlas_backend",
        description="Repeats the most recent seasonal pattern across the holdout window.",
        min_train_points=4,
        limitations=("Requires at least one full default season in the training window.",),
        default_parameters={"daily_season_length": 7, "weekly_season_length": 4, "monthly_season_length": 12},
    ),
    "statsmodels_arima": BuiltinForecastModel(
        id="statsmodels_arima",
        name="Statsmodels ARIMA",
        model_kind="builtin_statsmodels",
        model_family="arima",
        implementation_source="statsmodels",
        description="ARIMA(1,0,0) baseline fitted with statsmodels.",
        min_train_points=8,
        limitations=("Small-sample ARIMA fits may be unstable and are benchmark references only.",),
        default_parameters={"order": [1, 0, 0]},
        citation_or_package_notes="Uses the open-source statsmodels package.",
        dependency_name="statsmodels",
    ),
    "statsmodels_sarima": BuiltinForecastModel(
        id="statsmodels_sarima",
        name="Statsmodels SARIMA",
        model_kind="builtin_statsmodels",
        model_family="sarima",
        implementation_source="statsmodels",
        description="SARIMA baseline fitted with statsmodels using the default seasonal length.",
        min_train_points=12,
        limitations=("Requires at least two seasons plus extra history; small-sample seasonal fits may be unstable.",),
        default_parameters={"order": [1, 0, 0], "seasonal_order": [1, 0, 0, "season_length"]},
        citation_or_package_notes="Uses the open-source statsmodels package.",
        dependency_name="statsmodels",
    ),
    "statsforecast_autoets": BuiltinForecastModel(
        id="statsforecast_autoets",
        name="StatsForecast AutoETS",
        model_kind="builtin_statsforecast",
        model_family="exponential_smoothing_ets",
        implementation_source="statsforecast",
        description="AutoETS benchmark fitted with the open-source Nixtla StatsForecast package.",
        min_train_points=8,
        limitations=(
            "Statistical time-series benchmark only; not an epidemiological model, public-health alert, or validated pandemic prediction.",
            "Requires stored aggregate observations and enough history after the holdout split.",
            "Seasonality is disabled when there are not enough observed cycles.",
        ),
        required_frequency_notes=(
            "Uses daily, weekly, or monthly benchmark frequency. Seasonality is enabled only when at least two observed cycles exist."
        ),
        supports_prediction_intervals="unknown",
        default_parameters={"model": "AutoETS", "season_length": "1 unless enough observed seasonal cycles exist"},
        citation_or_package_notes="Uses Nixtla StatsForecast AutoETS if the optional `statsforecast` dependency is installed.",
        dependency_name="statsforecast",
    ),
    EXPERIMENTAL_TABPFN_TS_MODEL_ID: BuiltinForecastModel(
        id=EXPERIMENTAL_TABPFN_TS_MODEL_ID,
        name="Experimental TabPFN-Time-Series",
        model_kind="builtin_experimental",
        model_family="foundation_time_series_experimental",
        implementation_source="tabpfn-time-series",
        description=(
            "Experimental TabPFN-Time-Series benchmark run only on stored aggregate challenge snapshots "
            "when explicitly requested and feature-flag enabled."
        ),
        min_train_points=TABPFN_MIN_TRAIN_POINTS,
        limitations=(
            "Experimental statistical/foundation time-series benchmark only; not an epidemiological model, public-health alert, or validated pandemic prediction.",
            "Disabled by default and only runnable when SENTINEL_ENABLE_EXPERIMENTAL_TABPFN=true.",
            "Requires the optional tabpfn-time-series dependency and a supported local no-remote inference path.",
            "Uses stored aggregate observations only and never executes uploaded model code.",
        ),
        required_frequency_notes=(
            "Uses exact daily, weekly, or monthly challenge target dates. Irregular or short series are returned as insufficient_data."
        ),
        supports_prediction_intervals="false",
        default_parameters={"minimum_train_points": TABPFN_MIN_TRAIN_POINTS, "telemetry": "disabled by default"},
        safety_notes=(
            "Experimental statistical/foundation time-series benchmark only.",
            "Not a validated epidemiological model.",
            "Not a public-health alert.",
            "No user model code is executed.",
            "No remote inference is used by default.",
        ),
        citation_or_package_notes="Optional experimental dependency: tabpfn-time-series.",
        dependency_name="tabpfn_time_series",
        warnings=("Experimental model is disabled by default and excluded from default benchmark runs.",),
        status="experimental",
        experimental=True,
        enabled_by_default=False,
    ),
}


def list_forecast_models(db: Session, *, include_experimental: bool = False) -> list[ForecastModelRead]:
    uploaded = db.execute(select(models.ForecastModel).order_by(models.ForecastModel.name)).scalars().all()
    uploaded_by_id = {model.id: model for model in uploaded}
    output = [
        _builtin_model_read(model)
        for model in BUILTIN_MODELS.values()
        if include_experimental or not model.experimental
    ]
    output.extend(_db_model_read(model) for model_id, model in uploaded_by_id.items() if model_id not in BUILTIN_MODELS)
    return output


def get_forecast_model(db: Session, model_id: str) -> ForecastModelRead | None:
    if model_id in BUILTIN_MODELS:
        return _builtin_model_read(BUILTIN_MODELS[model_id])
    model = db.get(models.ForecastModel, model_id)
    if model is None:
        return None
    return _db_model_read(model)


def default_builtin_model_ids() -> list[str]:
    return [
        model.id
        for model in BUILTIN_MODELS.values()
        if model.enabled_by_default
        and (model.id != "statsforecast_autoets" or _dependency_status(model) == "available")
    ]


def is_experimental_tabpfn_enabled() -> bool:
    return bool(get_settings().enable_experimental_tabpfn)


def parse_prediction_csv(content: str) -> list[dict[str, str]]:
    reader = csv.DictReader(StringIO(content))
    if not reader.fieldnames:
        raise NormalizationError("CSV upload must include a header row")
    return [dict(row) for row in reader]


def reject_executable_prediction_filename(filename: str | None) -> None:
    if not filename:
        return
    lower = filename.lower()
    if any(lower.endswith(suffix) for suffix in EXECUTABLE_UPLOAD_SUFFIXES):
        raise NormalizationError("Executable model artifacts are not accepted. Only aggregate prediction CSVs are accepted.")
    if not lower.endswith(".csv"):
        raise NormalizationError("Only aggregate prediction CSVs are accepted.")


def upload_forecast_predictions(
    db: Session,
    content: str,
    *,
    benchmark_dataset_snapshot_id: int | None = None,
    country_iso3: str | None = None,
    source_id: str | None = None,
    metric: str | None = None,
    unit: str | None = None,
    model_id: str | None = None,
    model_name: str | None = None,
    frequency: str | None = None,
    horizon_periods: int | None = None,
    user_notes: str | None = None,
    submitter_name: str | None = None,
    submitter_email: str | None = None,
    organization: str | None = None,
    submission_track: str | None = None,
    method_summary: str | None = None,
    model_url: str | None = None,
    code_url: str | None = None,
    provenance_url: str | None = None,
    visibility: str | None = None,
    disclosure_notes: str | None = None,
    verified_group: bool = False,
) -> ForecastPredictionUploadResult:
    snapshot = _get_snapshot_row(db, benchmark_dataset_snapshot_id) if benchmark_dataset_snapshot_id else None
    has_submission_metadata = any(
        value not in (None, "")
        for value in (
            submitter_name,
            submitter_email,
            organization,
            submission_track,
            method_summary,
            model_url,
            code_url,
            provenance_url,
            visibility,
            disclosure_notes,
        )
    ) or verified_group
    submitter_metadata = normalize_submitter_metadata(
        db,
        submitter_name=submitter_name,
        submitter_email=submitter_email,
        organization=organization,
        submission_track=submission_track,
        method_summary=method_summary,
        model_url=model_url,
        code_url=code_url,
        provenance_url=provenance_url,
        visibility=visibility,
        disclosure_notes=disclosure_notes,
        verified_group=verified_group,
        allow_missing_submitter=not has_submission_metadata,
    )
    defaults = _prediction_defaults_from_snapshot(snapshot)
    defaults.update(
        {
            key: value
            for key, value in {
                "country_iso3": country_iso3,
                "source_id": source_id,
                "metric": metric,
                "unit": unit,
                "model_id": model_id,
                "model_name": model_name,
                "frequency": frequency,
                "horizon_periods": horizon_periods,
            }.items()
            if value not in (None, "")
        }
    )

    raw_rows = parse_prediction_csv(content)
    normalized_rows: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []

    for index, row in enumerate(raw_rows, start=2):
        try:
            normalized_rows.append(normalize_prediction_upload_row(row, defaults=defaults))
        except NormalizationError as exc:
            errors.append({"row": index, "error": str(exc)})

    if errors or not normalized_rows:
        return ForecastPredictionUploadResult(
            inserted_count=0,
            rejected_count=len(errors) if errors else len(raw_rows),
            validation_status="invalid",
            errors=errors or [{"error": "No valid aggregate prediction rows were supplied."}],
            warnings=[BENCHMARK_WARNING],
        )

    consistency_errors = _validate_prediction_set_consistency(normalized_rows)
    if consistency_errors:
        return ForecastPredictionUploadResult(
            inserted_count=0,
            rejected_count=len(normalized_rows),
            validation_status="invalid",
            errors=consistency_errors,
            warnings=[BENCHMARK_WARNING],
        )

    snapshot_errors: list[dict[str, object]] = []
    validation_status = "stored_unmatched"
    if snapshot is not None:
        snapshot_errors = validate_prediction_dates_against_snapshot(normalized_rows, _snapshot_data_from_row(snapshot))
        validation_status = "valid_for_snapshot" if not snapshot_errors else "invalid"
    if snapshot_errors:
        return ForecastPredictionUploadResult(
            inserted_count=0,
            rejected_count=len(normalized_rows),
            validation_status="invalid",
            matched_dataset_snapshot_id=snapshot.id,
            errors=snapshot_errors,
            warnings=[BENCHMARK_WARNING],
        )

    first = normalized_rows[0]
    country = str(first["country_iso3"])
    ensure_country(db, country)
    model = _ensure_uploaded_forecast_model(db, first)

    dates = sorted(row["target_date"] for row in normalized_rows)
    prediction_set = models.UploadedPredictionSet(
        benchmark_dataset_snapshot_id=snapshot.id if snapshot else None,
        model_id=str(first["model_id"]),
        model_name=str(first["model_name"]),
        country_iso3=country,
        source_id=str(first["source_id"]),
        metric=str(first["metric"]),
        unit=first["unit"],
        frequency=str(defaults.get("frequency") or snapshot.frequency) if snapshot or defaults.get("frequency") else None,
        horizon_periods=int(defaults.get("horizon_periods") or snapshot.horizon_periods)
        if snapshot or defaults.get("horizon_periods")
        else None,
        target_start=dates[0],
        target_end=dates[-1],
        provenance_url=submitter_metadata.provenance_url or first["provenance_url"],
        user_notes=user_notes,
        validation_status=validation_status,
        submitter_id=submitter_metadata.submitter_id,
        submitter_name=submitter_metadata.submitter_name,
        submitter_email=submitter_metadata.submitter_email,
        organization=submitter_metadata.organization,
        submission_track=submitter_metadata.submission_track,
        review_status=submitter_metadata.review_status,
        visibility=submitter_metadata.visibility,
        method_summary=submitter_metadata.method_summary,
        model_url=submitter_metadata.model_url,
        code_url=submitter_metadata.code_url,
        disclosure_notes=submitter_metadata.disclosure_notes,
        limitations_json=first["limitations"],
        validation_warnings_json=[
            *([FAIRNESS_WARNING] if validation_status == "valid_for_snapshot" else []),
            *submitter_metadata.warnings,
        ],
        validation_errors_json=[],
    )
    db.add(prediction_set)
    db.flush()

    inserted_old_points: list[models.UploadedForecastPredictionPoint] = []
    inserted_points: list[models.UploadedPredictionPoint] = []
    for row in normalized_rows:
        point = models.UploadedPredictionPoint(
            prediction_set_id=prediction_set.id,
            target_date=row["target_date"],
            predicted_value=row["predicted_value"],
            lower=row["lower"],
            upper=row["upper"],
            unit=row["unit"],
            generated_at=row["generated_at"],
            provenance_url=row["provenance_url"],
        )
        old_point = models.UploadedForecastPredictionPoint(
            model_id=model.id,
            country_iso3=country,
            source_id=str(row["source_id"]),
            metric=str(row["metric"]),
            unit=row["unit"],
            target_date=row["target_date"],
            predicted_value=row["predicted_value"],
            lower=row["lower"],
            upper=row["upper"],
            generated_at=row["generated_at"],
            provenance_url=row["provenance_url"],
            limitations=row["limitations"],
        )
        db.add(point)
        db.add(old_point)
        inserted_points.append(point)
        inserted_old_points.append(old_point)

    db.commit()
    db.refresh(prediction_set)
    db.refresh(model)
    for point in inserted_points:
        db.refresh(point)
    for point in inserted_old_points:
        db.refresh(point)

    return ForecastPredictionUploadResult(
        prediction_set_id=prediction_set.id,
        inserted_count=len(inserted_points),
        rejected_count=0,
        validation_status=validation_status,
        matched_dataset_snapshot_id=snapshot.id if snapshot else None,
        models=[_db_model_read(model)],
        predictions=[UploadedForecastPredictionRead.model_validate(point) for point in inserted_old_points],
        errors=[],
        warnings=[BENCHMARK_WARNING, *prediction_set.validation_warnings_json],
    )


def normalize_prediction_upload_row(
    raw: Mapping[str, object],
    *,
    defaults: Mapping[str, object] | None = None,
) -> dict[str, object]:
    defaults = defaults or {}
    lower_fields = {_normalize_field_name(field) for field in raw.keys()}
    compact_fields = {field.replace("_", "") for field in lower_fields}
    unsafe_lookup = set(AGGREGATE_ONLY_REJECT_FIELDS) | {field.replace("_", "") for field in AGGREGATE_ONLY_REJECT_FIELDS}
    trace_lookup = set(OPERATIONAL_TRACE_WARNING_FIELDS) | {
        field.replace("_", "") for field in OPERATIONAL_TRACE_WARNING_FIELDS
    }
    executable_lookup = set(EXECUTABLE_MODEL_REJECT_FIELDS) | {
        field.replace("_", "") for field in EXECUTABLE_MODEL_REJECT_FIELDS
    }
    unsafe_fields = sorted((lower_fields | compact_fields).intersection(unsafe_lookup))
    trace_fields = sorted((lower_fields | compact_fields).intersection(trace_lookup))
    executable_fields = sorted((lower_fields | compact_fields).intersection(executable_lookup))
    if unsafe_fields:
        raise NormalizationError(
            "Individual-level, PII, medical-record, or precise trace fields are not accepted: "
            + ", ".join(unsafe_fields)
        )
    if trace_fields:
        raise NormalizationError(
            "Operational trace-level fields are not accepted in forecast prediction uploads: "
            + ", ".join(trace_fields)
        )
    if executable_fields:
        raise NormalizationError(
            "Only aggregate prediction CSVs are accepted. Executable model artifacts are not accepted: "
            + ", ".join(executable_fields)
        )

    model_id = _clean_text(_first_value(raw, ("modelId", "model_id"))) or _clean_text(defaults.get("model_id"))
    model_name = (
        _clean_text(_first_value(raw, ("modelName", "model_name")))
        or _clean_text(defaults.get("model_name"))
        or model_id
    )
    country = normalize_iso3(
        _first_value(raw, ("countryIso3", "country_iso3", "iso3", "country")) or defaults.get("country_iso3")
    )
    source_id = _clean_text(_first_value(raw, ("sourceId", "source_id", "source")) or defaults.get("source_id"))
    metric = _clean_text(_first_value(raw, ("metric", "measure", "indicator", "signal")) or defaults.get("metric"))
    target_date = coerce_date(_first_value(raw, ("targetDate", "target_date", "date")))
    predicted_value = coerce_float(_first_value(raw, ("predictedValue", "predicted_value", "value")))
    generated_at = _coerce_datetime(_first_value(raw, ("generatedAt", "generated_at")))
    unit = _clean_text(raw.get("unit") or defaults.get("unit"))

    missing = []
    if not model_id:
        missing.append("modelId")
    if not model_name:
        missing.append("modelName")
    if not country or country == "GLOBAL":
        missing.append("countryIso3")
    if not source_id:
        missing.append("sourceId")
    if not metric:
        missing.append("metric")
    if target_date is None:
        missing.append("targetDate")
    if predicted_value is None:
        missing.append("predictedValue")
    if missing:
        raise NormalizationError("Missing or invalid required fields: " + ", ".join(missing))

    return {
        "model_id": model_id,
        "model_name": model_name,
        "country_iso3": country,
        "source_id": source_id,
        "metric": metric,
        "unit": unit,
        "target_date": target_date,
        "predicted_value": predicted_value,
        "lower": coerce_float(raw.get("lower")),
        "upper": coerce_float(raw.get("upper")),
        "generated_at": generated_at,
        "provenance_url": _clean_text(_first_value(raw, ("provenanceUrl", "provenance_url", "sourceUrl"))),
        "limitations": _string_list(raw.get("limitations")),
    }


def preview_benchmark_dataset(
    db: Session,
    request: ForecastBenchmarkDatasetRequest,
) -> ForecastBenchmarkDatasetPreview:
    data = build_benchmark_dataset_snapshot(db, request)
    return ForecastBenchmarkDatasetPreview(
        dataset_snapshot=data.read,
        train_preview=data.train_rows[:10],
        target_template=build_prediction_template_from_data(data),
    )


def create_benchmark_dataset(
    db: Session,
    request: ForecastBenchmarkDatasetRequest,
) -> ForecastBenchmarkDatasetRead:
    data = build_benchmark_dataset_snapshot(db, request)
    row = _persist_snapshot_data(db, data)
    return _dataset_read_from_row(row)


def get_benchmark_dataset(db: Session, dataset_snapshot_id: int) -> ForecastBenchmarkDatasetRead | None:
    row = db.get(models.ForecastBenchmarkDatasetSnapshot, dataset_snapshot_id)
    return _dataset_read_from_row(row) if row else None


def get_prediction_template(
    db: Session,
    dataset_snapshot_id: int,
) -> list[ForecastPredictionTemplateRow]:
    snapshot = _get_snapshot_row(db, dataset_snapshot_id)
    return build_prediction_template_from_data(_snapshot_data_from_row(snapshot))


def build_benchmark_dataset_snapshot(
    db: Session,
    request: ForecastBenchmarkDatasetRequest,
) -> SnapshotData:
    country = _validate_country(request.country_iso3)
    frequency = _validate_frequency(request.frequency)
    horizon = _validate_horizon(request.horizon_periods)
    split_strategy = _validate_split_strategy(request.split_strategy)
    ensure_country(db, country)

    rows = _query_observation_rows(db, request, country)
    warnings = _snapshot_diagnostics(db, request, rows, frequency)
    train_rows, test_rows = split_train_test(rows, horizon)
    status = "ready" if len(train_rows) >= MIN_TRAIN_POINTS and len(test_rows) >= MIN_TEST_POINTS else "insufficient_data"
    if status == "insufficient_data":
        warnings.append(
            {
                "code": "insufficient_data",
                "message": f"Need at least {MIN_TRAIN_POINTS} training observations and {MIN_TEST_POINTS} holdout observations for a benchmark snapshot.",
                "severity": "warning",
            }
        )

    train = [(row["date"], float(row["value"])) for row in train_rows]
    test = [(row["date"], float(row["value"])) for row in test_rows]
    dataset_hash = compute_dataset_hash(rows, request, country, frequency, horizon, split_strategy)
    provenance_urls = sorted({url for row in rows for url in row["provenance_urls"] if url})
    read = ForecastBenchmarkDatasetRead(
        country_iso3=country,
        source_id=request.source_id,
        signal_category=request.signal_category,
        metric=request.metric,
        unit=request.unit,
        frequency=frequency,
        horizon_periods=horizon,
        split_strategy=split_strategy,
        train_start=train[0][0] if train else None,
        train_end=train[-1][0] if train else None,
        test_start=test[0][0] if test else None,
        test_end=test[-1][0] if test else None,
        target_dates=[day for day, _value in test],
        observation_ids=[obs_id for row in rows for obs_id in row["observation_ids"]],
        train_observation_ids=[obs_id for row in train_rows for obs_id in row["observation_ids"]],
        test_observation_ids=[obs_id for row in test_rows for obs_id in row["observation_ids"]],
        n_train=len(train_rows),
        n_test=len(test_rows),
        dataset_hash=dataset_hash,
        status=status,
        warnings=warnings,
        limitations=SNAPSHOT_LIMITATIONS,
        provenance={
            "observation_count": sum(len(row["observation_ids"]) for row in rows),
            "source_id": request.source_id,
            "provenance_urls": provenance_urls[:10],
        },
        created_at=datetime.now(UTC),
    )
    return SnapshotData(read=read, train=train, test=test, train_rows=train_rows, test_rows=test_rows)


def compute_dataset_hash(
    rows: list[dict[str, object]],
    request: ForecastBenchmarkDatasetRequest,
    country: str,
    frequency: str,
    horizon: int,
    split_strategy: str,
) -> str:
    payload = {
        "country_iso3": country,
        "source_id": request.source_id,
        "signal_category": request.signal_category,
        "metric": request.metric,
        "unit": request.unit,
        "frequency": frequency,
        "horizon_periods": horizon,
        "split_strategy": split_strategy,
        "start_date": request.start_date.isoformat() if request.start_date else None,
        "end_date": request.end_date.isoformat() if request.end_date else None,
        "rows": [
            {
                "date": row["date"].isoformat(),
                "value": row["value"],
                "observation_ids": row["observation_ids"],
            }
            for row in rows
        ],
    }
    return hashlib.sha256(str(serializable(payload)).encode("utf-8")).hexdigest()


def split_train_test(
    rows: list[dict[str, object]],
    horizon_periods: int,
    split_strategy: str = DEFAULT_SPLIT_STRATEGY,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if split_strategy != DEFAULT_SPLIT_STRATEGY:
        raise ValueError("split_strategy must be last_n_periods")
    if not rows:
        return [], []
    n_test = min(horizon_periods, len(rows))
    return rows[:-n_test], rows[-n_test:]


def validate_regular_frequency(rows: list[dict[str, object]], frequency: str) -> bool:
    series = [(row["date"], float(row["value"])) for row in rows]
    return not _has_irregular_dates(series, frequency)


def build_prediction_template_from_data(data: SnapshotData) -> list[ForecastPredictionTemplateRow]:
    return [
        ForecastPredictionTemplateRow(
            target_date=day,
            model_id=None,
            model_name=None,
            country_iso3=data.read.country_iso3,
            source_id=data.read.source_id,
            metric=data.read.metric,
            predicted_value=None,
            unit=data.read.unit,
        )
        for day, _value in data.test
    ]


def validate_prediction_dates_against_snapshot(
    predictions: Iterable[Mapping[str, object]] | models.UploadedPredictionSet,
    snapshot: SnapshotData,
) -> list[dict[str, object]]:
    if isinstance(predictions, models.UploadedPredictionSet):
        rows = [
            {
                "country_iso3": predictions.country_iso3,
                "source_id": predictions.source_id,
                "metric": predictions.metric,
                "unit": predictions.unit,
                "target_date": point.target_date,
            }
            for point in predictions.points
        ]
    else:
        rows = list(predictions)

    errors: list[dict[str, object]] = []
    if not rows:
        return [{"code": "invalid_predictions", "message": "Prediction set contains no rows."}]

    first = rows[0]
    if first.get("country_iso3") != snapshot.read.country_iso3:
        errors.append({"code": "wrong_country", "message": "Prediction country does not match the benchmark snapshot."})
    if first.get("source_id") != snapshot.read.source_id:
        errors.append({"code": "wrong_source", "message": "Prediction source does not match the benchmark snapshot."})
    if first.get("metric") != snapshot.read.metric:
        errors.append({"code": "wrong_metric", "message": "Prediction metric does not match the benchmark snapshot."})
    if snapshot.read.unit is not None and first.get("unit") not in (snapshot.read.unit, None, ""):
        errors.append({"code": "wrong_unit", "message": "Prediction unit does not match the benchmark snapshot."})

    expected = {day.isoformat() for day in snapshot.read.target_dates}
    supplied = {row["target_date"].isoformat() if isinstance(row["target_date"], date) else str(row["target_date"]) for row in rows}
    missing = sorted(expected - supplied)
    extra = sorted(supplied - expected)
    if missing:
        errors.append({"code": "missing_target_dates", "message": "Prediction CSV is missing snapshot target dates.", "dates": missing})
    if extra:
        errors.append({"code": "extra_target_dates", "message": "Prediction CSV includes dates outside the snapshot holdout.", "dates": extra})
    return errors


def preview_forecast_benchmark(db: Session, request: ForecastBenchmarkRequest) -> ForecastBenchmarkRead:
    snapshot = _snapshot_for_benchmark_request(db, request, persist=False)
    return _evaluate_benchmark(db, request, snapshot, created_at=datetime.now(UTC))


def create_forecast_benchmark(db: Session, request: ForecastBenchmarkRequest) -> ForecastBenchmarkRead:
    snapshot = _snapshot_for_benchmark_request(db, request, persist=True)
    if not snapshot.test:
        raise ValueError("No matching stored aggregate observations were found")
    preview = _evaluate_benchmark(db, request, snapshot, created_at=datetime.now(UTC))
    run = models.ForecastBenchmarkRun(
        dataset_snapshot_id=preview.dataset_snapshot_id,
        country_iso3=preview.country_iso3,
        source_id=preview.source_id,
        metric=preview.metric,
        unit=preview.unit,
        frequency=preview.frequency,
        horizon_periods=preview.horizon_periods,
        train_start=preview.train_start,
        train_end=preview.train_end,
        requested_model_ids=preview.requested_model_ids,
        uploaded_prediction_set_ids=preview.uploaded_prediction_set_ids,
        output_status=preview.output_status,
        explanation=preview.explanation,
        warnings=preview.warnings,
        limitations=preview.limitations,
        comparison=serializable(preview.leaderboard),
        data_quality_notes=preview.data_quality_notes,
        created_at=preview.created_at,
    )
    db.add(run)
    db.flush()

    for result in preview.results:
        result_row = models.ForecastBenchmarkResult(
            dataset_snapshot_id=preview.dataset_snapshot_id,
            model_id=result.model_id,
            model_name=result.model_name,
            model_kind=result.model_kind,
            result_type=result.result_type,
            status=result.status,
            mae=result.mae,
            rmse=result.rmse,
            smape=result.smape,
            n_train=result.n_train or 0,
            n_test=result.n_test,
            train_start=result.train_start,
            train_end=result.train_end,
            test_start=result.test_start,
            test_end=result.test_end,
            rank=result.rank,
            provenance_url=result.provenance_url,
            warnings=result.warnings,
            limitations=result.limitations,
            data_quality_notes=result.data_quality_notes,
            metadata_json=result.metadata,
        )
        for point in result.points:
            result_row.points.append(
                models.ForecastBenchmarkPredictionPoint(
                    date=point.date,
                    observed_value=point.observed_value,
                    predicted_value=point.predicted_value,
                    lower=point.lower,
                    upper=point.upper,
                    absolute_error=point.absolute_error,
                    percentage_error=point.percentage_error,
                    unit=point.unit,
                )
            )
        run.results.append(result_row)

    db.commit()
    saved = _get_benchmark_run(db, run.id)
    return _run_to_read(saved)


def get_forecast_benchmark(db: Session, run_id: int) -> ForecastBenchmarkRead | None:
    run = _get_benchmark_run(db, run_id, required=False)
    return _run_to_read(run) if run else None


def list_country_forecast_benchmarks(db: Session, country_iso3: str) -> list[ForecastBenchmarkRead]:
    country = _validate_country(country_iso3)
    runs = (
        db.execute(
            select(models.ForecastBenchmarkRun)
            .where(models.ForecastBenchmarkRun.country_iso3 == country)
            .options(
                selectinload(models.ForecastBenchmarkRun.dataset_snapshot),
                selectinload(models.ForecastBenchmarkRun.results).selectinload(models.ForecastBenchmarkResult.points),
            )
            .order_by(models.ForecastBenchmarkRun.created_at.desc(), models.ForecastBenchmarkRun.id.desc())
        )
        .scalars()
        .all()
    )
    return [_run_to_read(run) for run in runs]


def list_prediction_sets(
    db: Session,
    *,
    country_iso3: str | None = None,
    source_id: str | None = None,
    metric: str | None = None,
    dataset_snapshot_id: int | None = None,
    model_id: str | None = None,
) -> list[UploadedPredictionSetRead]:
    query = select(models.UploadedPredictionSet).options(selectinload(models.UploadedPredictionSet.points))
    if country_iso3:
        query = query.where(models.UploadedPredictionSet.country_iso3 == _validate_country(country_iso3))
    if source_id:
        query = query.where(models.UploadedPredictionSet.source_id == source_id)
    if metric:
        query = query.where(models.UploadedPredictionSet.metric == metric)
    if dataset_snapshot_id:
        query = query.where(models.UploadedPredictionSet.benchmark_dataset_snapshot_id == dataset_snapshot_id)
    if model_id:
        query = query.where(models.UploadedPredictionSet.model_id == model_id)
    rows = db.execute(query.order_by(models.UploadedPredictionSet.created_at.desc())).scalars().all()
    return [_prediction_set_read(row, include_points=False) for row in rows]


def get_prediction_set(db: Session, prediction_set_id: int) -> UploadedPredictionSetRead | None:
    row = _get_prediction_set_row(db, prediction_set_id, required=False)
    return _prediction_set_read(row, include_points=True) if row else None


def delete_prediction_set(db: Session, prediction_set_id: int) -> bool:
    row = _get_prediction_set_row(db, prediction_set_id, required=False)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def rank_benchmark_results(results: list[ForecastBenchmarkResultRead]) -> list[dict[str, object]]:
    def sort_key(result: ForecastBenchmarkResultRead) -> tuple[int, float, float, float, str]:
        complete_rank = 0 if result.status == "complete" else 1
        smape = result.smape if result.smape is not None else float("inf")
        rmse = result.rmse if result.rmse is not None else float("inf")
        mae = result.mae if result.mae is not None else float("inf")
        return (complete_rank, smape, rmse, mae, result.model_id)

    ranked = sorted(results, key=sort_key)
    output: list[dict[str, object]] = []
    rank = 1
    for result in ranked:
        is_complete = result.status == "complete"
        result.rank = rank if is_complete else None
        output.append(
            {
                "rank": result.rank,
                "model_id": result.model_id,
                "display_name": result.display_name or result.model_name,
                "result_type": result.result_type,
                "status": result.status,
                "mae": result.mae,
                "rmse": result.rmse,
                "smape": result.smape,
                "n_train": result.n_train,
                "n_test": result.n_test,
                "train_start": result.train_start,
                "train_end": result.train_end,
                "test_start": result.test_start,
                "test_end": result.test_end,
                "warnings": result.warnings,
                "limitations": result.limitations,
                "data_quality_notes": result.data_quality_notes,
                "benchmark_note": "Historical holdout performance is not proof of future public-health validity.",
            }
        )
        if is_complete:
            rank += 1
    return output


def _evaluate_benchmark(
    db: Session,
    request: ForecastBenchmarkRequest,
    snapshot: SnapshotData,
    *,
    created_at: datetime,
) -> ForecastBenchmarkRead:
    selected_model_ids = _selected_builtin_and_uploaded_model_ids(db, request, snapshot)
    data_quality_notes = list(snapshot.read.warnings)
    results: list[ForecastBenchmarkResultRead] = []

    for model_id in selected_model_ids:
        if model_id in BUILTIN_MODELS:
            results.append(
                _benchmark_builtin(
                    model_id,
                    snapshot.train,
                    snapshot.test,
                    snapshot.read.unit,
                    _legacy_season_length(snapshot.read.frequency),
                    snapshot.read.frequency,
                    data_quality_notes,
                    snapshot.read.id,
                )
            )
        else:
            matching_sets = _prediction_sets_for_model(db, model_id, request, snapshot)
            if not matching_sets:
                results.append(
                    _insufficient_result(
                        model_id,
                        "Model is not registered as a built-in model or compatible uploaded prediction set.",
                        n_train=len(snapshot.train),
                        n_test=len(snapshot.test),
                        train=snapshot.train,
                        test=snapshot.test,
                        data_quality_notes=data_quality_notes,
                        dataset_snapshot_id=snapshot.read.id,
                        result_type="uploaded_prediction_csv",
                    )
                )
            for prediction_set in matching_sets:
                results.append(_benchmark_prediction_set(prediction_set, snapshot, data_quality_notes))

    for prediction_set_id in request.uploaded_prediction_set_ids or []:
        if any(result.metadata.get("prediction_set_id") == prediction_set_id for result in results):
            continue
        prediction_set = _get_prediction_set_row(db, prediction_set_id, required=True)
        results.append(_benchmark_prediction_set(prediction_set, snapshot, data_quality_notes))

    output_status = _benchmark_output_status(results)
    leaderboard = rank_benchmark_results(results)
    comparison_points = _comparison_points(snapshot, results)
    uploaded_prediction_set_ids = [
        result.metadata["prediction_set_id"]
        for result in results
        if result.result_type == "uploaded_prediction_csv" and result.metadata.get("prediction_set_id")
    ]

    return ForecastBenchmarkRead(
        dataset_snapshot_id=snapshot.read.id,
        country_iso3=snapshot.read.country_iso3,
        source_id=snapshot.read.source_id,
        metric=snapshot.read.metric,
        unit=snapshot.read.unit,
        frequency=snapshot.read.frequency,
        horizon_periods=snapshot.read.horizon_periods,
        train_start=snapshot.read.train_start,
        train_end=snapshot.read.train_end,
        requested_model_ids=selected_model_ids,
        uploaded_prediction_set_ids=uploaded_prediction_set_ids,
        output_status=output_status,
        explanation=(
            "Historical holdout benchmark completed using a fixed aggregate dataset snapshot."
            if output_status == "complete"
            else "Historical holdout benchmark returned partial, unavailable, invalid, or insufficient model results from a fixed aggregate dataset snapshot."
        ),
        warnings=[BENCHMARK_WARNING],
        limitations=BENCHMARK_LIMITATIONS,
        comparison=leaderboard,
        leaderboard=leaderboard,
        comparison_points=comparison_points,
        data_quality_notes=data_quality_notes,
        dataset_snapshot=snapshot.read,
        benchmark_run={
            "id": None,
            "dataset_snapshot_id": snapshot.read.id,
            "country_iso3": snapshot.read.country_iso3,
            "source_id": snapshot.read.source_id,
            "metric": snapshot.read.metric,
            "frequency": snapshot.read.frequency,
            "horizon_periods": snapshot.read.horizon_periods,
            "status": output_status,
            "warnings": [BENCHMARK_WARNING],
            "limitations": BENCHMARK_LIMITATIONS,
            "explanation": "Historical holdout benchmark. Not a validated public-health prediction.",
        },
        created_at=created_at,
        results=results,
    )


def _benchmark_builtin(
    model_id: str,
    train: list[tuple[date, float]],
    test: list[tuple[date, float]],
    unit: str | None,
    season_length: int,
    frequency: str,
    data_quality_notes: list[dict[str, str]],
    dataset_snapshot_id: int | None,
) -> ForecastBenchmarkResultRead:
    model = BUILTIN_MODELS[model_id]
    min_train_points = max(model.min_train_points, season_length if model_id == "seasonal_naive" else model.min_train_points)
    if model_id == "statsmodels_sarima":
        min_train_points = max(model.min_train_points, (season_length * 2) + 4)
    if model_id == "statsforecast_autoets":
        min_train_points = model.min_train_points
        if len(test) < 2:
            return _insufficient_result(
                model_id,
                "Need at least 2 holdout observations for statsforecast_autoets.",
                n_train=len(train),
                n_test=len(test),
                train=train,
                test=test,
                data_quality_notes=data_quality_notes,
                dataset_snapshot_id=dataset_snapshot_id,
            )
    elif model_id == EXPERIMENTAL_TABPFN_TS_MODEL_ID:
        min_train_points = model.min_train_points
        if not is_experimental_tabpfn_enabled():
            return _model_unavailable_result(
                model,
                n_train=len(train),
                n_test=len(test),
                train=train,
                test=test,
                dataset_snapshot_id=dataset_snapshot_id,
                status="experimental_disabled",
                code="experimental_disabled",
                message=(
                    "Experimental TabPFN-Time-Series is disabled. Set "
                    "SENTINEL_ENABLE_EXPERIMENTAL_TABPFN=true to request this benchmark explicitly."
                ),
            )
        if _dependency_status(model) != "available":
            return _model_unavailable_result(
                model,
                n_train=len(train),
                n_test=len(test),
                train=train,
                test=test,
                dataset_snapshot_id=dataset_snapshot_id,
                code="missing_optional_dependency",
                message=(
                    "Experimental TabPFN-Time-Series requires the optional `tabpfn-time-series` dependency. "
                    "Install backend with `pip install -e \".[dev,experimental]\"`."
                ),
            )
    if len(train) < min_train_points:
        return _insufficient_result(
            model_id,
            f"Need at least {min_train_points} training points for {model_id}.",
            n_train=len(train),
            n_test=len(test),
            train=train,
            test=test,
            data_quality_notes=data_quality_notes,
            dataset_snapshot_id=dataset_snapshot_id,
        )

    try:
        if model_id == "naive_last_value":
            predictions = [train[-1][1]] * len(test)
            model_warnings = []
        elif model_id == "seasonal_naive":
            pattern = [value for _day, value in train[-season_length:]]
            predictions = [pattern[index % len(pattern)] for index in range(len(test))]
            model_warnings = []
        elif model_id == "statsmodels_arima":
            predictions = _forecast_arima([value for _day, value in train], len(test))
            model_warnings = []
        elif model_id == "statsmodels_sarima":
            predictions = _forecast_sarima([value for _day, value in train], len(test), season_length)
            model_warnings = []
        elif model_id == "statsforecast_autoets":
            dependency_status = _dependency_status(model)
            if dependency_status != "available":
                return _model_unavailable_result(
                    model,
                    n_train=len(train),
                    n_test=len(test),
                    train=train,
                    test=test,
                    dataset_snapshot_id=dataset_snapshot_id,
                )
            predictions, model_warnings = _forecast_autoets(train, len(test), frequency)
        elif model_id == EXPERIMENTAL_TABPFN_TS_MODEL_ID:
            target_dates = [day for day, _value in test]
            predictions, model_warnings = forecast_with_tabpfn_ts(train, target_dates, frequency)
        else:
            return _insufficient_result(
                model_id,
                "Unknown built-in model.",
                n_train=len(train),
                n_test=len(test),
                train=train,
                test=test,
                data_quality_notes=data_quality_notes,
                dataset_snapshot_id=dataset_snapshot_id,
            )
    except Exception as exc:  # statsmodels/statsforecast can raise data-shape or convergence exceptions.
        return _failed_result(
            model,
            str(exc),
            n_train=len(train),
            n_test=len(test),
            train=train,
            test=test,
            dataset_snapshot_id=dataset_snapshot_id,
        )

    return _complete_result(
        model_id=model.id,
        model_name=model.name,
        model_kind=model.model_kind,
        model_family=model.model_family,
        result_type="builtin_model",
        predictions=predictions,
        test=test,
        unit=unit,
        limitations=list(model.limitations),
        warnings=[
            BENCHMARK_WARNING,
            *({"code": "model_warning", "message": warning, "severity": "info"} for warning in model.warnings),
            *model_warnings,
        ],
        n_train=len(train),
        train=train,
        data_quality_notes=data_quality_notes,
        dataset_snapshot_id=dataset_snapshot_id,
    )


def _benchmark_prediction_set(
    prediction_set: models.UploadedPredictionSet,
    snapshot: SnapshotData,
    data_quality_notes: list[dict[str, str]],
) -> ForecastBenchmarkResultRead:
    errors = validate_prediction_dates_against_snapshot(prediction_set, snapshot)
    if errors:
        return ForecastBenchmarkResultRead(
            dataset_snapshot_id=snapshot.read.id,
            model_id=prediction_set.model_id,
            model_name=prediction_set.model_name,
            display_name=prediction_set.model_name,
            model_kind="uploaded_predictions",
            model_family="uploaded_prediction_csv",
            result_type="uploaded_prediction_csv",
            status="invalid_predictions",
            n_train=None,
            n_test=len(snapshot.test),
            train_start=snapshot.read.train_start,
            train_end=snapshot.read.train_end,
            test_start=snapshot.read.test_start,
            test_end=snapshot.read.test_end,
            provenance_url=prediction_set.provenance_url,
            warnings=[BENCHMARK_WARNING, FAIRNESS_WARNING, *errors],
            limitations=_string_list(prediction_set.limitations_json) + BENCHMARK_LIMITATIONS,
            data_quality_notes=data_quality_notes,
            metadata={"prediction_set_id": prediction_set.id},
            points=[],
        )

    by_date = {point.target_date: point for point in prediction_set.points}
    predictions = [by_date[day].predicted_value for day, _observed in snapshot.test]
    result = _complete_result(
        model_id=prediction_set.model_id,
        model_name=prediction_set.model_name,
        model_kind="uploaded_predictions",
        model_family="uploaded_prediction_csv",
        result_type="uploaded_prediction_csv",
        predictions=predictions,
        test=snapshot.test,
        unit=snapshot.read.unit or prediction_set.unit,
        limitations=_string_list(prediction_set.limitations_json) + BENCHMARK_LIMITATIONS,
        warnings=[BENCHMARK_WARNING, FAIRNESS_WARNING],
        n_train=None,
        train=snapshot.train,
        data_quality_notes=data_quality_notes,
        provenance_url=prediction_set.provenance_url,
        dataset_snapshot_id=snapshot.read.id,
        metadata={"prediction_set_id": prediction_set.id},
    )
    for point, (day, _observed) in zip(result.points, snapshot.test, strict=True):
        uploaded = by_date[day]
        point.lower = uploaded.lower
        point.upper = uploaded.upper
        point.unit = uploaded.unit or point.unit
    return result


def _complete_result(
    *,
    model_id: str,
    model_name: str,
    model_kind: str,
    model_family: str,
    result_type: str,
    predictions: Iterable[float],
    test: list[tuple[date, float]],
    unit: str | None,
    limitations: list[str],
    warnings: list[dict[str, str]],
    n_train: int | None,
    train: list[tuple[date, float]],
    data_quality_notes: list[dict[str, str]],
    provenance_url: str | None = None,
    dataset_snapshot_id: int | None = None,
    metadata: dict | None = None,
) -> ForecastBenchmarkResultRead:
    prediction_values = [float(value) for value in predictions]
    observed_values = [value for _day, value in test]
    metrics = _metrics(observed_values, prediction_values)
    points = []
    for (day, observed), predicted in zip(test, prediction_values, strict=True):
        absolute_error = abs(predicted - observed)
        percentage_error = None if observed == 0 else (absolute_error / abs(observed)) * 100
        points.append(
            ForecastBenchmarkPointRead(
                date=day,
                observed_value=float(observed),
                predicted_value=float(predicted),
                absolute_error=round(absolute_error, 6),
                percentage_error=round(percentage_error, 6) if percentage_error is not None else None,
                unit=unit,
            )
        )
    return ForecastBenchmarkResultRead(
        dataset_snapshot_id=dataset_snapshot_id,
        model_id=model_id,
        model_name=model_name,
        display_name=model_name,
        model_kind=model_kind,
        model_family=model_family,
        result_type=result_type,
        status="complete",
        mae=metrics["mae"],
        rmse=metrics["rmse"],
        smape=metrics["smape"],
        n_train=n_train,
        n_test=len(test),
        train_start=train[0][0] if train else None,
        train_end=train[-1][0] if train else None,
        test_start=test[0][0] if test else None,
        test_end=test[-1][0] if test else None,
        provenance_url=provenance_url,
        warnings=warnings,
        limitations=limitations,
        data_quality_notes=data_quality_notes,
        metadata=metadata or {},
        points=points,
    )


def _metrics(observed: list[float], predicted: list[float]) -> dict[str, float]:
    pairs = [
        (float(actual), float(forecast))
        for actual, forecast in zip(observed, predicted, strict=True)
        if isfinite(actual) and isfinite(forecast)
    ]
    if not pairs:
        return {"mae": 0.0, "rmse": 0.0, "smape": 0.0}
    errors = [forecast - actual for actual, forecast in pairs]
    mae = mean(abs(error) for error in errors)
    rmse = sqrt(mean(error * error for error in errors))
    smape_terms = []
    for actual, forecast in pairs:
        denominator = abs(actual) + abs(forecast)
        smape_terms.append(0.0 if denominator == 0 else (2 * abs(forecast - actual) / denominator) * 100)
    return {"mae": round(mae, 6), "rmse": round(rmse, 6), "smape": round(mean(smape_terms), 6)}


def _forecast_arima(train_values: list[float], steps: int) -> list[float]:
    from statsmodels.tsa.arima.model import ARIMA

    model = ARIMA(np.asarray(train_values, dtype=float), order=(1, 0, 0))
    fitted = model.fit()
    return [float(value) for value in fitted.forecast(steps=steps)]


def _forecast_sarima(train_values: list[float], steps: int, season_length: int) -> list[float]:
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    model = SARIMAX(
        np.asarray(train_values, dtype=float),
        order=(1, 0, 0),
        seasonal_order=(1, 0, 0, season_length),
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fitted = model.fit(disp=False)
    return [float(value) for value in fitted.forecast(steps=steps)]


def _forecast_autoets(
    train: list[tuple[date, float]],
    steps: int,
    frequency: str,
) -> tuple[list[float], list[dict[str, str]]]:
    from statsforecast import StatsForecast
    from statsforecast.models import AutoETS

    season_length = _autoets_season_length(frequency, len(train))
    warnings: list[dict[str, str]] = []
    if season_length == 1:
        warnings.append(
            {
                "code": "seasonality_disabled",
                "message": "StatsForecast AutoETS ran with season_length=1 because the stored aggregate series lacks enough observed seasonal cycles.",
                "severity": "info",
            }
        )

    frame = pd.DataFrame(
        {
            "unique_id": ["benchmark_series"] * len(train),
            "ds": pd.to_datetime([day for day, _value in train]),
            "y": [float(value) for _day, value in train],
        }
    )
    model = AutoETS(season_length=season_length)
    forecast = StatsForecast(models=[model], freq=FREQUENCY_TO_PANDAS[frequency], n_jobs=1).forecast(
        df=frame,
        h=steps,
    )
    value_column = "AutoETS"
    if value_column not in forecast.columns:
        value_column = next(column for column in forecast.columns if column not in {"unique_id", "ds"})
    return [float(value) for value in forecast[value_column].tolist()], warnings


def _autoets_season_length(frequency: str, train_count: int) -> int:
    candidates = {"daily": 7, "weekly": 52, "monthly": 12}
    candidate = candidates.get(frequency, 1)
    return candidate if train_count >= candidate * 2 else 1


def _legacy_season_length(frequency: str) -> int:
    if frequency == "daily":
        return 7
    if frequency == "monthly":
        return 12
    return 4


def _query_observation_rows(
    db: Session,
    request: ForecastBenchmarkDatasetRequest,
    country: str,
) -> list[dict[str, object]]:
    query = select(models.Observation).where(
        models.Observation.country_iso3 == country,
        models.Observation.source_id == request.source_id,
        models.Observation.metric == request.metric,
    )
    if request.unit is not None:
        query = query.where(models.Observation.unit == request.unit)
    if request.signal_category is not None:
        query = query.where(models.Observation.signal_category == request.signal_category)

    rows = db.execute(query.order_by(models.Observation.observed_at.asc(), models.Observation.id.asc())).scalars().all()
    grouped: dict[date, list[models.Observation]] = defaultdict(list)
    for row in rows:
        observed_date = row.observed_at.date()
        if request.start_date and observed_date < request.start_date:
            continue
        if request.end_date and observed_date > request.end_date:
            continue
        grouped[observed_date].append(row)

    output: list[dict[str, object]] = []
    for observed_date in sorted(grouped):
        group = grouped[observed_date]
        values = [float(row.normalized_value if row.normalized_value is not None else row.value) for row in group]
        quality_scores = [row.quality_score for row in group if row.quality_score is not None]
        output.append(
            {
                "date": observed_date,
                "value": mean(values),
                "observation_ids": [row.id for row in group],
                "signal_categories": sorted({row.signal_category for row in group if row.signal_category}),
                "units": sorted({row.unit for row in group if row.unit}),
                "provenance_urls": sorted({row.provenance_url for row in group if row.provenance_url}),
                "quality_score": mean(quality_scores) if quality_scores else None,
            }
        )
    return output


def _snapshot_diagnostics(
    db: Session,
    request: ForecastBenchmarkDatasetRequest,
    rows: list[dict[str, object]],
    frequency: str,
) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    if not rows:
        notes.append(
            {
                "code": "no_matching_observations",
                "message": "No matching stored aggregate observations were found.",
                "severity": "warning",
            }
        )
        return notes
    if len(rows) < request.horizon_periods + MIN_TRAIN_POINTS:
        notes.append(
            {
                "code": "short_series",
                "message": "The stored aggregate series is short for benchmark modeling; some models may return insufficient_data.",
                "severity": "warning",
            }
        )
    if not validate_regular_frequency(rows, frequency):
        notes.append(
            {
                "code": "irregular_frequency",
                "message": "Observation dates are not perfectly regular for the requested frequency; the backend did not fabricate missing observations.",
                "severity": "warning",
            }
        )
    if any(not row["units"] for row in rows):
        notes.append(
            {
                "code": "missing_units",
                "message": "Some matching observations do not include units.",
                "severity": "info",
            }
        )
    if any(not row["provenance_urls"] for row in rows):
        notes.append(
            {
                "code": "missing_provenance",
                "message": "Some matching observations lack provenance_url; benchmark is allowed but should be interpreted cautiously.",
                "severity": "warning",
            }
        )
    quality_scores = [row["quality_score"] for row in rows if row["quality_score"] is not None]
    if quality_scores and mean(quality_scores) < 0.5:
        notes.append(
            {
                "code": "low_quality_score",
                "message": "Average observation quality_score is below 0.5.",
                "severity": "warning",
            }
        )
    return notes


def _has_irregular_dates(series: list[tuple[date, float]], frequency: str) -> bool:
    if len(series) < 3:
        return False
    dates = [day for day, _value in series]
    gaps = [(right - left).days for left, right in zip(dates, dates[1:], strict=False)]
    if frequency == "daily":
        return any(gap != 1 for gap in gaps)
    if frequency == "weekly":
        return any(gap != 7 for gap in gaps)
    if frequency == "monthly":
        return any(not _is_next_month(left, right) for left, right in zip(dates, dates[1:], strict=False))
    return False


def _is_next_month(left: date, right: date) -> bool:
    year = left.year + (1 if left.month == 12 else 0)
    month = 1 if left.month == 12 else left.month + 1
    return right.year == year and right.month == month


def _selected_builtin_and_uploaded_model_ids(
    db: Session,
    request: ForecastBenchmarkRequest,
    snapshot: SnapshotData,
) -> list[str]:
    if request.model_ids:
        return list(dict.fromkeys(request.model_ids))

    builtin_ids = default_builtin_model_ids()
    uploaded_ids = [
        row[0]
        for row in db.execute(
            select(models.UploadedPredictionSet.model_id)
            .where(
                models.UploadedPredictionSet.country_iso3 == snapshot.read.country_iso3,
                models.UploadedPredictionSet.source_id == snapshot.read.source_id,
                models.UploadedPredictionSet.metric == snapshot.read.metric,
            )
            .group_by(models.UploadedPredictionSet.model_id)
        ).all()
    ]
    legacy_uploaded_ids = [
        row[0]
        for row in db.execute(
            select(models.UploadedForecastPredictionPoint.model_id)
            .where(
                models.UploadedForecastPredictionPoint.country_iso3 == snapshot.read.country_iso3,
                models.UploadedForecastPredictionPoint.source_id == snapshot.read.source_id,
                models.UploadedForecastPredictionPoint.metric == snapshot.read.metric,
            )
            .group_by(models.UploadedForecastPredictionPoint.model_id)
        ).all()
    ]
    return list(dict.fromkeys([*builtin_ids, *uploaded_ids, *legacy_uploaded_ids]))


def _prediction_sets_for_model(
    db: Session,
    model_id: str,
    request: ForecastBenchmarkRequest,
    snapshot: SnapshotData,
) -> list[models.UploadedPredictionSet]:
    explicit_ids = set(request.uploaded_prediction_set_ids or [])
    query = (
        select(models.UploadedPredictionSet)
        .where(
            models.UploadedPredictionSet.model_id == model_id,
            models.UploadedPredictionSet.country_iso3 == snapshot.read.country_iso3,
            models.UploadedPredictionSet.source_id == snapshot.read.source_id,
            models.UploadedPredictionSet.metric == snapshot.read.metric,
        )
        .options(selectinload(models.UploadedPredictionSet.points))
        .order_by(models.UploadedPredictionSet.created_at.desc(), models.UploadedPredictionSet.id.desc())
    )
    rows = db.execute(query).scalars().all()
    compatible = [row for row in rows if not validate_prediction_dates_against_snapshot(row, snapshot)]
    if explicit_ids:
        compatible.extend(row for row in rows if row.id in explicit_ids and row not in compatible)
    if compatible:
        return compatible[:1] if not explicit_ids else compatible

    legacy_model = db.get(models.ForecastModel, model_id)
    if legacy_model is None:
        return []
    legacy_set = _legacy_prediction_set_from_points(db, legacy_model, snapshot)
    return [legacy_set] if legacy_set else []


def _legacy_prediction_set_from_points(
    db: Session,
    model: models.ForecastModel,
    snapshot: SnapshotData,
) -> models.UploadedPredictionSet | None:
    target_dates = {day for day, _value in snapshot.test}
    rows = (
        db.execute(
            select(models.UploadedForecastPredictionPoint)
            .where(
                models.UploadedForecastPredictionPoint.model_id == model.id,
                models.UploadedForecastPredictionPoint.country_iso3 == snapshot.read.country_iso3,
                models.UploadedForecastPredictionPoint.source_id == snapshot.read.source_id,
                models.UploadedForecastPredictionPoint.metric == snapshot.read.metric,
                models.UploadedForecastPredictionPoint.target_date.in_(target_dates),
            )
            .order_by(models.UploadedForecastPredictionPoint.target_date.asc())
        )
        .scalars()
        .all()
    )
    if not rows:
        return None
    pseudo = models.UploadedPredictionSet(
        id=-1,
        model_id=model.id,
        model_name=model.name,
        country_iso3=snapshot.read.country_iso3,
        source_id=snapshot.read.source_id,
        metric=snapshot.read.metric,
        unit=snapshot.read.unit,
        provenance_url=model.provenance_url,
        validation_status="stored_unmatched",
        limitations_json=model.limitations,
        validation_warnings_json=[],
        validation_errors_json=[],
        created_at=datetime.now(UTC),
    )
    pseudo.points = [
        models.UploadedPredictionPoint(
            prediction_set_id=-1,
            target_date=row.target_date,
            predicted_value=row.predicted_value,
            lower=row.lower,
            upper=row.upper,
            unit=row.unit,
            generated_at=row.generated_at,
            provenance_url=row.provenance_url,
        )
        for row in rows
    ]
    return pseudo


def _comparison_points(
    snapshot: SnapshotData,
    results: list[ForecastBenchmarkResultRead],
) -> list[dict[str, object]]:
    by_date: dict[date, dict[str, object]] = {
        day: {"target_date": day, "observed_value": observed, "unit": snapshot.read.unit, "predictions": []}
        for day, observed in snapshot.test
    }
    for result in results:
        if result.status != "complete":
            continue
        for point in result.points:
            by_date[point.date]["predictions"].append(
                {
                    "model_id": result.model_id,
                    "display_name": result.display_name or result.model_name,
                    "result_type": result.result_type,
                    "predicted_value": point.predicted_value,
                    "lower": point.lower,
                    "upper": point.upper,
                }
            )
    return [by_date[day] for day, _observed in snapshot.test]


def _snapshot_for_benchmark_request(
    db: Session,
    request: ForecastBenchmarkRequest,
    *,
    persist: bool,
) -> SnapshotData:
    if request.dataset_snapshot_id is not None:
        return _snapshot_data_from_row(_get_snapshot_row(db, request.dataset_snapshot_id))

    dataset_request = _dataset_request_from_benchmark_request(request)
    data = build_benchmark_dataset_snapshot(db, dataset_request)
    if persist or request.save:
        row = _persist_snapshot_data(db, data)
        return _snapshot_data_from_row(row)
    return data


def _dataset_request_from_benchmark_request(request: ForecastBenchmarkRequest) -> ForecastBenchmarkDatasetRequest:
    missing = [
        field
        for field, value in {
            "countryIso3": request.country_iso3,
            "sourceId": request.source_id,
            "metric": request.metric,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError("Missing required dataset selection fields: " + ", ".join(missing))
    return ForecastBenchmarkDatasetRequest(
        country_iso3=request.country_iso3,
        source_id=request.source_id,
        signal_category=request.signal_category,
        metric=request.metric,
        unit=request.unit,
        frequency=request.frequency,
        horizon_periods=request.horizon_periods,
        start_date=request.start_date or request.train_start,
        end_date=request.end_date or request.train_end,
        split_strategy=request.split_strategy,
    )


def _persist_snapshot_data(db: Session, data: SnapshotData) -> models.ForecastBenchmarkDatasetSnapshot:
    read = data.read
    existing = (
        db.execute(
            select(models.ForecastBenchmarkDatasetSnapshot).where(
                models.ForecastBenchmarkDatasetSnapshot.dataset_hash == read.dataset_hash
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        return existing

    row = models.ForecastBenchmarkDatasetSnapshot(
        country_iso3=read.country_iso3,
        source_id=read.source_id,
        signal_category=read.signal_category,
        metric=read.metric,
        unit=read.unit,
        frequency=read.frequency,
        horizon_periods=read.horizon_periods,
        split_strategy=read.split_strategy,
        train_start=read.train_start,
        train_end=read.train_end,
        test_start=read.test_start,
        test_end=read.test_end,
        target_dates_json=[day.isoformat() for day in read.target_dates],
        observation_ids_json=read.observation_ids,
        train_observation_ids_json=read.train_observation_ids,
        test_observation_ids_json=read.test_observation_ids,
        train_rows_json=serializable(data.train_rows),
        test_rows_json=serializable(data.test_rows),
        dataset_hash=read.dataset_hash,
        status=read.status,
        quality_warnings_json=read.warnings,
        limitations_json=read.limitations,
        provenance_json=read.provenance,
        created_at=read.created_at or datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _snapshot_data_from_row(row: models.ForecastBenchmarkDatasetSnapshot) -> SnapshotData:
    read = _dataset_read_from_row(row)
    train_rows = [_deserialize_snapshot_row(item) for item in row.train_rows_json or []]
    test_rows = [_deserialize_snapshot_row(item) for item in row.test_rows_json or []]
    return SnapshotData(
        read=read,
        train=[(row["date"], float(row["value"])) for row in train_rows],
        test=[(row["date"], float(row["value"])) for row in test_rows],
        train_rows=train_rows,
        test_rows=test_rows,
    )


def _dataset_read_from_row(row: models.ForecastBenchmarkDatasetSnapshot) -> ForecastBenchmarkDatasetRead:
    return ForecastBenchmarkDatasetRead(
        id=row.id,
        country_iso3=row.country_iso3,
        source_id=row.source_id,
        signal_category=row.signal_category,
        metric=row.metric,
        unit=row.unit,
        frequency=row.frequency,
        horizon_periods=row.horizon_periods,
        split_strategy=row.split_strategy,
        train_start=row.train_start,
        train_end=row.train_end,
        test_start=row.test_start,
        test_end=row.test_end,
        target_dates=[coerce_date(value) for value in row.target_dates_json or [] if coerce_date(value)],
        observation_ids=row.observation_ids_json or [],
        train_observation_ids=row.train_observation_ids_json or [],
        test_observation_ids=row.test_observation_ids_json or [],
        n_train=len(row.train_rows_json or []),
        n_test=len(row.test_rows_json or []),
        dataset_hash=row.dataset_hash,
        status=row.status,
        warnings=row.quality_warnings_json or [],
        limitations=row.limitations_json or [],
        provenance=row.provenance_json or {},
        created_at=row.created_at,
    )


def _deserialize_snapshot_row(row: Mapping[str, object]) -> dict[str, object]:
    output = dict(row)
    output["date"] = coerce_date(output.get("date"))
    return output


def _prediction_defaults_from_snapshot(row: models.ForecastBenchmarkDatasetSnapshot | None) -> dict[str, object]:
    if row is None:
        return {}
    return {
        "country_iso3": row.country_iso3,
        "source_id": row.source_id,
        "metric": row.metric,
        "unit": row.unit,
        "frequency": row.frequency,
        "horizon_periods": row.horizon_periods,
    }


def _validate_prediction_set_consistency(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    keys = ("model_id", "model_name", "country_iso3", "source_id", "metric", "unit")
    errors = []
    first = rows[0]
    for key in keys:
        values = {row.get(key) for row in rows}
        if len(values) > 1:
            errors.append({"code": "mixed_prediction_set", "message": f"Prediction CSV contains multiple {key} values."})
    return errors


def _ensure_uploaded_forecast_model(
    db: Session,
    normalized: Mapping[str, object],
) -> models.ForecastModel:
    model = db.get(models.ForecastModel, normalized["model_id"])
    if model is None:
        model = models.ForecastModel(
            id=normalized["model_id"],
            name=normalized["model_name"],
            model_kind="uploaded_predictions",
            description="Uploaded forecast prediction points for benchmark comparison.",
            owner="Sentinel Atlas user",
            status="uploaded_predictions",
            provenance_url=normalized["provenance_url"],
            limitations=normalized["limitations"],
            warnings=[BENCHMARK_WARNING],
        )
        db.add(model)
        db.flush()
    else:
        model.name = normalized["model_name"]
        if normalized["provenance_url"]:
            model.provenance_url = normalized["provenance_url"]
        if normalized["limitations"]:
            model.limitations = normalized["limitations"]
    return model


def _prediction_set_read(
    row: models.UploadedPredictionSet,
    *,
    include_points: bool,
) -> UploadedPredictionSetRead:
    points = sorted(row.points, key=lambda point: point.target_date)
    return UploadedPredictionSetRead(
        id=row.id,
        benchmark_dataset_snapshot_id=row.benchmark_dataset_snapshot_id,
        submitter_id=row.submitter_id,
        model_id=row.model_id,
        model_name=row.model_name,
        country_iso3=row.country_iso3,
        source_id=row.source_id,
        metric=row.metric,
        unit=row.unit,
        frequency=row.frequency,
        horizon_periods=row.horizon_periods,
        target_start=row.target_start,
        target_end=row.target_end,
        provenance_url=row.provenance_url,
        user_notes=row.user_notes,
        validation_status=row.validation_status,
        submitter_name=row.submitter_name,
        organization=row.organization,
        submission_track=row.submission_track,
        review_status=row.review_status,
        visibility=row.visibility,
        method_summary=row.method_summary,
        model_url=row.model_url,
        code_url=row.code_url,
        disclosure_notes=row.disclosure_notes,
        row_count=len(points),
        matched_dataset_snapshot_id=row.benchmark_dataset_snapshot_id,
        warnings=row.validation_warnings_json or [],
        limitations=row.limitations_json or [],
        errors=row.validation_errors_json or [],
        created_at=row.created_at,
        points=[
            UploadedPredictionPointRead(
                id=point.id,
                prediction_set_id=point.prediction_set_id,
                target_date=point.target_date,
                predicted_value=point.predicted_value,
                lower=point.lower,
                upper=point.upper,
                unit=point.unit,
                generated_at=point.generated_at,
                provenance_url=point.provenance_url,
            )
            for point in points
        ]
        if include_points
        else [],
    )


def _run_to_read(run: models.ForecastBenchmarkRun) -> ForecastBenchmarkRead:
    dataset = _dataset_read_from_row(run.dataset_snapshot) if run.dataset_snapshot else None
    results = [
        ForecastBenchmarkResultRead(
            id=result.id,
            benchmark_run_id=run.id,
            dataset_snapshot_id=result.dataset_snapshot_id,
            model_id=result.model_id,
            model_name=result.model_name,
            display_name=result.model_name,
            model_kind=result.model_kind,
            model_family=(result.metadata_json or {}).get("model_family"),
            result_type=result.result_type,
            status=result.status,
            mae=result.mae,
            rmse=result.rmse,
            smape=result.smape,
            n_train=result.n_train,
            n_test=result.n_test,
            train_start=result.train_start,
            train_end=result.train_end,
            test_start=result.test_start,
            test_end=result.test_end,
            rank=result.rank,
            provenance_url=result.provenance_url,
            warnings=result.warnings,
            limitations=result.limitations,
            data_quality_notes=result.data_quality_notes,
            metadata=result.metadata_json or {},
            points=[
                ForecastBenchmarkPointRead(
                    id=point.id,
                    benchmark_result_id=result.id,
                    date=point.date,
                    observed_value=point.observed_value,
                    predicted_value=point.predicted_value,
                    lower=point.lower,
                    upper=point.upper,
                    absolute_error=point.absolute_error,
                    percentage_error=point.percentage_error,
                    unit=point.unit,
                )
                for point in sorted(result.points, key=lambda item: item.date)
            ],
        )
        for result in run.results
    ]
    leaderboard = rank_benchmark_results(results)
    comparison_points = _comparison_points(_snapshot_data_from_row(run.dataset_snapshot), results) if run.dataset_snapshot else []
    return ForecastBenchmarkRead(
        id=run.id,
        dataset_snapshot_id=run.dataset_snapshot_id,
        country_iso3=run.country_iso3,
        source_id=run.source_id,
        metric=run.metric,
        unit=run.unit,
        frequency=run.frequency,
        horizon_periods=run.horizon_periods,
        train_start=run.train_start,
        train_end=run.train_end,
        requested_model_ids=run.requested_model_ids,
        uploaded_prediction_set_ids=run.uploaded_prediction_set_ids,
        output_status=run.output_status,
        explanation=run.explanation,
        warnings=run.warnings,
        limitations=run.limitations,
        comparison=leaderboard,
        leaderboard=leaderboard,
        comparison_points=comparison_points,
        data_quality_notes=run.data_quality_notes,
        dataset_snapshot=dataset,
        benchmark_run={
            "id": run.id,
            "dataset_snapshot_id": run.dataset_snapshot_id,
            "country_iso3": run.country_iso3,
            "source_id": run.source_id,
            "metric": run.metric,
            "frequency": run.frequency,
            "horizon_periods": run.horizon_periods,
            "status": run.output_status,
            "warnings": run.warnings,
            "limitations": run.limitations,
            "explanation": run.explanation,
        },
        created_at=run.created_at,
        results=results,
    )


def _insufficient_result(
    model_id: str,
    message: str,
    *,
    n_train: int | None = 0,
    n_test: int = 0,
    train: list[tuple[date, float]] | None = None,
    test: list[tuple[date, float]] | None = None,
    data_quality_notes: list[dict[str, str]] | None = None,
    dataset_snapshot_id: int | None = None,
    result_type: str = "builtin_model",
) -> ForecastBenchmarkResultRead:
    model = BUILTIN_MODELS.get(model_id)
    model_name = model.name if model else model_id
    model_kind = model.model_kind if model else "uploaded_predictions"
    model_family = model.model_family if model else "uploaded_prediction_csv"
    limitations = list(model.limitations) if model else []
    train = train or []
    test = test or []
    return ForecastBenchmarkResultRead(
        dataset_snapshot_id=dataset_snapshot_id,
        model_id=model_id,
        model_name=model_name,
        display_name=model_name,
        model_kind=model_kind,
        model_family=model_family,
        result_type=result_type,
        status="insufficient_data",
        n_train=n_train,
        n_test=n_test,
        train_start=train[0][0] if train else None,
        train_end=train[-1][0] if train else None,
        test_start=test[0][0] if test else None,
        test_end=test[-1][0] if test else None,
        warnings=[BENCHMARK_WARNING, {"code": "insufficient_data", "message": message, "severity": "warning"}],
        limitations=limitations + BENCHMARK_LIMITATIONS,
        data_quality_notes=data_quality_notes or [],
        points=[],
    )


def _failed_result(
    model: BuiltinForecastModel,
    message: str,
    *,
    n_train: int,
    n_test: int,
    train: list[tuple[date, float]] | None = None,
    test: list[tuple[date, float]] | None = None,
    dataset_snapshot_id: int | None = None,
) -> ForecastBenchmarkResultRead:
    train = train or []
    test = test or []
    return ForecastBenchmarkResultRead(
        dataset_snapshot_id=dataset_snapshot_id,
        model_id=model.id,
        model_name=model.name,
        display_name=model.name,
        model_kind=model.model_kind,
        model_family=model.model_family,
        result_type="builtin_model",
        status="failed",
        n_train=n_train,
        n_test=n_test,
        train_start=train[0][0] if train else None,
        train_end=train[-1][0] if train else None,
        test_start=test[0][0] if test else None,
        test_end=test[-1][0] if test else None,
        warnings=[BENCHMARK_WARNING, {"code": "model_failed", "message": message[:500], "severity": "warning"}],
        limitations=list(model.limitations) + BENCHMARK_LIMITATIONS,
        points=[],
    )


def _model_unavailable_result(
    model: BuiltinForecastModel,
    *,
    n_train: int,
    n_test: int,
    train: list[tuple[date, float]] | None = None,
    test: list[tuple[date, float]] | None = None,
    dataset_snapshot_id: int | None = None,
    status: str = "model_unavailable",
    code: str = "missing_optional_dependency",
    message: str | None = None,
) -> ForecastBenchmarkResultRead:
    train = train or []
    test = test or []
    if message is None:
        if model.id == EXPERIMENTAL_TABPFN_TS_MODEL_ID:
            message = (
                "Experimental TabPFN-Time-Series requires the optional `tabpfn-time-series` dependency. "
                "Install backend with `pip install -e \".[dev,experimental]\"`."
            )
        else:
            message = (
                "StatsForecast AutoETS requires the optional `statsforecast` dependency. "
                "Install backend with `pip install -e \".[dev,forecast]\"`."
            )
    return ForecastBenchmarkResultRead(
        dataset_snapshot_id=dataset_snapshot_id,
        model_id=model.id,
        model_name=model.name,
        display_name=model.name,
        model_kind=model.model_kind,
        model_family=model.model_family,
        result_type="builtin_model",
        status=status,
        n_train=n_train,
        n_test=n_test,
        train_start=train[0][0] if train else None,
        train_end=train[-1][0] if train else None,
        test_start=test[0][0] if test else None,
        test_end=test[-1][0] if test else None,
        warnings=[
            BENCHMARK_WARNING,
            {
                "code": code,
                "message": message,
                "severity": "warning",
            },
        ],
        limitations=list(model.limitations) + BENCHMARK_LIMITATIONS,
        points=[],
    )


def _benchmark_output_status(results: list[ForecastBenchmarkResultRead]) -> str:
    statuses = {result.status for result in results}
    if "complete" in statuses and statuses <= {"complete"}:
        return "complete"
    if "complete" in statuses:
        return "partial"
    if "invalid_predictions" in statuses:
        return "partial"
    if "model_unavailable" in statuses:
        return "partial"
    if "experimental_disabled" in statuses:
        return "partial"
    return "insufficient_data"


def _builtin_model_read(model: BuiltinForecastModel) -> ForecastModelRead:
    return ForecastModelRead(
        id=model.id,
        name=model.name,
        model_id=model.id,
        display_name=model.name,
        model_kind=model.model_kind,
        model_family=model.model_family,
        implementation_source=model.implementation_source,
        benchmark_only=True,
        builtin=True,
        experimental=model.experimental,
        enabled_by_default=model.enabled_by_default,
        feature_flag_enabled=is_experimental_tabpfn_enabled() if model.experimental else True,
        accepts_uploaded_code=False,
        accepts_prediction_csv=False,
        required_observation_count=model.min_train_points,
        supported_frequencies=list(model.supported_frequencies),
        required_frequency_notes=model.required_frequency_notes,
        supports_prediction_intervals=model.supports_prediction_intervals,
        default_parameters=dict(model.default_parameters or {}),
        description=model.description,
        owner="Sentinel Atlas",
        status=model.status,
        safety_notes=list(model.safety_notes),
        citation_or_package_notes=model.citation_or_package_notes,
        dependency_status=_dependency_status(model),
        registry_version=REGISTRY_VERSION,
        limitations=list(model.limitations),
        warnings=[
            BENCHMARK_WARNING,
            *({"code": "model_warning", "message": warning, "severity": "info"} for warning in model.warnings),
        ],
    )


def _db_model_read(model: models.ForecastModel) -> ForecastModelRead:
    return ForecastModelRead(
        id=model.id,
        name=model.name,
        model_id=model.id,
        display_name=model.name,
        model_kind=model.model_kind,
        model_family="uploaded_prediction_csv",
        implementation_source="user_uploaded_prediction_csv",
        benchmark_only=True,
        builtin=False,
        accepts_uploaded_code=False,
        accepts_prediction_csv=True,
        supported_frequencies=list(SUPPORTED_FREQUENCIES),
        required_frequency_notes="Uploaded predictions are matched to benchmark snapshot holdout target dates.",
        supports_prediction_intervals="true_when_lower_upper_columns_are_supplied",
        default_parameters={},
        description=model.description,
        owner=model.owner,
        status=model.status,
        safety_notes=[
            "Uploaded prediction CSVs are benchmark inputs only.",
            "Executable model code, notebooks, containers, pickle/joblib files, and model binaries are not accepted.",
        ],
        dependency_status="available",
        registry_version=REGISTRY_VERSION,
        provenance_url=model.provenance_url,
        limitations=_string_list(model.limitations),
        warnings=list(model.warnings or []),
    )


def _dependency_status(model: BuiltinForecastModel) -> str:
    if model.id == EXPERIMENTAL_TABPFN_TS_MODEL_ID:
        return get_tabpfn_dependency_status()
    if model.dependency_name is None:
        return "available"
    return "available" if importlib.util.find_spec(model.dependency_name) is not None else "missing_optional_dependency"


def _get_benchmark_run(db: Session, run_id: int, *, required: bool = True) -> models.ForecastBenchmarkRun | None:
    run = (
        db.execute(
            select(models.ForecastBenchmarkRun)
            .where(models.ForecastBenchmarkRun.id == run_id)
            .options(
                selectinload(models.ForecastBenchmarkRun.dataset_snapshot),
                selectinload(models.ForecastBenchmarkRun.results).selectinload(models.ForecastBenchmarkResult.points),
            )
        )
        .scalars()
        .one_or_none()
    )
    if run is None and required:
        raise LookupError(f"Forecast benchmark {run_id} not found")
    return run


def _get_snapshot_row(db: Session, dataset_snapshot_id: int | None) -> models.ForecastBenchmarkDatasetSnapshot:
    row = db.get(models.ForecastBenchmarkDatasetSnapshot, dataset_snapshot_id)
    if row is None:
        raise ValueError("Benchmark dataset snapshot not found")
    return row


def _get_prediction_set_row(
    db: Session,
    prediction_set_id: int,
    *,
    required: bool = True,
) -> models.UploadedPredictionSet | None:
    row = (
        db.execute(
            select(models.UploadedPredictionSet)
            .where(models.UploadedPredictionSet.id == prediction_set_id)
            .options(selectinload(models.UploadedPredictionSet.points))
        )
        .scalars()
        .one_or_none()
    )
    if row is None and required:
        raise ValueError("Uploaded prediction set not found")
    return row


def _validate_country(value: str) -> str:
    country = normalize_iso3(value)
    if not country or country == "GLOBAL":
        raise ValueError("country_iso3 must be a concrete ISO3 country code")
    return country


def _validate_frequency(value: str) -> str:
    frequency = value.strip().lower()
    if frequency not in SUPPORTED_FREQUENCIES:
        raise ValueError("frequency must be daily, weekly, or monthly")
    return frequency


def _validate_horizon(value: int) -> int:
    if value < 1 or value > 52:
        raise ValueError("horizon_periods must be between 1 and 52")
    return value


def _validate_split_strategy(value: str) -> str:
    split_strategy = (value or DEFAULT_SPLIT_STRATEGY).strip().lower()
    if split_strategy != DEFAULT_SPLIT_STRATEGY:
        raise ValueError("split_strategy must be last_n_periods")
    return split_strategy


def _first_value(raw: Mapping[str, object], fields: tuple[str, ...]) -> object | None:
    for field in fields:
        if field in raw and raw[field] not in (None, ""):
            return raw[field]
    return None


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_field_name(value: object) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _string_list(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    if isinstance(value, Iterable):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]


def _coerce_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed_date = coerce_date(text)
        if parsed_date is None:
            return None
        return datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=UTC)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
