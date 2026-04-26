from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import models
from app.schemas.forecast_challenge import ForecastChallengeMode
from app.schemas.prediction_set import (
    BuiltInPredictionRunResponse,
    BuiltInPredictionRunResult,
    ChallengePredictionUploadResult,
    PredictionPointResponse,
    PredictionSetResponse,
)
from app.services.forecast_benchmark import (
    BENCHMARK_LIMITATIONS,
    FAIRNESS_WARNING,
    BUILTIN_MODELS,
    EXPERIMENTAL_TABPFN_TS_MODEL_ID,
    _dependency_status,
    _forecast_arima,
    _forecast_autoets,
    _forecast_sarima,
    _legacy_season_length,
    default_builtin_model_ids,
    is_experimental_tabpfn_enabled,
    normalize_prediction_upload_row,
    parse_prediction_csv,
)
from app.services.experimental_tabpfn_ts import forecast_with_tabpfn_ts
from app.services.normalization import NormalizationError, coerce_date
from app.services.submissions import normalize_submitter_metadata, redact_private_submitter_fields


CHALLENGE_PREDICTION_WARNING = {
    "code": "challenge_prediction_only",
    "message": (
        "Built-in challenge prediction sets are benchmark-only metric forecasts, not public-health alerts, "
        "risk scores, Rt/R0 estimates, validated epidemiological predictions, or operational guidance."
    ),
    "severity": "warning",
}

OVERLAY_WARNING = {
    "code": "overlay_only",
    "message": "Prediction set was stored for visual overlay only and will not receive benchmark scores.",
    "severity": "warning",
}


@dataclass(frozen=True)
class BuiltinPrediction:
    model_id: str
    status: str
    values: list[float]
    warnings: list[dict[str, str]]
    limitations: list[str]


def run_builtin_predictions_for_challenge(
    db: Session,
    challenge_id: int,
    model_ids: list[str] | None = None,
    *,
    overwrite_existing: bool = False,
) -> BuiltInPredictionRunResponse:
    challenge = _get_challenge_row(db, challenge_id)
    selected = list(dict.fromkeys(model_ids or default_builtin_model_ids()))
    prediction_sets: list[PredictionSetResponse] = []
    results: list[BuiltInPredictionRunResult] = []

    for model_id in selected:
        if model_id not in BUILTIN_MODELS:
            results.append(
                BuiltInPredictionRunResult(
                    model_id=model_id,
                    status="insufficient_data",
                    warnings=[
                        CHALLENGE_PREDICTION_WARNING,
                        {"code": "unknown_model", "message": "Unknown built-in forecast model.", "severity": "warning"},
                    ],
                    limitations=BENCHMARK_LIMITATIONS,
                )
            )
            continue

        existing = _existing_builtin_prediction_sets(db, challenge.id, model_id)
        if existing and not overwrite_existing:
            prediction_set = existing[0]
            prediction_sets.append(prediction_set_to_response(prediction_set))
            results.append(
                BuiltInPredictionRunResult(
                    model_id=model_id,
                    status="complete",
                    prediction_set_id=prediction_set.id,
                    warnings=[
                        CHALLENGE_PREDICTION_WARNING,
                        {
                            "code": "existing_prediction_set",
                            "message": "Existing built-in prediction set was reused because overwriteExisting=false.",
                            "severity": "info",
                        },
                    ],
                    limitations=prediction_set.limitations_json or [],
                )
            )
            continue

        if existing and overwrite_existing:
            for row in existing:
                db.delete(row)
            db.flush()

        prediction = run_single_builtin_model(challenge, model_id)
        if prediction.status != "complete":
            results.append(
                BuiltInPredictionRunResult(
                    model_id=model_id,
                    status=prediction.status,
                    prediction_set_id=None,
                    warnings=prediction.warnings,
                    limitations=prediction.limitations,
                )
            )
            continue

        prediction_set = store_prediction_set(db, challenge, model_id, prediction)
        prediction_sets.append(prediction_set_to_response(prediction_set))
        results.append(
            BuiltInPredictionRunResult(
                model_id=model_id,
                status="complete",
                prediction_set_id=prediction_set.id,
                warnings=prediction.warnings,
                limitations=prediction.limitations,
            )
        )

    db.commit()
    refreshed_sets = [get_prediction_set(db, item.id) for item in prediction_sets]
    return BuiltInPredictionRunResponse(
        challenge_id=challenge_id,
        prediction_sets=[item for item in refreshed_sets if item is not None],
        results=results,
    )


def upload_prediction_csv_for_challenge(
    db: Session,
    challenge_id: int,
    content: str,
    *,
    model_id: str | None = None,
    model_name: str | None = None,
    unit: str | None = None,
    method_summary: str | None = None,
    model_url: str | None = None,
    code_url: str | None = None,
    submitter_name: str | None = None,
    submitter_email: str | None = None,
    organization: str | None = None,
    provenance_url: str | None = None,
    limitations: str | None = None,
    submission_track: str | None = None,
    visibility: str | None = None,
    disclosure_notes: str | None = None,
    verified_group: bool = False,
    allow_metric_overlay: bool = False,
) -> ChallengePredictionUploadResult:
    challenge = _get_challenge_row(db, challenge_id)
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
    )
    defaults = {
        "country_iso3": challenge.country_iso3,
        "source_id": challenge.source_id,
        "metric": challenge.metric,
        "unit": unit if unit not in (None, "") else challenge.unit,
        "model_id": model_id,
        "model_name": model_name,
        "frequency": challenge.frequency,
        "horizon_periods": challenge.horizon_periods,
    }
    raw_rows = parse_prediction_csv(content)
    normalized_rows: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    for index, row in enumerate(raw_rows, start=2):
        try:
            normalized_rows.append(normalize_prediction_upload_row(row, defaults=defaults))
        except NormalizationError as exc:
            errors.append({"row": index, "error": str(exc)})

    if errors or not normalized_rows:
        return ChallengePredictionUploadResult(
            inserted_count=0,
            rejected_count=len(errors) if errors else len(raw_rows),
            validation_status="invalid",
            scoring_status="invalid",
            matched_challenge_id=challenge_id,
            errors=errors or [{"error": "No valid aggregate prediction rows were supplied."}],
            warnings=[CHALLENGE_PREDICTION_WARNING],
        )

    validation_status, validation_errors, validation_warnings = _validate_challenge_prediction_rows(
        challenge,
        normalized_rows,
        allow_metric_overlay=allow_metric_overlay,
    )
    if validation_status == "invalid":
        return ChallengePredictionUploadResult(
            inserted_count=0,
            rejected_count=len(normalized_rows),
            validation_status="invalid",
            scoring_status="invalid",
            matched_challenge_id=challenge_id,
            errors=validation_errors,
            warnings=[CHALLENGE_PREDICTION_WARNING, *validation_warnings],
        )

    first = normalized_rows[0]
    prediction_set = models.PredictionSet(
        challenge_id=challenge.id,
        model_id=str(first["model_id"]),
        model_name=str(first["model_name"]),
        prediction_source="user_uploaded",
        submission_track=submitter_metadata.submission_track,
        review_status=submitter_metadata.review_status,
        validation_status=validation_status,
        scoring_status="unscored" if validation_status == "overlay_only" else "pending_truth",
        submitter_id=submitter_metadata.submitter_id,
        country_iso3=str(first["country_iso3"]),
        source_id=str(first["source_id"]),
        signal_category=challenge.signal_category,
        metric=str(first["metric"]),
        unit=first["unit"],
        frequency=challenge.frequency,
        horizon_periods=challenge.horizon_periods,
        submitter_name=submitter_metadata.submitter_name,
        submitter_email=submitter_metadata.submitter_email,
        organization=submitter_metadata.organization,
        method_summary=submitter_metadata.method_summary,
        model_url=submitter_metadata.model_url,
        code_url=submitter_metadata.code_url,
        provenance_url=submitter_metadata.provenance_url or first["provenance_url"],
        visibility=submitter_metadata.visibility,
        disclosure_notes=submitter_metadata.disclosure_notes,
        limitations_json=_merge_limitations(first["limitations"], limitations),
        warnings_json=[
            CHALLENGE_PREDICTION_WARNING,
            FAIRNESS_WARNING,
            *submitter_metadata.warnings,
            *validation_warnings,
        ],
        created_at=datetime.now(UTC),
    )
    for row in normalized_rows:
        prediction_set.points.append(
            models.PredictionPoint(
                target_date=row["target_date"],
                predicted_value=row["predicted_value"],
                lower=row["lower"],
                upper=row["upper"],
                unit=row["unit"],
                generated_at=row["generated_at"],
                provenance_url=row["provenance_url"] or submitter_metadata.provenance_url,
                created_at=datetime.now(UTC),
            )
        )
    db.add(prediction_set)
    db.flush()

    if validation_status == "valid_for_snapshot":
        from app.services.forecast_scoring import score_prediction_set_against_challenge

        score = score_prediction_set_against_challenge(prediction_set, challenge, db)
        scoring_status = score.status
    else:
        scoring_status = "unscored"
        prediction_set.scoring_status = scoring_status

    db.commit()
    return ChallengePredictionUploadResult(
        prediction_set_id=prediction_set.id,
        inserted_count=len(prediction_set.points),
        rejected_count=0,
        validation_status=validation_status,
        scoring_status=scoring_status,
        matched_challenge_id=challenge_id,
        warnings=prediction_set.warnings_json or [],
        errors=[],
    )


def run_single_builtin_model(
    snapshot: models.ForecastChallengeSnapshot,
    model_id: str,
) -> BuiltinPrediction:
    model = BUILTIN_MODELS[model_id]
    train = _train_series(snapshot)
    target_dates = _target_dates(snapshot)
    season_length = _legacy_season_length(snapshot.frequency)
    base_warnings = [CHALLENGE_PREDICTION_WARNING]
    limitations = list(model.limitations) + BENCHMARK_LIMITATIONS

    if not target_dates:
        return BuiltinPrediction(
            model_id=model_id,
            status="insufficient_data",
            values=[],
            warnings=[
                *base_warnings,
                {"code": "missing_target_dates", "message": "Challenge has no target dates.", "severity": "warning"},
            ],
            limitations=limitations,
        )

    min_train_points = model.min_train_points
    if model_id == "seasonal_naive":
        min_train_points = season_length * 2
    elif model_id == "statsmodels_sarima":
        min_train_points = max(model.min_train_points, (season_length * 2) + 4)
    elif model_id == "statsforecast_autoets":
        dependency_status = _dependency_status(model)
        if dependency_status != "available":
            return BuiltinPrediction(
                model_id=model_id,
                status="model_unavailable",
                values=[],
                warnings=[
                    *base_warnings,
                    {
                        "code": "missing_optional_dependency",
                        "message": "Optional dependency statsforecast is not installed.",
                        "severity": "warning",
                    },
                ],
                limitations=limitations,
            )
    elif model_id == EXPERIMENTAL_TABPFN_TS_MODEL_ID:
        if not is_experimental_tabpfn_enabled():
            return BuiltinPrediction(
                model_id=model_id,
                status="experimental_disabled",
                values=[],
                warnings=[
                    *base_warnings,
                    {
                        "code": "experimental_disabled",
                        "message": (
                            "Experimental TabPFN-Time-Series is disabled. Set "
                            "SENTINEL_ENABLE_EXPERIMENTAL_TABPFN=true to request this benchmark explicitly."
                        ),
                        "severity": "warning",
                    },
                ],
                limitations=limitations,
            )
        dependency_status = _dependency_status(model)
        if dependency_status != "available":
            return BuiltinPrediction(
                model_id=model_id,
                status="model_unavailable",
                values=[],
                warnings=[
                    *base_warnings,
                    {
                        "code": "missing_optional_dependency",
                        "message": "Optional dependency tabpfn-time-series is not installed.",
                        "severity": "warning",
                    },
                ],
                limitations=limitations,
            )

    if len(train) < min_train_points:
        return BuiltinPrediction(
            model_id=model_id,
            status="insufficient_data",
            values=[],
            warnings=[
                *base_warnings,
                {
                    "code": "insufficient_data",
                    "message": f"Need at least {min_train_points} training observations for {model_id}.",
                    "severity": "warning",
                },
            ],
            limitations=limitations,
        )

    try:
        if model_id == "naive_last_value":
            values = [train[-1][1]] * len(target_dates)
            extra_warnings: list[dict[str, str]] = []
        elif model_id == "seasonal_naive":
            pattern = [value for _day, value in train[-season_length:]]
            values = [pattern[index % len(pattern)] for index in range(len(target_dates))]
            extra_warnings = []
        elif model_id == "statsmodels_arima":
            values = _forecast_arima([value for _day, value in train], len(target_dates))
            extra_warnings = []
        elif model_id == "statsmodels_sarima":
            values = _forecast_sarima([value for _day, value in train], len(target_dates), season_length)
            extra_warnings = []
        elif model_id == "statsforecast_autoets":
            values, extra_warnings = _forecast_autoets(train, len(target_dates), snapshot.frequency)
        elif model_id == EXPERIMENTAL_TABPFN_TS_MODEL_ID:
            values, extra_warnings = forecast_with_tabpfn_ts(train, target_dates, snapshot.frequency)
        else:
            values = []
            extra_warnings = []
    except Exception as exc:
        return BuiltinPrediction(
            model_id=model_id,
            status="failed",
            values=[],
            warnings=[
                *base_warnings,
                {"code": "model_failed", "message": str(exc)[:500], "severity": "warning"},
            ],
            limitations=limitations,
        )

    return BuiltinPrediction(
        model_id=model_id,
        status="complete",
        values=[float(value) for value in values],
        warnings=[*base_warnings, *extra_warnings],
        limitations=limitations,
    )


def store_prediction_set(
    db: Session,
    snapshot: models.ForecastChallengeSnapshot,
    model_id: str,
    prediction: BuiltinPrediction,
) -> models.PredictionSet:
    model = BUILTIN_MODELS[model_id]
    scoring_status = (
        "pending_truth"
        if snapshot.mode == ForecastChallengeMode.PROSPECTIVE_CHALLENGE.value
        else "unscored"
    )
    submitter_metadata = normalize_submitter_metadata(
        db,
        submitter_name="Sentinel Atlas backend",
        organization="Sentinel Atlas",
        submission_track="internal_baseline",
        method_summary=model.description,
        visibility="public",
        disclosure_notes="Internal baseline generated by the Sentinel Atlas backend.",
    )
    prediction_set = models.PredictionSet(
        challenge_id=snapshot.id,
        model_id=model.id,
        model_name=model.name,
        prediction_source="built_in",
        submission_track="internal_baseline",
        review_status="approved",
        validation_status="valid_for_snapshot",
        scoring_status=scoring_status,
        submitter_id=submitter_metadata.submitter_id,
        country_iso3=snapshot.country_iso3,
        source_id=snapshot.source_id,
        signal_category=snapshot.signal_category,
        metric=snapshot.metric,
        unit=snapshot.unit,
        frequency=snapshot.frequency,
        horizon_periods=snapshot.horizon_periods,
        submitter_name="Sentinel Atlas backend",
        organization="Sentinel Atlas",
        visibility="public",
        method_summary=model.description,
        provenance_url=model.citation_or_package_notes,
        disclosure_notes=submitter_metadata.disclosure_notes,
        limitations_json=prediction.limitations,
        warnings_json=prediction.warnings,
        created_at=datetime.now(UTC),
    )
    for target_date, value in zip(_target_dates(snapshot), prediction.values, strict=True):
        prediction_set.points.append(
            models.PredictionPoint(
                target_date=target_date,
                predicted_value=float(value),
                unit=snapshot.unit,
                generated_at=datetime.now(UTC),
            )
        )
    db.add(prediction_set)
    db.flush()
    return prediction_set


def list_prediction_sets(
    db: Session,
    *,
    challenge_id: int | None = None,
    country_iso3: str | None = None,
    source_id: str | None = None,
    metric: str | None = None,
) -> list[PredictionSetResponse]:
    query = select(models.PredictionSet).options(
        selectinload(models.PredictionSet.points),
        selectinload(models.PredictionSet.submitter),
    )
    if challenge_id is not None:
        query = query.where(models.PredictionSet.challenge_id == challenge_id)
    if country_iso3:
        query = query.where(models.PredictionSet.country_iso3 == country_iso3.upper())
    if source_id:
        query = query.where(models.PredictionSet.source_id == source_id)
    if metric:
        query = query.where(models.PredictionSet.metric == metric)
    rows = db.execute(query.order_by(models.PredictionSet.created_at.desc(), models.PredictionSet.id.desc())).scalars().all()
    return [prediction_set_to_response(row) for row in rows]


def get_prediction_set(db: Session, prediction_set_id: int) -> PredictionSetResponse | None:
    row = (
        db.execute(
            select(models.PredictionSet)
            .where(models.PredictionSet.id == prediction_set_id)
            .options(
                selectinload(models.PredictionSet.points),
                selectinload(models.PredictionSet.submitter),
            )
        )
        .scalars()
        .one_or_none()
    )
    return prediction_set_to_response(row) if row else None


def prediction_set_to_response(row: models.PredictionSet) -> PredictionSetResponse:
    points = sorted(row.points, key=lambda point: point.target_date)
    submitter_fields = redact_private_submitter_fields(row)
    return PredictionSetResponse(
        id=row.id,
        challenge_id=row.challenge_id,
        submitter_id=row.submitter_id,
        model_id=row.model_id,
        model_name=row.model_name,
        prediction_source=row.prediction_source,
        submission_track=row.submission_track,
        review_status=row.review_status,
        validation_status=row.validation_status,
        scoring_status=row.scoring_status,
        country_iso3=row.country_iso3,
        source_id=row.source_id,
        signal_category=row.signal_category,
        metric=row.metric,
        unit=row.unit,
        frequency=row.frequency,
        horizon_periods=row.horizon_periods,
        submitter_display_name=submitter_fields["submitter_display_name"],
        submitter_name=row.submitter_name,
        submitter_email=None,
        organization=submitter_fields["organization"],
        verification_status=submitter_fields["verification_status"],
        visibility=row.visibility,
        method_summary=row.method_summary,
        model_url=row.model_url,
        code_url=row.code_url,
        provenance_url=row.provenance_url,
        disclosure_notes=row.disclosure_notes,
        limitations=row.limitations_json or [],
        warnings=row.warnings_json or [],
        created_at=row.created_at,
        updated_at=row.updated_at,
        points=[
            PredictionPointResponse(
                id=point.id,
                prediction_set_id=point.prediction_set_id,
                target_date=point.target_date,
                predicted_value=point.predicted_value,
                lower=point.lower,
                upper=point.upper,
                unit=point.unit,
                generated_at=point.generated_at,
                provenance_url=point.provenance_url,
                created_at=point.created_at,
            )
            for point in points
        ],
    )


def _validate_challenge_prediction_rows(
    challenge: models.ForecastChallengeSnapshot,
    rows: list[dict[str, object]],
    *,
    allow_metric_overlay: bool,
) -> tuple[str, list[dict[str, object]], list[dict[str, str]]]:
    errors: list[dict[str, object]] = []
    warnings: list[dict[str, str]] = []
    if not rows:
        return "invalid", [{"code": "invalid_predictions", "message": "Prediction set contains no rows."}], warnings

    first = rows[0]
    consistency_errors = _validate_prediction_set_consistency(rows)
    if consistency_errors:
        errors.extend(consistency_errors)

    if first.get("country_iso3") != challenge.country_iso3:
        errors.append({"code": "wrong_country", "message": "Prediction country does not match the challenge."})
    if first.get("source_id") != challenge.source_id:
        errors.append({"code": "wrong_source", "message": "Prediction source does not match the challenge."})

    overlay_only = False
    if first.get("metric") != challenge.metric:
        if allow_metric_overlay:
            overlay_only = True
            warnings.append(
                {
                    "code": "metric_mismatch_overlay",
                    "message": "Prediction metric does not match the challenge metric; stored for overlay only.",
                    "severity": "warning",
                }
            )
        else:
            errors.append({"code": "wrong_metric", "message": "Prediction metric does not match the challenge."})
    if challenge.unit is not None and first.get("unit") not in (challenge.unit, None, ""):
        overlay_only = True
        warnings.append(
            {
                "code": "unit_mismatch_overlay",
                "message": "Prediction unit does not match the challenge unit; stored for overlay only and not benchmark scored.",
                "severity": "warning",
            }
        )

    expected = {day.isoformat() for day in _target_dates(challenge)}
    supplied: list[str] = []
    for row in rows:
        target_date = row.get("target_date")
        supplied.append(target_date.isoformat() if isinstance(target_date, date) else str(target_date))
        lower = row.get("lower")
        upper = row.get("upper")
        predicted = row.get("predicted_value")
        if lower is not None and upper is not None and float(lower) > float(upper):
            errors.append({"code": "invalid_interval", "message": "Prediction lower bound is greater than upper bound."})
        if lower is not None and predicted is not None and float(lower) > float(predicted):
            errors.append({"code": "invalid_interval", "message": "Prediction lower bound is greater than predicted value."})
        if upper is not None and predicted is not None and float(predicted) > float(upper):
            errors.append({"code": "invalid_interval", "message": "Prediction predicted value is greater than upper bound."})

    supplied_set = set(supplied)
    duplicate_dates = sorted({day for day in supplied if supplied.count(day) > 1})
    missing = sorted(expected - supplied_set)
    extra = sorted(supplied_set - expected)
    if duplicate_dates:
        errors.append({"code": "duplicate_target_dates", "message": "Prediction CSV contains duplicate target dates.", "dates": duplicate_dates})
    if missing:
        errors.append({"code": "missing_target_dates", "message": "Prediction CSV is missing challenge target dates.", "dates": missing})
    if extra:
        errors.append({"code": "extra_target_dates", "message": "Prediction CSV includes dates outside the challenge target dates.", "dates": extra})
    if errors:
        return "invalid", errors, warnings
    if overlay_only:
        return "overlay_only", [], [OVERLAY_WARNING, *warnings]
    return "valid_for_snapshot", [], warnings


def _validate_prediction_set_consistency(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    keys = ("model_id", "model_name", "country_iso3", "source_id", "metric", "unit")
    errors = []
    for key in keys:
        values = {row.get(key) for row in rows}
        if len(values) > 1:
            errors.append({"code": "mixed_prediction_set", "message": f"Prediction CSV contains multiple {key} values."})
    return errors


def _merge_limitations(row_limitations: object, form_limitations: str | None) -> list[str]:
    output: list[str] = []
    if isinstance(row_limitations, list):
        output.extend(str(item) for item in row_limitations if item not in (None, ""))
    elif row_limitations not in (None, ""):
        output.append(str(row_limitations))
    if form_limitations:
        output.extend(item.strip() for item in form_limitations.split(";") if item.strip())
    return output


def _existing_builtin_prediction_sets(
    db: Session,
    challenge_id: int,
    model_id: str,
) -> list[models.PredictionSet]:
    return (
        db.execute(
            select(models.PredictionSet)
            .where(
                models.PredictionSet.challenge_id == challenge_id,
                models.PredictionSet.model_id == model_id,
                models.PredictionSet.prediction_source == "built_in",
                models.PredictionSet.submission_track == "internal_baseline",
            )
            .options(selectinload(models.PredictionSet.points))
            .order_by(models.PredictionSet.created_at.desc(), models.PredictionSet.id.desc())
        )
        .scalars()
        .all()
    )


def _get_challenge_row(db: Session, challenge_id: int) -> models.ForecastChallengeSnapshot:
    row = db.get(models.ForecastChallengeSnapshot, challenge_id)
    if row is None:
        raise ValueError("Forecast challenge snapshot not found")
    return row


def _train_series(snapshot: models.ForecastChallengeSnapshot) -> list[tuple[date, float]]:
    return [
        (coerce_date(row["date"]), float(row["value"]))
        for row in snapshot.train_rows_json or []
        if coerce_date(row.get("date")) is not None
    ]


def _target_dates(snapshot: models.ForecastChallengeSnapshot) -> list[date]:
    return [day for day in (coerce_date(value) for value in snapshot.target_dates_json or []) if day is not None]
