from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
import csv
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
from app.db import models
from app.schemas.forecast import (
    ForecastBenchmarkPointRead,
    ForecastBenchmarkRead,
    ForecastBenchmarkRequest,
    ForecastBenchmarkResultRead,
    ForecastModelRead,
    ForecastPredictionUploadResult,
    UploadedForecastPredictionRead,
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


BENCHMARK_WARNING = {
    "code": "benchmark_only",
    "message": "Forecast benchmark outputs are historical metric evaluations only, not public-health alerts, risk scores, Rt/R0 estimates, or operational guidance.",
    "severity": "warning",
}

BENCHMARK_LIMITATIONS = [
    "Benchmarks use stored aggregate observations only.",
    "Built-in baselines are proof-of-concept forecasting references, not validated public-health prediction systems.",
    "Missing, short, or sparse series are returned as insufficient_data instead of fabricated outputs.",
]

REGISTRY_VERSION = "forecast-benchmark-registry-v2-2026-04-25"
SUPPORTED_FREQUENCIES = ("daily", "weekly", "monthly")
FREQUENCY_TO_PANDAS = {"daily": "D", "weekly": "W", "monthly": "MS"}
EXECUTABLE_MODEL_REJECT_FIELDS = frozenset(
    {
        "code",
        "model_code",
        "python_code",
        "script",
        "shell_command",
        "command",
        "cmd",
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
    required_frequency_notes: str = "Uses the benchmark request frequency after duplicate observation dates are aggregated by mean."
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
}


def list_forecast_models(db: Session) -> list[ForecastModelRead]:
    uploaded = db.execute(select(models.ForecastModel).order_by(models.ForecastModel.name)).scalars().all()
    uploaded_by_id = {model.id: model for model in uploaded}
    output = [_builtin_model_read(model) for model in BUILTIN_MODELS.values()]
    output.extend(_db_model_read(model) for model_id, model in uploaded_by_id.items() if model_id not in BUILTIN_MODELS)
    return output


def get_forecast_model(db: Session, model_id: str) -> ForecastModelRead | None:
    if model_id in BUILTIN_MODELS:
        return _builtin_model_read(BUILTIN_MODELS[model_id])
    model = db.get(models.ForecastModel, model_id)
    if model is None:
        return None
    return _db_model_read(model)


def parse_prediction_csv(content: str) -> list[dict[str, str]]:
    reader = csv.DictReader(StringIO(content))
    if not reader.fieldnames:
        raise NormalizationError("CSV upload must include a header row")
    return [dict(row) for row in reader]


def upload_forecast_predictions(db: Session, content: str) -> ForecastPredictionUploadResult:
    raw_rows = parse_prediction_csv(content)
    inserted: list[models.UploadedForecastPredictionPoint] = []
    models_by_id: dict[str, models.ForecastModel] = {}
    errors: list[dict[str, object]] = []

    for index, row in enumerate(raw_rows, start=2):
        try:
            normalized = normalize_prediction_upload_row(row)
        except NormalizationError as exc:
            errors.append({"row": index, "error": str(exc)})
            continue

        ensure_country(db, normalized["country_iso3"])
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
        models_by_id[model.id] = model

        point = models.UploadedForecastPredictionPoint(
            model_id=model.id,
            country_iso3=normalized["country_iso3"],
            source_id=normalized["source_id"],
            metric=normalized["metric"],
            unit=normalized["unit"],
            target_date=normalized["target_date"],
            predicted_value=normalized["predicted_value"],
            lower=normalized["lower"],
            upper=normalized["upper"],
            generated_at=normalized["generated_at"],
            provenance_url=normalized["provenance_url"],
            limitations=normalized["limitations"],
        )
        db.add(point)
        inserted.append(point)

    db.commit()
    for point in inserted:
        db.refresh(point)
    for model in models_by_id.values():
        db.refresh(model)

    return ForecastPredictionUploadResult(
        inserted_count=len(inserted),
        rejected_count=len(errors),
        models=[_db_model_read(model) for model in models_by_id.values()],
        predictions=[UploadedForecastPredictionRead.model_validate(point) for point in inserted],
        errors=errors,
        warnings=[BENCHMARK_WARNING],
    )


def normalize_prediction_upload_row(raw: Mapping[str, object]) -> dict[str, object]:
    lower_fields = {_normalize_field_name(field) for field in raw.keys()}
    unsafe_fields = sorted(lower_fields.intersection(AGGREGATE_ONLY_REJECT_FIELDS))
    trace_fields = sorted(lower_fields.intersection(OPERATIONAL_TRACE_WARNING_FIELDS))
    executable_fields = sorted(lower_fields.intersection(EXECUTABLE_MODEL_REJECT_FIELDS))
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

    model_id = _clean_text(_first_value(raw, ("modelId", "model_id")))
    model_name = _clean_text(_first_value(raw, ("modelName", "model_name"))) or model_id
    country = normalize_iso3(_first_value(raw, ("countryIso3", "country_iso3", "iso3", "country")))
    source_id = _clean_text(_first_value(raw, ("sourceId", "source_id", "source")))
    metric = _clean_text(_first_value(raw, ("metric", "measure", "indicator", "signal")))
    target_date = coerce_date(_first_value(raw, ("targetDate", "target_date", "date")))
    predicted_value = coerce_float(_first_value(raw, ("predictedValue", "predicted_value", "value")))
    generated_at = _coerce_datetime(_first_value(raw, ("generatedAt", "generated_at")))

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
        "unit": _clean_text(raw.get("unit")),
        "target_date": target_date,
        "predicted_value": predicted_value,
        "lower": coerce_float(raw.get("lower")),
        "upper": coerce_float(raw.get("upper")),
        "generated_at": generated_at,
        "provenance_url": _clean_text(_first_value(raw, ("provenanceUrl", "provenance_url", "sourceUrl"))),
        "limitations": _string_list(raw.get("limitations")),
    }


def preview_forecast_benchmark(db: Session, request: ForecastBenchmarkRequest) -> ForecastBenchmarkRead:
    country = _validate_country(request.country_iso3)
    frequency = _validate_frequency(request.frequency)
    horizon = _validate_horizon(request.horizon_periods)
    selected_model_ids = _selected_model_ids(db, request, country)
    series = _observed_series(db, request, country)
    data_quality_notes = _series_diagnostics(db, request, country, series, frequency)
    created_at = datetime.now(UTC)

    if not series:
        results = [
            _insufficient_result(model_id, "No matching stored aggregate observations were found.")
            for model_id in selected_model_ids
        ]
        return ForecastBenchmarkRead(
            country_iso3=country,
            source_id=request.source_id,
            metric=request.metric,
            unit=request.unit,
            frequency=frequency,
            horizon_periods=horizon,
            train_start=request.train_start,
            train_end=request.train_end,
            requested_model_ids=selected_model_ids,
            output_status="insufficient_data",
            explanation="No matching stored aggregate observations were found; benchmark output was not created.",
            warnings=[BENCHMARK_WARNING],
            limitations=BENCHMARK_LIMITATIONS,
            comparison=rank_benchmark_results(results),
            data_quality_notes=data_quality_notes,
            created_at=created_at,
            results=results,
        )

    if len(series) <= horizon:
        n_train = max(len(series) - horizon, 0)
        n_test = min(len(series), horizon)
        results = [
            _insufficient_result(
                model_id,
                f"Need more than horizon_periods={horizon} observations for a train/test split.",
                n_train=n_train,
                n_test=n_test,
            )
            for model_id in selected_model_ids
        ]
        return ForecastBenchmarkRead(
            country_iso3=country,
            source_id=request.source_id,
            metric=request.metric,
            unit=request.unit,
            frequency=frequency,
            horizon_periods=horizon,
            train_start=request.train_start,
            train_end=request.train_end,
            requested_model_ids=selected_model_ids,
            output_status="insufficient_data",
            explanation="The matching aggregate series is too short to create a holdout benchmark.",
            warnings=[BENCHMARK_WARNING],
            limitations=BENCHMARK_LIMITATIONS,
            comparison=rank_benchmark_results(results),
            data_quality_notes=data_quality_notes,
            created_at=created_at,
            results=results,
        )

    train = series[:-horizon]
    test = series[-horizon:]
    season_length = _legacy_season_length(frequency)
    results = [
        _benchmark_model(db, model_id, train, test, request, country, season_length, frequency, data_quality_notes)
        for model_id in selected_model_ids
    ]
    output_status = _benchmark_output_status(results)
    comparison = rank_benchmark_results(results)
    return ForecastBenchmarkRead(
        country_iso3=country,
        source_id=request.source_id,
        metric=request.metric,
        unit=request.unit,
        frequency=frequency,
        horizon_periods=horizon,
        train_start=request.train_start,
        train_end=request.train_end,
        requested_model_ids=selected_model_ids,
        output_status=output_status,
        explanation=(
            "Forecast benchmark completed using stored aggregate observations."
            if output_status == "complete"
            else "Forecast benchmark returned partial or insufficient model results from stored aggregate observations."
        ),
        warnings=[BENCHMARK_WARNING],
        limitations=BENCHMARK_LIMITATIONS,
        comparison=comparison,
        data_quality_notes=data_quality_notes,
        created_at=created_at,
        results=results,
    )


def create_forecast_benchmark(db: Session, request: ForecastBenchmarkRequest) -> models.ForecastBenchmarkRun:
    preview = preview_forecast_benchmark(db, request)
    if not _observed_series(db, request, preview.country_iso3):
        raise ValueError("No matching stored aggregate observations were found")

    ensure_country(db, preview.country_iso3)
    run = models.ForecastBenchmarkRun(
        country_iso3=preview.country_iso3,
        source_id=preview.source_id,
        metric=preview.metric,
        unit=preview.unit,
        frequency=preview.frequency,
        horizon_periods=preview.horizon_periods,
        train_start=preview.train_start,
        train_end=preview.train_end,
        requested_model_ids=preview.requested_model_ids,
        output_status=preview.output_status,
        explanation=preview.explanation,
        warnings=preview.warnings,
        limitations=preview.limitations,
        comparison=serializable(preview.comparison),
        data_quality_notes=preview.data_quality_notes,
        created_at=preview.created_at,
    )
    for result in preview.results:
        result_row = models.ForecastBenchmarkResult(
            model_id=result.model_id,
            model_name=result.model_name,
            model_kind=result.model_kind,
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
            provenance_url=result.provenance_url,
            warnings=result.warnings,
            limitations=result.limitations,
            data_quality_notes=result.data_quality_notes,
        )
        for point in result.points:
            result_row.points.append(
                models.ForecastBenchmarkPredictionPoint(
                    date=point.date,
                    observed_value=point.observed_value,
                    predicted_value=point.predicted_value,
                    lower=point.lower,
                    upper=point.upper,
                    unit=point.unit,
                )
            )
        run.results.append(result_row)
    db.add(run)
    db.commit()
    return _get_benchmark_run(db, run.id)


def get_forecast_benchmark(db: Session, run_id: int) -> models.ForecastBenchmarkRun | None:
    return _get_benchmark_run(db, run_id, required=False)


def list_country_forecast_benchmarks(db: Session, country_iso3: str) -> list[models.ForecastBenchmarkRun]:
    country = _validate_country(country_iso3)
    return (
        db.execute(
            select(models.ForecastBenchmarkRun)
            .where(models.ForecastBenchmarkRun.country_iso3 == country)
            .options(
                selectinload(models.ForecastBenchmarkRun.results).selectinload(models.ForecastBenchmarkResult.points)
            )
            .order_by(models.ForecastBenchmarkRun.created_at.desc(), models.ForecastBenchmarkRun.id.desc())
        )
        .scalars()
        .all()
    )


def rank_benchmark_results(results: list[ForecastBenchmarkResultRead]) -> list[dict[str, object]]:
    def sort_key(result: ForecastBenchmarkResultRead) -> tuple[int, float, float, str]:
        complete_rank = 0 if result.status == "complete" else 1
        smape = result.smape if result.smape is not None else float("inf")
        rmse = result.rmse if result.rmse is not None else float("inf")
        return (complete_rank, smape, rmse, result.model_id)

    ranked = sorted(results, key=sort_key)
    output: list[dict[str, object]] = []
    rank = 1
    for result in ranked:
        is_complete = result.status == "complete"
        output.append(
            {
                "rank": rank if is_complete else None,
                "model_id": result.model_id,
                "display_name": result.display_name or result.model_name,
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


def _series_diagnostics(
    db: Session,
    request: ForecastBenchmarkRequest,
    country: str,
    series: list[tuple[date, float]],
    frequency: str,
) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    if len(series) < request.horizon_periods + 8:
        notes.append(
            {
                "code": "short_series",
                "message": "The stored aggregate series is short for benchmark modeling; some models may return insufficient_data.",
                "severity": "warning",
            }
        )
    if _has_irregular_dates(series, frequency):
        notes.append(
            {
                "code": "irregular_frequency",
                "message": "Observation dates are not perfectly regular for the requested frequency; the backend did not fabricate missing observations.",
                "severity": "warning",
            }
        )

    query = select(models.Observation).where(
        models.Observation.country_iso3 == country,
        models.Observation.source_id == request.source_id,
        models.Observation.metric == request.metric,
    )
    if request.unit is not None:
        query = query.where(models.Observation.unit == request.unit)
    rows = db.execute(query).scalars().all()
    if rows and any(row.unit is None for row in rows):
        notes.append(
            {
                "code": "missing_units",
                "message": "Some matching observations do not include units.",
                "severity": "info",
            }
        )
    if rows and any(not row.provenance_url for row in rows):
        notes.append(
            {
                "code": "missing_provenance",
                "message": "Some matching observations lack provenance_url; benchmark is allowed but should be interpreted cautiously.",
                "severity": "warning",
            }
        )
    quality_scores = [row.quality_score for row in rows if row.quality_score is not None]
    if quality_scores and mean(quality_scores) < 0.5:
        notes.append(
            {
                "code": "low_quality_score",
                "message": "Average observation quality_score is below 0.5.",
                "severity": "warning",
            }
        )
    return notes


def _benchmark_model(
    db: Session,
    model_id: str,
    train: list[tuple[date, float]],
    test: list[tuple[date, float]],
    request: ForecastBenchmarkRequest,
    country: str,
    season_length: int,
    frequency: str,
    data_quality_notes: list[dict[str, str]],
) -> ForecastBenchmarkResultRead:
    if model_id in BUILTIN_MODELS:
        return _benchmark_builtin(model_id, train, test, request.unit, season_length, frequency, data_quality_notes)
    return _benchmark_uploaded(db, model_id, test, request, country, train, data_quality_notes)


def _benchmark_builtin(
    model_id: str,
    train: list[tuple[date, float]],
    test: list[tuple[date, float]],
    unit: str | None,
    season_length: int,
    frequency: str,
    data_quality_notes: list[dict[str, str]],
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
        )

    try:
        if model_id == "naive_last_value":
            predictions = [train[-1][1]] * len(test)
        elif model_id == "seasonal_naive":
            pattern = [value for _day, value in train[-season_length:]]
            predictions = [pattern[index % len(pattern)] for index in range(len(test))]
        elif model_id == "statsmodels_arima":
            predictions = _forecast_arima([value for _day, value in train], len(test))
        elif model_id == "statsmodels_sarima":
            predictions = _forecast_sarima([value for _day, value in train], len(test), season_length)
        elif model_id == "statsforecast_autoets":
            dependency_status = _dependency_status(model)
            if dependency_status != "available":
                return _model_unavailable_result(model, n_train=len(train), n_test=len(test), train=train, test=test)
            predictions, autoets_warnings = _forecast_autoets(train, len(test), frequency)
        else:
            return _insufficient_result(
                model_id,
                "Unknown built-in model.",
                n_train=len(train),
                n_test=len(test),
                train=train,
                test=test,
                data_quality_notes=data_quality_notes,
            )
    except Exception as exc:  # statsmodels can raise data-shape or convergence exceptions.
        return _failed_result(model, str(exc), n_train=len(train), n_test=len(test), train=train, test=test)

    if model_id != "statsforecast_autoets":
        autoets_warnings = []

    return _complete_result(
        model_id=model.id,
        model_name=model.name,
        model_kind=model.model_kind,
        predictions=predictions,
        test=test,
        unit=unit,
        limitations=list(model.limitations),
        warnings=[
            BENCHMARK_WARNING,
            *({"code": "model_warning", "message": warning, "severity": "info"} for warning in model.warnings),
            *autoets_warnings,
        ],
        n_train=len(train),
        train=train,
        data_quality_notes=data_quality_notes,
    )


def _benchmark_uploaded(
    db: Session,
    model_id: str,
    test: list[tuple[date, float]],
    request: ForecastBenchmarkRequest,
    country: str,
    train: list[tuple[date, float]],
    data_quality_notes: list[dict[str, str]],
) -> ForecastBenchmarkResultRead:
    model = db.get(models.ForecastModel, model_id)
    if model is None:
        return _insufficient_result(
            model_id,
            "Model is not registered as a built-in model or uploaded prediction model.",
            n_train=len(train),
            n_test=len(test),
            train=train,
            test=test,
            data_quality_notes=data_quality_notes,
        )

    test_dates = {day for day, _value in test}
    query = select(models.UploadedForecastPredictionPoint).where(
        models.UploadedForecastPredictionPoint.model_id == model_id,
        models.UploadedForecastPredictionPoint.country_iso3 == country,
        models.UploadedForecastPredictionPoint.source_id == request.source_id,
        models.UploadedForecastPredictionPoint.metric == request.metric,
        models.UploadedForecastPredictionPoint.target_date.in_(test_dates),
    )
    if request.unit is not None:
        query = query.where(models.UploadedForecastPredictionPoint.unit == request.unit)
    rows = db.execute(query).scalars().all()
    by_date = {row.target_date: row for row in rows}
    matched = [(day, observed, by_date[day]) for day, observed in test if day in by_date]
    if not matched:
        return _insufficient_result(
            model_id,
            "No uploaded prediction points matched the benchmark holdout dates.",
            n_train=len(train),
            n_test=len(test),
            train=train,
            test=test,
            data_quality_notes=data_quality_notes,
        )

    predictions = [row.predicted_value for _day, _observed, row in matched]
    observed = [(day, value) for day, value, _row in matched]
    result = _complete_result(
        model_id=model.id,
        model_name=model.name,
        model_kind=model.model_kind,
        predictions=predictions,
        test=observed,
        unit=request.unit,
        limitations=_string_list(model.limitations),
        warnings=[BENCHMARK_WARNING],
        n_train=len(train),
        train=train,
        data_quality_notes=data_quality_notes,
        provenance_url=model.provenance_url,
    )
    result.status = "complete" if len(matched) == len(test) else "partial"
    if result.status == "partial":
        result.warnings.append(
            {
                "code": "partial_uploaded_predictions",
                "message": "Uploaded predictions matched only part of the benchmark holdout window.",
                "severity": "warning",
            }
        )
    for point, (_day, _observed, row) in zip(result.points, matched, strict=True):
        point.lower = row.lower
        point.upper = row.upper
        point.unit = row.unit
    return result


def _complete_result(
    *,
    model_id: str,
    model_name: str,
    model_kind: str,
    predictions: Iterable[float],
    test: list[tuple[date, float]],
    unit: str | None,
    limitations: list[str],
    warnings: list[dict[str, str]],
    n_train: int,
    train: list[tuple[date, float]],
    data_quality_notes: list[dict[str, str]],
    provenance_url: str | None = None,
) -> ForecastBenchmarkResultRead:
    prediction_values = [float(value) for value in predictions]
    observed_values = [value for _day, value in test]
    metrics = _metrics(observed_values, prediction_values)
    return ForecastBenchmarkResultRead(
        model_id=model_id,
        model_name=model_name,
        display_name=model_name,
        model_kind=model_kind,
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
        points=[
            ForecastBenchmarkPointRead(
                date=day,
                observed_value=float(observed),
                predicted_value=float(predicted),
                unit=unit,
            )
            for (day, observed), predicted in zip(test, prediction_values, strict=True)
        ],
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


def _observed_series(db: Session, request: ForecastBenchmarkRequest, country: str) -> list[tuple[date, float]]:
    query = select(models.Observation).where(
        models.Observation.country_iso3 == country,
        models.Observation.source_id == request.source_id,
        models.Observation.metric == request.metric,
    )
    if request.unit is not None:
        query = query.where(models.Observation.unit == request.unit)
    rows = db.execute(query.order_by(models.Observation.observed_at.asc(), models.Observation.id.asc())).scalars().all()
    by_date: dict[date, list[float]] = defaultdict(list)
    for row in rows:
        observed_date = row.observed_at.date()
        if request.train_start and observed_date < request.train_start:
            continue
        if request.train_end and observed_date > request.train_end:
            continue
        value = row.normalized_value if row.normalized_value is not None else row.value
        by_date[observed_date].append(float(value))
    frame = pd.DataFrame(
        [{"date": day, "value": mean(values)} for day, values in by_date.items()]
    ).sort_values("date") if by_date else pd.DataFrame(columns=["date", "value"])
    return [(row.date, float(row.value)) for row in frame.itertuples(index=False)]


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


def _selected_model_ids(db: Session, request: ForecastBenchmarkRequest, country: str) -> list[str]:
    if request.model_ids:
        return list(dict.fromkeys(request.model_ids))
    uploaded_model_ids = [
        row[0]
        for row in db.execute(
            select(models.UploadedForecastPredictionPoint.model_id)
            .where(
                models.UploadedForecastPredictionPoint.country_iso3 == country,
                models.UploadedForecastPredictionPoint.source_id == request.source_id,
                models.UploadedForecastPredictionPoint.metric == request.metric,
            )
            .group_by(models.UploadedForecastPredictionPoint.model_id)
        ).all()
    ]
    builtin_ids = [
        model.id
        for model in BUILTIN_MODELS.values()
        if model.id != "statsforecast_autoets" or _dependency_status(model) == "available"
    ]
    return builtin_ids + [model_id for model_id in uploaded_model_ids if model_id not in BUILTIN_MODELS]


def _insufficient_result(
    model_id: str,
    message: str,
    *,
    n_train: int = 0,
    n_test: int = 0,
    train: list[tuple[date, float]] | None = None,
    test: list[tuple[date, float]] | None = None,
    data_quality_notes: list[dict[str, str]] | None = None,
) -> ForecastBenchmarkResultRead:
    model = BUILTIN_MODELS.get(model_id)
    model_name = model.name if model else model_id
    model_kind = model.model_kind if model else "uploaded_predictions"
    limitations = list(model.limitations) if model else []
    train = train or []
    test = test or []
    return ForecastBenchmarkResultRead(
        model_id=model_id,
        model_name=model_name,
        display_name=model_name,
        model_kind=model_kind,
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
) -> ForecastBenchmarkResultRead:
    train = train or []
    test = test or []
    return ForecastBenchmarkResultRead(
        model_id=model.id,
        model_name=model.name,
        display_name=model.name,
        model_kind=model.model_kind,
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
) -> ForecastBenchmarkResultRead:
    train = train or []
    test = test or []
    return ForecastBenchmarkResultRead(
        model_id=model.id,
        model_name=model.name,
        display_name=model.name,
        model_kind=model.model_kind,
        status="model_unavailable",
        n_train=n_train,
        n_test=n_test,
        train_start=train[0][0] if train else None,
        train_end=train[-1][0] if train else None,
        test_start=test[0][0] if test else None,
        test_end=test[-1][0] if test else None,
        warnings=[
            BENCHMARK_WARNING,
            {
                "code": "missing_optional_dependency",
                "message": "StatsForecast AutoETS requires the optional `statsforecast` dependency. Install backend with `pip install -e \".[dev,forecast]\"`.",
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
    if "complete" in statuses or "partial" in statuses:
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
        accepts_uploaded_code=False,
        accepts_prediction_csv=False,
        required_observation_count=model.min_train_points,
        supported_frequencies=list(model.supported_frequencies),
        required_frequency_notes=model.required_frequency_notes,
        supports_prediction_intervals=model.supports_prediction_intervals,
        default_parameters=dict(model.default_parameters or {}),
        description=model.description,
        owner="Sentinel Atlas",
        status="builtin",
        safety_notes=list(model.safety_notes),
        citation_or_package_notes=model.citation_or_package_notes,
        dependency_status=_dependency_status(model),
        registry_version=REGISTRY_VERSION,
        limitations=list(model.limitations),
        warnings=[BENCHMARK_WARNING, *({"code": "model_warning", "message": warning, "severity": "info"} for warning in model.warnings)],
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
        required_frequency_notes="Uploaded predictions are matched to benchmark holdout target dates.",
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
    if model.dependency_name is None:
        return "available"
    return "available" if importlib.util.find_spec(model.dependency_name) is not None else "missing_optional_dependency"


def _get_benchmark_run(db: Session, run_id: int, *, required: bool = True) -> models.ForecastBenchmarkRun | None:
    run = (
        db.execute(
            select(models.ForecastBenchmarkRun)
            .where(models.ForecastBenchmarkRun.id == run_id)
            .options(
                selectinload(models.ForecastBenchmarkRun.results).selectinload(models.ForecastBenchmarkResult.points)
            )
        )
        .scalars()
        .one_or_none()
    )
    if run is None and required:
        raise LookupError(f"Forecast benchmark {run_id} not found")
    return run


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
