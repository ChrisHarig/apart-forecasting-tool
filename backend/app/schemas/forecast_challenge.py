from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import Field

from app.schemas.common import APIModel, JsonList


class ForecastChallengeMode(StrEnum):
    RETROSPECTIVE_HOLDOUT = "retrospective_holdout"
    PROSPECTIVE_CHALLENGE = "prospective_challenge"


class ForecastChallengeStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    SCORING = "scoring"
    PENDING_TRUTH = "pending_truth"
    PARTIALLY_SCORED = "partially_scored"
    SCORED = "scored"
    INSUFFICIENT_DATA = "insufficient_data"


class ForecastChallengeBaseRequest(APIModel):
    mode: ForecastChallengeMode = ForecastChallengeMode.RETROSPECTIVE_HOLDOUT
    country_iso3: str
    source_id: str
    metric: str
    signal_category: str | None = None
    unit: str | None = None
    frequency: str = "weekly"
    horizon_periods: int = 4
    split_strategy: str = "last_n_periods"
    cutoff_at: datetime | None = None
    start_date: date | None = None
    end_date: date | None = None


class ForecastChallengePreviewRequest(ForecastChallengeBaseRequest):
    pass


class ForecastChallengeCreateRequest(ForecastChallengeBaseRequest):
    pass


class PredictionTemplateRow(APIModel):
    model_id: str | None = None
    model_name: str | None = None
    target_date: date
    predicted_value: float | None = None
    lower: float | None = None
    upper: float | None = None
    unit: str | None = None
    country_iso3: str
    source_id: str
    metric: str
    signal_category: str | None = None
    generated_at: datetime | None = None
    provenance_url: str | None = None


class ForecastChallengeSnapshotResponse(APIModel):
    id: int | None = None
    mode: ForecastChallengeMode
    country_iso3: str
    source_id: str
    signal_category: str | None = None
    metric: str
    unit: str | None = None
    frequency: str
    horizon_periods: int
    split_strategy: str
    cutoff_at: datetime | None = None
    train_start: date | None = None
    train_end: date | None = None
    target_start: date | None = None
    target_end: date | None = None
    target_dates: list[date] = []
    observation_ids: JsonList = []
    train_observation_ids: JsonList = []
    holdout_observation_ids: JsonList = []
    n_train: int = 0
    n_targets: int = 0
    dataset_hash: str
    status: ForecastChallengeStatus
    warnings: JsonList = []
    limitations: JsonList = []
    provenance: dict = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ForecastChallengePreviewResponse(APIModel):
    challenge_snapshot: ForecastChallengeSnapshotResponse
    train_preview: JsonList = []
    prediction_template: list[PredictionTemplateRow] = []


class ForecastChallengeListItem(ForecastChallengeSnapshotResponse):
    pass
