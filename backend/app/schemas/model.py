from datetime import date, datetime
from typing import Any

from app.schemas.common import APIModel, JsonDict, JsonList


class ModelRunRequest(APIModel):
    country_iso3: str
    horizon_days: int = 14
    target_signal: str = "public_health_signal"
    selected_model_id: str | None = None


class ModelReadiness(APIModel):
    country_iso3: str
    selected_model_id: str
    eligible_models: JsonList
    output_status: str
    features: JsonList
    missing_features: JsonList
    sources_used: JsonList
    data_quality_score: float
    warnings: JsonList
    limitations: JsonList
    explanation: str
    generated_at: datetime


class ModelOutputPointRead(APIModel):
    id: int | None = None
    model_run_id: int | None = None
    date: date
    metric: str
    value: float
    lower: float | None = None
    upper: float | None = None
    unit: str | None = None


class ModelRunRead(APIModel):
    id: int
    country_iso3: str
    requested_at: datetime
    horizon_days: int
    target_signal: str
    selected_model_id: str
    model_eligibility: JsonDict
    input_feature_snapshot: JsonDict
    data_quality_snapshot: JsonDict
    output_status: str
    explanation: str
    warnings: list[Any] = []
    output_points: list[ModelOutputPointRead] = []

