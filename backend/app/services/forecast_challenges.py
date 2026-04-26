from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
from statistics import mean
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.utils import ensure_country
from app.db import models
from app.schemas.forecast_challenge import (
    ForecastChallengeCreateRequest,
    ForecastChallengeListItem,
    ForecastChallengeMode,
    ForecastChallengePreviewRequest,
    ForecastChallengePreviewResponse,
    ForecastChallengeSnapshotResponse,
    ForecastChallengeStatus,
    PredictionTemplateRow,
)
from app.services.normalization import coerce_date, normalize_iso3, serializable


SUPPORTED_FREQUENCIES = {"daily", "weekly", "monthly"}
DEFAULT_SPLIT_STRATEGY = "last_n_periods"
MIN_TRAIN_POINTS = 8
MIN_TARGET_PERIODS = 2

CHALLENGE_LIMITATIONS = [
    "Forecast challenge snapshots use stored aggregate observations only.",
    "Prediction templates do not include observed truth values.",
    "The backend does not fabricate missing observations, future truth values, or public-health alerts.",
    "Historical or prospective challenge outputs are not validated pandemic predictions.",
]


@dataclass(frozen=True)
class ChallengeBuild:
    response: ForecastChallengeSnapshotResponse
    train_rows: list[dict[str, object]]
    holdout_rows: list[dict[str, object]]


def preview_forecast_challenge(
    db: Session,
    request: ForecastChallengePreviewRequest,
) -> ForecastChallengePreviewResponse:
    build = _build_challenge(db, request)
    return ForecastChallengePreviewResponse(
        challenge_snapshot=build.response,
        train_preview=build.train_rows[:10],
        prediction_template=build_prediction_template(build.response),
    )


def create_forecast_challenge(
    db: Session,
    request: ForecastChallengeCreateRequest,
) -> ForecastChallengeSnapshotResponse:
    build = _build_challenge(db, request)
    row = models.ForecastChallengeSnapshot(
        mode=build.response.mode.value,
        country_iso3=build.response.country_iso3,
        source_id=build.response.source_id,
        signal_category=build.response.signal_category,
        metric=build.response.metric,
        unit=build.response.unit,
        frequency=build.response.frequency,
        horizon_periods=build.response.horizon_periods,
        split_strategy=build.response.split_strategy,
        cutoff_at=build.response.cutoff_at,
        train_start=build.response.train_start,
        train_end=build.response.train_end,
        target_start=build.response.target_start,
        target_end=build.response.target_end,
        target_dates_json=[day.isoformat() for day in build.response.target_dates],
        observation_ids_json=build.response.observation_ids,
        train_observation_ids_json=build.response.train_observation_ids,
        holdout_observation_ids_json=build.response.holdout_observation_ids,
        train_rows_json=serializable(build.train_rows),
        holdout_rows_json=serializable(build.holdout_rows),
        dataset_hash=build.response.dataset_hash,
        status=build.response.status.value,
        quality_warnings_json=build.response.warnings,
        limitations_json=build.response.limitations,
        provenance_json=build.response.provenance,
        created_at=build.response.created_at or datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _challenge_response_from_row(row)


def get_forecast_challenge(db: Session, challenge_id: int) -> ForecastChallengeSnapshotResponse | None:
    row = db.get(models.ForecastChallengeSnapshot, challenge_id)
    return _challenge_response_from_row(row) if row else None


def list_forecast_challenges(
    db: Session,
    *,
    country_iso3: str | None = None,
    source_id: str | None = None,
    metric: str | None = None,
    mode: ForecastChallengeMode | str | None = None,
    status: ForecastChallengeStatus | str | None = None,
) -> list[ForecastChallengeListItem]:
    query = select(models.ForecastChallengeSnapshot)
    if country_iso3:
        query = query.where(models.ForecastChallengeSnapshot.country_iso3 == _validate_country(country_iso3))
    if source_id:
        query = query.where(models.ForecastChallengeSnapshot.source_id == source_id)
    if metric:
        query = query.where(models.ForecastChallengeSnapshot.metric == metric)
    if mode:
        query = query.where(models.ForecastChallengeSnapshot.mode == _mode_value(mode))
    if status:
        query = query.where(models.ForecastChallengeSnapshot.status == _status_value(status))
    rows = db.execute(
        query.order_by(models.ForecastChallengeSnapshot.created_at.desc(), models.ForecastChallengeSnapshot.id.desc())
    ).scalars().all()
    return [ForecastChallengeListItem.model_validate(_challenge_response_from_row(row)) for row in rows]


def build_prediction_template(snapshot: ForecastChallengeSnapshotResponse) -> list[PredictionTemplateRow]:
    return [
        PredictionTemplateRow(
            model_id=None,
            model_name=None,
            target_date=target_date,
            predicted_value=None,
            lower=None,
            upper=None,
            unit=snapshot.unit,
            country_iso3=snapshot.country_iso3,
            source_id=snapshot.source_id,
            metric=snapshot.metric,
            signal_category=snapshot.signal_category,
            generated_at=None,
            provenance_url=None,
        )
        for target_date in snapshot.target_dates
    ]


def _build_challenge(
    db: Session,
    request: ForecastChallengePreviewRequest | ForecastChallengeCreateRequest,
) -> ChallengeBuild:
    country = _validate_country(request.country_iso3)
    frequency = _validate_frequency(request.frequency)
    horizon = _validate_horizon(request.horizon_periods)
    split_strategy = _validate_split_strategy(request.split_strategy)
    ensure_country(db, country)

    rows = _query_observation_rows(db, request, country)
    if request.mode == ForecastChallengeMode.RETROSPECTIVE_HOLDOUT:
        return build_retrospective_holdout_snapshot(request, rows, country, frequency, horizon, split_strategy)
    return build_prospective_challenge_snapshot(request, rows, country, frequency, horizon, split_strategy)


def build_retrospective_holdout_snapshot(
    request: ForecastChallengePreviewRequest | ForecastChallengeCreateRequest,
    observations: list[dict[str, object]],
    country: str,
    frequency: str,
    horizon: int,
    split_strategy: str,
) -> ChallengeBuild:
    train_rows, holdout_rows = _split_last_n(observations, horizon)
    warnings = _quality_warnings(observations, train_rows, frequency, prospective=False)
    if len(train_rows) < MIN_TRAIN_POINTS or len(holdout_rows) < MIN_TARGET_PERIODS:
        status = ForecastChallengeStatus.INSUFFICIENT_DATA
        warnings.append(
            {
                "code": "insufficient_data",
                "message": f"Need at least {MIN_TRAIN_POINTS} training observations and {MIN_TARGET_PERIODS} target periods.",
                "severity": "warning",
            }
        )
    else:
        status = ForecastChallengeStatus.CLOSED

    target_dates = [row["date"] for row in holdout_rows]
    response = _snapshot_response(
        request=request,
        country=country,
        mode=ForecastChallengeMode.RETROSPECTIVE_HOLDOUT,
        frequency=frequency,
        horizon=horizon,
        split_strategy=split_strategy,
        cutoff_at=request.cutoff_at,
        train_rows=train_rows,
        holdout_rows=holdout_rows,
        target_dates=target_dates,
        status=status,
        warnings=warnings,
    )
    return ChallengeBuild(response=response, train_rows=train_rows, holdout_rows=holdout_rows)


def build_prospective_challenge_snapshot(
    request: ForecastChallengePreviewRequest | ForecastChallengeCreateRequest,
    observations: list[dict[str, object]],
    country: str,
    frequency: str,
    horizon: int,
    split_strategy: str,
) -> ChallengeBuild:
    cutoff = request.cutoff_at
    if cutoff is None and observations:
        cutoff = max(row["observed_at"] for row in observations)
    if cutoff is not None and cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=UTC)

    train_rows = [row for row in observations if cutoff is None or row["observed_at"] <= cutoff]
    warnings = _quality_warnings(observations, train_rows, frequency, prospective=True)
    if cutoff is None or not train_rows:
        target_dates: list[date] = []
    else:
        target_dates = infer_target_dates_for_prospective(train_rows[-1]["date"], frequency, horizon)

    if len(train_rows) < MIN_TRAIN_POINTS or len(target_dates) < MIN_TARGET_PERIODS:
        status = ForecastChallengeStatus.INSUFFICIENT_DATA
        warnings.append(
            {
                "code": "insufficient_data",
                "message": f"Need at least {MIN_TRAIN_POINTS} training observations and {MIN_TARGET_PERIODS} future target periods.",
                "severity": "warning",
            }
        )
    else:
        status = ForecastChallengeStatus.OPEN

    warnings.append(
        {
            "code": "prospective_truth_unavailable",
            "message": "Prospective challenge target observations do not exist yet and cannot be scored until aggregate truth arrives.",
            "severity": "info",
        }
    )

    response = _snapshot_response(
        request=request,
        country=country,
        mode=ForecastChallengeMode.PROSPECTIVE_CHALLENGE,
        frequency=frequency,
        horizon=horizon,
        split_strategy=split_strategy,
        cutoff_at=cutoff,
        train_rows=train_rows,
        holdout_rows=[],
        target_dates=target_dates,
        status=status,
        warnings=warnings,
    )
    return ChallengeBuild(response=response, train_rows=train_rows, holdout_rows=[])


def compute_dataset_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(serializable(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_frequency(observations: list[dict[str, object]], frequency: str) -> bool:
    if len(observations) < 3:
        return True
    dates = [row["date"] for row in observations]
    pairs = zip(dates, dates[1:], strict=False)
    if frequency == "daily":
        return all((right - left).days == 1 for left, right in pairs)
    if frequency == "weekly":
        return all((right - left).days == 7 for left, right in pairs)
    if frequency == "monthly":
        return all(_is_next_month(left, right) for left, right in pairs)
    return False


def infer_target_dates_for_prospective(
    train_end: date,
    frequency: str,
    horizon_periods: int,
) -> list[date]:
    targets: list[date] = []
    current = train_end
    for _index in range(horizon_periods):
        current = _advance_date(current, frequency)
        targets.append(current)
    return targets


def _snapshot_response(
    *,
    request: ForecastChallengePreviewRequest | ForecastChallengeCreateRequest,
    country: str,
    mode: ForecastChallengeMode,
    frequency: str,
    horizon: int,
    split_strategy: str,
    cutoff_at: datetime | None,
    train_rows: list[dict[str, object]],
    holdout_rows: list[dict[str, object]],
    target_dates: list[date],
    status: ForecastChallengeStatus,
    warnings: list[dict[str, str]],
) -> ForecastChallengeSnapshotResponse:
    all_rows = [*train_rows, *holdout_rows]
    observation_ids = [row["id"] for row in all_rows]
    train_ids = [row["id"] for row in train_rows]
    holdout_ids = [row["id"] for row in holdout_rows]
    provenance_urls = sorted({row["provenance_url"] for row in all_rows if row.get("provenance_url")})
    hash_payload = {
        "mode": mode.value,
        "country_iso3": country,
        "source_id": request.source_id,
        "signal_category": request.signal_category,
        "metric": request.metric,
        "unit": request.unit,
        "frequency": frequency,
        "horizon_periods": horizon,
        "split_strategy": split_strategy,
        "cutoff_at": cutoff_at.isoformat() if cutoff_at else None,
        "start_date": request.start_date.isoformat() if request.start_date else None,
        "end_date": request.end_date.isoformat() if request.end_date else None,
        "target_dates": [day.isoformat() for day in target_dates],
        "observation_ids": observation_ids,
        "train_observation_ids": train_ids,
        "holdout_observation_ids": holdout_ids,
        "values": [(row["id"], row["date"].isoformat(), row["value"]) for row in all_rows],
    }
    return ForecastChallengeSnapshotResponse(
        mode=mode,
        country_iso3=country,
        source_id=request.source_id,
        signal_category=request.signal_category,
        metric=request.metric,
        unit=request.unit,
        frequency=frequency,
        horizon_periods=horizon,
        split_strategy=split_strategy,
        cutoff_at=cutoff_at,
        train_start=train_rows[0]["date"] if train_rows else None,
        train_end=train_rows[-1]["date"] if train_rows else None,
        target_start=target_dates[0] if target_dates else None,
        target_end=target_dates[-1] if target_dates else None,
        target_dates=target_dates,
        observation_ids=observation_ids,
        train_observation_ids=train_ids,
        holdout_observation_ids=holdout_ids,
        n_train=len(train_rows),
        n_targets=len(target_dates),
        dataset_hash=compute_dataset_hash(hash_payload),
        status=status,
        warnings=warnings,
        limitations=CHALLENGE_LIMITATIONS,
        provenance={
            "source_id": request.source_id,
            "observation_count": len(all_rows),
            "train_observation_count": len(train_rows),
            "holdout_observation_count": len(holdout_rows),
            "provenance_urls": provenance_urls[:10],
        },
        created_at=datetime.now(UTC),
    )


def _query_observation_rows(
    db: Session,
    request: ForecastChallengePreviewRequest | ForecastChallengeCreateRequest,
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
    output: list[dict[str, object]] = []
    for row in rows:
        observed_date = row.observed_at.date()
        if request.start_date and observed_date < request.start_date:
            continue
        if request.end_date and observed_date > request.end_date:
            continue
        observed_at = row.observed_at if row.observed_at.tzinfo else row.observed_at.replace(tzinfo=UTC)
        output.append(
            {
                "id": row.id,
                "date": observed_date,
                "observed_at": observed_at,
                "value": float(row.normalized_value if row.normalized_value is not None else row.value),
                "unit": row.unit,
                "signal_category": row.signal_category,
                "quality_score": row.quality_score,
                "provenance_url": row.provenance_url,
            }
        )
    return output


def _split_last_n(
    rows: list[dict[str, object]],
    horizon_periods: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if not rows:
        return [], []
    n_target = min(horizon_periods, len(rows))
    return rows[:-n_target], rows[-n_target:]


def _quality_warnings(
    all_rows: list[dict[str, object]],
    train_rows: list[dict[str, object]],
    frequency: str,
    *,
    prospective: bool,
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if len(train_rows) < MIN_TRAIN_POINTS:
        warnings.append(
            {
                "code": "short_training_window",
                "message": "The training window is short for a forecast challenge.",
                "severity": "warning",
            }
        )
    if all_rows and not validate_frequency(all_rows, frequency):
        warnings.append(
            {
                "code": "irregular_frequency",
                "message": "Observation dates are not perfectly regular for the requested frequency; no dates were fabricated.",
                "severity": "warning",
            }
        )
    if all_rows and any(row.get("unit") is None for row in all_rows):
        warnings.append(
            {"code": "missing_unit", "message": "Some observations do not include units.", "severity": "info"}
        )
    if all_rows and any(not row.get("provenance_url") for row in all_rows):
        warnings.append(
            {
                "code": "missing_provenance",
                "message": "Some observations lack provenance_url; challenge creation is allowed but should be interpreted cautiously.",
                "severity": "warning",
            }
        )
    if all_rows and any(row.get("quality_score") is None for row in all_rows):
        warnings.append(
            {
                "code": "missing_quality_score",
                "message": "Some observations lack quality_score values.",
                "severity": "info",
            }
        )
    if len(all_rows) < MIN_TRAIN_POINTS + MIN_TARGET_PERIODS:
        warnings.append(
            {
                "code": "sparse_observations",
                "message": "The selected series has sparse observations for challenge construction.",
                "severity": "warning",
            }
        )
    if prospective:
        warnings.append(
            {
                "code": "prospective_targets",
                "message": "Future target dates are generated from the cutoff and frequency; observed truth is not created.",
                "severity": "info",
            }
        )
    return warnings


def _challenge_response_from_row(row: models.ForecastChallengeSnapshot) -> ForecastChallengeSnapshotResponse:
    return ForecastChallengeSnapshotResponse(
        id=row.id,
        mode=ForecastChallengeMode(row.mode),
        country_iso3=row.country_iso3,
        source_id=row.source_id,
        signal_category=row.signal_category,
        metric=row.metric,
        unit=row.unit,
        frequency=row.frequency,
        horizon_periods=row.horizon_periods,
        split_strategy=row.split_strategy,
        cutoff_at=row.cutoff_at,
        train_start=row.train_start,
        train_end=row.train_end,
        target_start=row.target_start,
        target_end=row.target_end,
        target_dates=[coerce_date(value) for value in row.target_dates_json or [] if coerce_date(value)],
        observation_ids=row.observation_ids_json or [],
        train_observation_ids=row.train_observation_ids_json or [],
        holdout_observation_ids=row.holdout_observation_ids_json or [],
        n_train=len(row.train_rows_json or []),
        n_targets=len(row.target_dates_json or []),
        dataset_hash=row.dataset_hash,
        status=ForecastChallengeStatus(row.status),
        warnings=row.quality_warnings_json or [],
        limitations=row.limitations_json or [],
        provenance=row.provenance_json or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _advance_date(value: date, frequency: str) -> date:
    if frequency == "daily":
        return value + timedelta(days=1)
    if frequency == "weekly":
        return value + timedelta(days=7)
    return _add_month(value)


def _add_month(value: date) -> date:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    days_by_month = [31, 29 if _is_leap_year(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = min(value.day, days_by_month[month - 1])
    return date(year, month, day)


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _is_next_month(left: date, right: date) -> bool:
    return _add_month(left) == right


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


def _mode_value(value: ForecastChallengeMode | str) -> str:
    return value.value if isinstance(value, ForecastChallengeMode) else str(value)


def _status_value(value: ForecastChallengeStatus | str) -> str:
    return value.value if isinstance(value, ForecastChallengeStatus) else str(value)
