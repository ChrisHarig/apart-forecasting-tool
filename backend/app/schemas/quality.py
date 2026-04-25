from datetime import date, datetime

from app.schemas.common import APIModel, JsonList


class DataQualityReportRead(APIModel):
    id: int | None = None
    country_iso3: str
    source_id: str | None = None
    signal_category: str
    completeness_score: float
    recency_score: float
    reporting_lag_score: float
    spatial_coverage_score: float
    temporal_coverage_score: float
    uncertainty_score: float
    overall_readiness_score: float
    generated_at: datetime
    notes: str | None = None


class FeatureAvailabilityRead(APIModel):
    id: int | None = None
    country_iso3: str
    as_of_date: date
    feature_name: str
    signal_category: str
    status: str
    source_ids: JsonList = []
    latest_observation_at: datetime | None = None
    coverage_window_days: int | None = None
    quality_score: float | None = None
    notes: str | None = None

