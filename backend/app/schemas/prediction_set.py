from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from app.schemas.common import APIModel, JsonList


class PredictionPointResponse(APIModel):
    id: int | None = None
    prediction_set_id: int | None = None
    target_date: date
    predicted_value: float
    lower: float | None = None
    upper: float | None = None
    unit: str | None = None
    generated_at: datetime | None = None
    provenance_url: str | None = None
    created_at: datetime | None = None


class PredictionSetResponse(APIModel):
    id: int
    challenge_id: int
    submitter_id: int | None = None
    model_id: str
    model_name: str
    prediction_source: str
    submission_track: str
    review_status: str
    validation_status: str
    scoring_status: str
    country_iso3: str
    source_id: str
    signal_category: str | None = None
    metric: str
    unit: str | None = None
    frequency: str | None = None
    horizon_periods: int | None = None
    submitter_display_name: str | None = None
    submitter_name: str | None = None
    submitter_email: str | None = None
    organization: str | None = None
    verification_status: str | None = None
    visibility: str = "public"
    method_summary: str | None = None
    model_url: str | None = None
    code_url: str | None = None
    provenance_url: str | None = None
    disclosure_notes: str | None = None
    limitations: JsonList = []
    warnings: JsonList = []
    created_at: datetime
    updated_at: datetime | None = None
    points: list[PredictionPointResponse] = []


class BuiltInPredictionRunRequest(APIModel):
    model_ids: list[str] | None = None
    overwrite_existing: bool = False


class BuiltInPredictionRunResult(APIModel):
    model_id: str
    status: str
    prediction_set_id: int | None = None
    warnings: JsonList = []
    limitations: JsonList = []


class BuiltInPredictionRunResponse(APIModel):
    challenge_id: int
    prediction_sets: list[PredictionSetResponse] = []
    results: list[BuiltInPredictionRunResult] = []


class PredictionSetListResponse(APIModel):
    prediction_sets: list[PredictionSetResponse] = []


class ChallengePredictionUploadResult(APIModel):
    prediction_set_id: int | None = None
    inserted_count: int = 0
    rejected_count: int = 0
    validation_status: str
    scoring_status: str
    matched_challenge_id: int | None = None
    warnings: JsonList = []
    errors: JsonList = []


class ForecastChallengeScoreRequest(APIModel):
    ranking_metric: Literal["smape", "rmse", "mae"] = "smape"


class ForecastScoreResponse(APIModel):
    id: int | None = None
    challenge_id: int
    prediction_set_id: int
    status: str
    mae: float | None = None
    rmse: float | None = None
    smape: float | None = None
    n_scored: int
    n_expected: int
    rank_smape: int | None = None
    rank_rmse: int | None = None
    rank_mae: int | None = None
    warnings: JsonList = []
    limitations: JsonList = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ForecastChallengeScoreResponse(APIModel):
    challenge_id: int
    ranking_metric: str
    status: str
    scores: list[ForecastScoreResponse] = []
    warnings: JsonList = []
    limitations: JsonList = []


class ForecastLeaderboardEntry(APIModel):
    rank: int | None = None
    prediction_set_id: int
    model_id: str
    model_name: str
    prediction_source: str
    submission_track: str
    review_status: str
    submitter_display_name: str | None = None
    organization: str | None = None
    method_summary: str | None = None
    model_url: str | None = None
    code_url: str | None = None
    provenance_url: str | None = None
    visibility: str = "public"
    status: str
    mae: float | None = None
    rmse: float | None = None
    smape: float | None = None
    n_scored: int
    n_expected: int
    warnings: JsonList = []
    limitations: JsonList = []


class ForecastLeaderboardResponse(APIModel):
    challenge_id: int
    ranking_metric: str
    leaderboard: list[ForecastLeaderboardEntry] = []
    warnings: JsonList = []
    limitations: JsonList = []


class ForecastComparisonPrediction(APIModel):
    prediction_set_id: int
    model_id: str
    model_name: str
    prediction_source: str
    submission_track: str
    review_status: str | None = None
    validation_status: str
    scoring_status: str
    predicted_value: float | None = None
    lower: float | None = None
    upper: float | None = None
    unit: str | None = None
    absolute_error: float | None = None
    percentage_error: float | None = None
    warnings: JsonList = []


class ForecastComparisonPointResponse(APIModel):
    target_date: date
    observed_value: float | None = None
    unit: str | None = None
    predictions: list[ForecastComparisonPrediction] = []


class SubmitterResponse(APIModel):
    id: int
    display_name: str
    organization: str | None = None
    affiliation_type: str | None = None
    verification_status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class ReviewDecisionRequest(APIModel):
    review_status: Literal["unreviewed", "approved", "rejected", "needs_changes"]
    reviewer_name: str | None = None
    review_notes: str | None = None


class ReviewDecisionResponse(APIModel):
    id: int
    prediction_set_id: int
    review_status: str
    reviewer_name: str | None = None
    review_notes: str | None = None
    created_at: datetime
