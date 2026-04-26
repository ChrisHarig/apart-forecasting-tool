from __future__ import annotations

from datetime import UTC, date, datetime
from math import sqrt
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import models
from app.schemas.forecast_challenge import ForecastChallengeMode, ForecastChallengeStatus
from app.schemas.prediction_set import (
    ForecastChallengeScoreResponse,
    ForecastComparisonPointResponse,
    ForecastComparisonPrediction,
    ForecastLeaderboardEntry,
    ForecastLeaderboardResponse,
    ForecastScoreResponse,
)
from app.services.forecast_benchmark import BENCHMARK_LIMITATIONS
from app.services.normalization import coerce_date
from app.services.submissions import filter_leaderboard_by_track_and_review, redact_private_submitter_fields


SCORING_WARNING = {
    "code": "challenge_scoring_only",
    "message": (
        "Forecast challenge scores are historical or pending metric comparisons only, not public-health alerts, "
        "risk scores, Rt/R0 estimates, validated epidemiological predictions, or operational guidance."
    ),
    "severity": "warning",
}

SCORING_LIMITATIONS = [
    "Scores compare aggregate prediction CSVs or built-in baselines against challenge target observations only.",
    "Historical holdout performance is not proof of future public-health validity.",
    "Prospective challenge predictions remain pending until matching aggregate truth observations arrive.",
]

SUPPORTED_RANKING_METRICS = {"smape", "rmse", "mae"}


def score_prediction_set_against_challenge(
    prediction_set: models.PredictionSet,
    challenge: models.ForecastChallengeSnapshot,
    db: Session,
) -> ForecastScoreResponse:
    target_dates = _target_dates(challenge)
    truth = _truth_by_date(db, challenge)
    warnings = [SCORING_WARNING, *(prediction_set.warnings_json or [])]
    limitations = [*SCORING_LIMITATIONS, *(prediction_set.limitations_json or [])]

    if prediction_set.validation_status == "overlay_only":
        row = _upsert_score(
            db,
            prediction_set,
            status="overlay_only",
            n_scored=0,
            n_expected=len(target_dates),
            warnings=[
                *warnings,
                {
                    "code": "overlay_only",
                    "message": "Prediction set is overlay-only and is not benchmark scored because its metric or unit does not match the challenge.",
                    "severity": "warning",
                },
            ],
            limitations=limitations,
        )
        prediction_set.scoring_status = "unscored"
        return _score_response(row)

    if prediction_set.validation_status == "invalid":
        row = _upsert_score(
            db,
            prediction_set,
            status="invalid",
            n_scored=0,
            n_expected=len(target_dates),
            warnings=warnings,
            limitations=limitations,
        )
        prediction_set.scoring_status = "invalid"
        return _score_response(row)

    predictions = _prediction_by_date(prediction_set)
    pairs = [
        (truth[day], predictions[day].predicted_value)
        for day in target_dates
        if day in truth and day in predictions
    ]

    if not pairs:
        row = _upsert_score(
            db,
            prediction_set,
            status="pending_truth",
            n_scored=0,
            n_expected=len(target_dates),
            warnings=[
                *warnings,
                {
                    "code": "pending_truth",
                    "message": "No observed aggregate truth values are available for the challenge target dates yet.",
                    "severity": "info",
                },
            ],
            limitations=limitations,
        )
        prediction_set.scoring_status = "pending_truth"
        return _score_response(row)

    status = "scored" if len(pairs) == len(target_dates) else "partially_scored"
    mae = compute_mae(pairs)
    rmse = compute_rmse(pairs)
    smape = compute_smape(pairs)
    row = _upsert_score(
        db,
        prediction_set,
        status=status,
        mae=mae,
        rmse=rmse,
        smape=smape,
        n_scored=len(pairs),
        n_expected=len(target_dates),
        warnings=warnings,
        limitations=limitations,
    )
    prediction_set.scoring_status = status
    return _score_response(row)


def score_all_prediction_sets_for_challenge(
    challenge_id: int,
    ranking_metric: str,
    db: Session,
) -> ForecastChallengeScoreResponse:
    metric = _validate_ranking_metric(ranking_metric)
    challenge = _get_challenge_row(db, challenge_id)
    prediction_sets = _prediction_sets_for_challenge(db, challenge_id)
    scores = [score_prediction_set_against_challenge(prediction_set, challenge, db) for prediction_set in prediction_sets]
    _rank_scores(db, challenge_id)
    status = update_challenge_scoring_status(challenge_id, db)
    db.commit()
    refreshed = _scores_for_challenge(db, challenge_id)
    return ForecastChallengeScoreResponse(
        challenge_id=challenge_id,
        ranking_metric=metric,
        status=status,
        scores=[_score_response(row) for row in refreshed],
        warnings=[SCORING_WARNING],
        limitations=SCORING_LIMITATIONS,
    )


def build_leaderboard(
    challenge_id: int,
    ranking_metric: str,
    db: Session,
    *,
    submission_track: str = "all",
    review_status: str = "all",
    include_unreviewed: bool = True,
) -> ForecastLeaderboardResponse:
    metric = _validate_ranking_metric(ranking_metric)
    _get_challenge_row(db, challenge_id)
    scores = _scores_for_challenge(db, challenge_id)
    score_by_prediction_set = {score.prediction_set_id: score for score in scores}
    prediction_sets = filter_leaderboard_by_track_and_review(
        _prediction_sets_for_challenge(db, challenge_id),
        submission_track=submission_track,
        review_status=review_status,
        include_unreviewed=include_unreviewed,
    )
    entries: list[ForecastLeaderboardEntry] = []
    for prediction_set in prediction_sets:
        submitter_fields = redact_private_submitter_fields(prediction_set)
        score = score_by_prediction_set.get(prediction_set.id)
        if score is None:
            entries.append(
                ForecastLeaderboardEntry(
                    prediction_set_id=prediction_set.id,
                    model_id=prediction_set.model_id,
                    model_name=prediction_set.model_name,
                    prediction_source=prediction_set.prediction_source,
                    submission_track=prediction_set.submission_track,
                    review_status=prediction_set.review_status,
                    submitter_display_name=submitter_fields["submitter_display_name"],
                    organization=submitter_fields["organization"],
                    method_summary=prediction_set.method_summary,
                    model_url=prediction_set.model_url,
                    code_url=prediction_set.code_url,
                    provenance_url=prediction_set.provenance_url,
                    visibility=prediction_set.visibility,
                    status=prediction_set.scoring_status,
                    n_scored=0,
                    n_expected=len(_target_dates(prediction_set.challenge)),
                    warnings=prediction_set.warnings_json or [],
                    limitations=prediction_set.limitations_json or [],
                )
            )
            continue
        entries.append(
            ForecastLeaderboardEntry(
                rank=getattr(score, f"rank_{metric}")
                if prediction_set.review_status not in {"rejected", "needs_changes"}
                else None,
                prediction_set_id=prediction_set.id,
                model_id=prediction_set.model_id,
                model_name=prediction_set.model_name,
                prediction_source=prediction_set.prediction_source,
                submission_track=prediction_set.submission_track,
                review_status=prediction_set.review_status,
                submitter_display_name=submitter_fields["submitter_display_name"],
                organization=submitter_fields["organization"],
                method_summary=prediction_set.method_summary,
                model_url=prediction_set.model_url,
                code_url=prediction_set.code_url,
                provenance_url=prediction_set.provenance_url,
                visibility=prediction_set.visibility,
                status=score.status,
                mae=score.mae,
                rmse=score.rmse,
                smape=score.smape,
                n_scored=score.n_scored,
                n_expected=score.n_expected,
                warnings=score.warnings_json or [],
                limitations=score.limitations_json or [],
            )
        )
    entries.sort(key=lambda item: (item.rank is None, item.rank or 10**9, item.model_name, item.prediction_set_id))
    return ForecastLeaderboardResponse(
        challenge_id=challenge_id,
        ranking_metric=metric,
        leaderboard=entries,
        warnings=[SCORING_WARNING],
        limitations=SCORING_LIMITATIONS,
    )


def build_comparison_points(
    challenge_id: int,
    db: Session,
) -> list[ForecastComparisonPointResponse]:
    challenge = _get_challenge_row(db, challenge_id)
    target_dates = _target_dates(challenge)
    truth = _truth_by_date(db, challenge)
    prediction_sets = _prediction_sets_for_challenge(db, challenge_id)
    output: list[ForecastComparisonPointResponse] = []
    for day in target_dates:
        predictions: list[ForecastComparisonPrediction] = []
        observed = truth.get(day)
        for prediction_set in prediction_sets:
            points = _prediction_by_date(prediction_set)
            point = points.get(day)
            if point is None:
                continue
            can_score = prediction_set.validation_status == "valid_for_snapshot" and observed is not None
            absolute_error = abs(point.predicted_value - observed) if can_score else None
            percentage_error = _percentage_error(observed, point.predicted_value) if can_score else None
            predictions.append(
                ForecastComparisonPrediction(
                    prediction_set_id=prediction_set.id,
                    model_id=prediction_set.model_id,
                    model_name=prediction_set.model_name,
                    prediction_source=prediction_set.prediction_source,
                    submission_track=prediction_set.submission_track,
                    review_status=prediction_set.review_status,
                    validation_status=prediction_set.validation_status,
                    scoring_status=prediction_set.scoring_status,
                    predicted_value=point.predicted_value,
                    lower=point.lower,
                    upper=point.upper,
                    unit=point.unit,
                    absolute_error=absolute_error,
                    percentage_error=percentage_error,
                    warnings=prediction_set.warnings_json or [],
                )
            )
        output.append(
            ForecastComparisonPointResponse(
                target_date=day,
                observed_value=observed,
                unit=challenge.unit,
                predictions=predictions,
            )
        )
    return output


def update_challenge_scoring_status(challenge_id: int, db: Session) -> str:
    challenge = _get_challenge_row(db, challenge_id)
    scores = _scores_for_challenge(db, challenge_id)
    scoreable = [score for score in scores if score.status not in {"overlay_only", "invalid", "failed"}]
    if not scoreable:
        status = (
            ForecastChallengeStatus.PENDING_TRUTH.value
            if challenge.mode == ForecastChallengeMode.PROSPECTIVE_CHALLENGE.value
            else challenge.status
        )
    elif all(score.status == "scored" for score in scoreable):
        status = ForecastChallengeStatus.SCORED.value
    elif any(score.status == "partially_scored" for score in scoreable):
        status = ForecastChallengeStatus.PARTIALLY_SCORED.value
    elif any(score.status == "pending_truth" for score in scoreable):
        status = ForecastChallengeStatus.PENDING_TRUTH.value
    else:
        status = challenge.status
    challenge.status = status
    challenge.updated_at = datetime.now(UTC)
    db.flush()
    return status


def compute_mae(points: list[tuple[float, float]]) -> float | None:
    if not points:
        return None
    return float(mean(abs(observed - predicted) for observed, predicted in points))


def compute_rmse(points: list[tuple[float, float]]) -> float | None:
    if not points:
        return None
    return float(sqrt(mean((observed - predicted) ** 2 for observed, predicted in points)))


def compute_smape(points: list[tuple[float, float]]) -> float | None:
    if not points:
        return None
    values = []
    for observed, predicted in points:
        denominator = (abs(observed) + abs(predicted)) / 2
        values.append(0.0 if denominator == 0 else abs(predicted - observed) / denominator * 100)
    return float(mean(values))


def _percentage_error(observed: float, predicted: float) -> float | None:
    if observed == 0:
        return 0.0 if predicted == 0 else None
    return float(abs(predicted - observed) / abs(observed) * 100)


def _upsert_score(
    db: Session,
    prediction_set: models.PredictionSet,
    *,
    status: str,
    n_scored: int,
    n_expected: int,
    warnings: list,
    limitations: list,
    mae: float | None = None,
    rmse: float | None = None,
    smape: float | None = None,
) -> models.ForecastScore:
    row = (
        db.execute(
            select(models.ForecastScore).where(
                models.ForecastScore.challenge_id == prediction_set.challenge_id,
                models.ForecastScore.prediction_set_id == prediction_set.id,
            )
        )
        .scalars()
        .one_or_none()
    )
    if row is None:
        row = models.ForecastScore(
            challenge_id=prediction_set.challenge_id,
            prediction_set_id=prediction_set.id,
            created_at=datetime.now(UTC),
        )
        db.add(row)
    row.status = status
    row.mae = mae
    row.rmse = rmse
    row.smape = smape
    row.n_scored = n_scored
    row.n_expected = n_expected
    row.rank_smape = None
    row.rank_rmse = None
    row.rank_mae = None
    row.warnings_json = warnings
    row.limitations_json = limitations
    row.updated_at = datetime.now(UTC)
    db.flush()
    return row


def _rank_scores(db: Session, challenge_id: int) -> None:
    rows = _scores_for_challenge(db, challenge_id)
    for row in rows:
        row.rank_smape = None
        row.rank_rmse = None
        row.rank_mae = None
    for metric in SUPPORTED_RANKING_METRICS:
        eligible = [
            row
            for row in rows
            if row.status in {"scored", "partially_scored"} and row.n_scored > 0 and getattr(row, metric) is not None
            and row.prediction_set.review_status not in {"rejected", "needs_changes"}
        ]
        eligible.sort(key=lambda row: (getattr(row, metric), row.prediction_set_id))
        for rank, row in enumerate(eligible, start=1):
            setattr(row, f"rank_{metric}", rank)
    db.flush()


def _score_response(row: models.ForecastScore) -> ForecastScoreResponse:
    return ForecastScoreResponse(
        id=row.id,
        challenge_id=row.challenge_id,
        prediction_set_id=row.prediction_set_id,
        status=row.status,
        mae=row.mae,
        rmse=row.rmse,
        smape=row.smape,
        n_scored=row.n_scored,
        n_expected=row.n_expected,
        rank_smape=row.rank_smape,
        rank_rmse=row.rank_rmse,
        rank_mae=row.rank_mae,
        warnings=row.warnings_json or [],
        limitations=row.limitations_json or [],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _get_challenge_row(db: Session, challenge_id: int) -> models.ForecastChallengeSnapshot:
    row = db.get(models.ForecastChallengeSnapshot, challenge_id)
    if row is None:
        raise ValueError("Forecast challenge snapshot not found")
    return row


def _prediction_sets_for_challenge(db: Session, challenge_id: int) -> list[models.PredictionSet]:
    return (
        db.execute(
            select(models.PredictionSet)
            .where(models.PredictionSet.challenge_id == challenge_id)
            .options(
                selectinload(models.PredictionSet.points),
                selectinload(models.PredictionSet.challenge),
                selectinload(models.PredictionSet.submitter),
            )
            .order_by(models.PredictionSet.created_at.asc(), models.PredictionSet.id.asc())
        )
        .scalars()
        .all()
    )


def _scores_for_challenge(db: Session, challenge_id: int) -> list[models.ForecastScore]:
    return (
        db.execute(
            select(models.ForecastScore)
            .where(models.ForecastScore.challenge_id == challenge_id)
            .order_by(models.ForecastScore.prediction_set_id.asc())
        )
        .scalars()
        .all()
    )


def _target_dates(challenge: models.ForecastChallengeSnapshot) -> list[date]:
    return [day for day in (coerce_date(value) for value in challenge.target_dates_json or []) if day is not None]


def _prediction_by_date(prediction_set: models.PredictionSet) -> dict[date, models.PredictionPoint]:
    return {point.target_date: point for point in sorted(prediction_set.points, key=lambda item: item.target_date)}


def _truth_by_date(db: Session, challenge: models.ForecastChallengeSnapshot) -> dict[date, float]:
    if (
        challenge.mode == ForecastChallengeMode.RETROSPECTIVE_HOLDOUT.value
        and challenge.holdout_rows_json
    ):
        grouped: dict[date, list[float]] = {}
        for row in challenge.holdout_rows_json:
            day = coerce_date(row.get("date"))
            if day is None:
                continue
            grouped.setdefault(day, []).append(float(row["value"]))
        return {day: float(mean(values)) for day, values in grouped.items()}

    target_dates = set(_target_dates(challenge))
    if not target_dates:
        return {}
    query = select(models.Observation).where(
        models.Observation.country_iso3 == challenge.country_iso3,
        models.Observation.source_id == challenge.source_id,
        models.Observation.metric == challenge.metric,
    )
    if challenge.unit is not None:
        query = query.where(models.Observation.unit == challenge.unit)
    if challenge.signal_category is not None:
        query = query.where(models.Observation.signal_category == challenge.signal_category)

    grouped: dict[date, list[float]] = {}
    for row in db.execute(query).scalars().all():
        day = row.observed_at.date()
        if day not in target_dates:
            continue
        value = row.normalized_value if row.normalized_value is not None else row.value
        grouped.setdefault(day, []).append(float(value))
    return {day: float(mean(values)) for day, values in grouped.items()}


def _validate_ranking_metric(value: str) -> str:
    metric = (value or "smape").strip().lower()
    if metric not in SUPPORTED_RANKING_METRICS:
        raise ValueError("ranking_metric must be smape, rmse, or mae")
    return metric
