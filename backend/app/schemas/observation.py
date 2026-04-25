from datetime import datetime

from app.schemas.common import APIModel, JsonList


class ObservationRead(APIModel):
    id: int
    source_id: str
    country_iso3: str
    admin1: str | None = None
    admin2: str | None = None
    location_id: int | None = None
    observed_at: datetime
    reported_at: datetime | None = None
    signal_category: str
    metric: str
    value: float
    unit: str | None = None
    normalized_value: float | None = None
    pathogen: str | None = None
    sample_type: str | None = None
    uncertainty_lower: float | None = None
    uncertainty_upper: float | None = None
    reporting_lag_days: float | None = None
    quality_score: float | None = None
    provenance_url: str | None = None
    raw_payload_ref: str | None = None


class TimeseriesUploadResult(APIModel):
    inserted_count: int
    rejected_count: int
    dry_run: bool = False
    observations: list[ObservationRead] = []
    errors: JsonList = []
    warnings: JsonList = []


class TimeSeriesAvailabilityOption(APIModel):
    source_id: str
    source_name: str
    signal_category: str
    metric: str
    unit: str | None = None
    record_count: int
    start_date: datetime
    end_date: datetime
    latest_observed_at: datetime
    latest_value: float | None = None
    quality_score: float | None = None
    provenance_url: str | None = None
    limitations: JsonList = []
    warnings: JsonList = []


class TimeSeriesAvailabilityResponse(APIModel):
    country_iso3: str
    generated_at: datetime
    options: list[TimeSeriesAvailabilityOption] = []
    warnings: JsonList = []
    limitations: JsonList = []
