from datetime import date, datetime

from app.schemas.common import APIModel, JsonList


class ForecastModelRead(APIModel):
    id: str
    name: str
    model_id: str | None = None
    display_name: str | None = None
    model_kind: str
    model_family: str | None = None
    implementation_source: str | None = None
    benchmark_only: bool = True
    builtin: bool = False
    accepts_uploaded_code: bool = False
    accepts_prediction_csv: bool = False
    required_observation_count: int | None = None
    supported_frequencies: JsonList = []
    required_frequency_notes: str | None = None
    supports_prediction_intervals: str | None = None
    default_parameters: dict = {}
    description: str | None = None
    owner: str | None = None
    status: str
    safety_notes: JsonList = []
    citation_or_package_notes: str | None = None
    dependency_status: str = "available"
    registry_version: str | None = None
    provenance_url: str | None = None
    limitations: JsonList = []
    warnings: JsonList = []


class UploadedForecastPredictionRead(APIModel):
    id: int | None = None
    model_id: str
    country_iso3: str
    source_id: str
    metric: str
    unit: str | None = None
    target_date: date
    predicted_value: float
    lower: float | None = None
    upper: float | None = None
    generated_at: datetime | None = None
    provenance_url: str | None = None
    limitations: JsonList = []


class ForecastPredictionUploadResult(APIModel):
    inserted_count: int
    rejected_count: int
    models: list[ForecastModelRead] = []
    predictions: list[UploadedForecastPredictionRead] = []
    errors: JsonList = []
    warnings: JsonList = []


class ForecastBenchmarkRequest(APIModel):
    country_iso3: str
    source_id: str
    metric: str
    unit: str | None = None
    frequency: str = "weekly"
    horizon_periods: int = 4
    model_ids: list[str] | None = None
    train_start: date | None = None
    train_end: date | None = None


class ForecastBenchmarkPointRead(APIModel):
    id: int | None = None
    benchmark_result_id: int | None = None
    date: date
    observed_value: float
    predicted_value: float
    lower: float | None = None
    upper: float | None = None
    unit: str | None = None


class ForecastBenchmarkResultRead(APIModel):
    id: int | None = None
    benchmark_run_id: int | None = None
    model_id: str
    model_name: str
    display_name: str | None = None
    model_kind: str
    status: str
    mae: float | None = None
    rmse: float | None = None
    smape: float | None = None
    n_train: int
    n_test: int
    train_start: date | None = None
    train_end: date | None = None
    test_start: date | None = None
    test_end: date | None = None
    provenance_url: str | None = None
    warnings: JsonList = []
    limitations: JsonList = []
    data_quality_notes: JsonList = []
    points: list[ForecastBenchmarkPointRead] = []


class ForecastBenchmarkRead(APIModel):
    id: int | None = None
    country_iso3: str
    source_id: str
    metric: str
    unit: str | None = None
    frequency: str
    horizon_periods: int
    train_start: date | None = None
    train_end: date | None = None
    requested_model_ids: JsonList = []
    output_status: str
    explanation: str
    warnings: JsonList = []
    limitations: JsonList = []
    comparison: JsonList = []
    data_quality_notes: JsonList = []
    created_at: datetime
    results: list[ForecastBenchmarkResultRead] = []
