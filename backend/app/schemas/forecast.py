from datetime import date, datetime

from pydantic import Field

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
    experimental: bool = False
    enabled_by_default: bool = True
    feature_flag_enabled: bool = True
    accepts_uploaded_code: bool = False
    accepts_prediction_csv: bool = False
    required_observation_count: int | None = None
    supported_frequencies: JsonList = []
    required_frequency_notes: str | None = None
    supports_prediction_intervals: str | None = None
    default_parameters: dict = Field(default_factory=dict)
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
    prediction_set_id: int | None = None
    inserted_count: int
    rejected_count: int
    validation_status: str | None = None
    matched_dataset_snapshot_id: int | None = None
    models: list[ForecastModelRead] = []
    predictions: list[UploadedForecastPredictionRead] = []
    errors: JsonList = []
    warnings: JsonList = []


class ForecastBenchmarkDatasetRequest(APIModel):
    country_iso3: str
    source_id: str
    metric: str
    signal_category: str | None = None
    unit: str | None = None
    frequency: str = "weekly"
    horizon_periods: int = 4
    start_date: date | None = None
    end_date: date | None = None
    split_strategy: str = "last_n_periods"


class ForecastPredictionTemplateRow(APIModel):
    target_date: date
    model_id: str | None = None
    model_name: str | None = None
    country_iso3: str
    source_id: str
    metric: str
    predicted_value: float | None = None
    lower: float | None = None
    upper: float | None = None
    unit: str | None = None
    generated_at: datetime | None = None
    provenance_url: str | None = None
    limitations: str | None = None


class ForecastBenchmarkDatasetRead(APIModel):
    id: int | None = None
    country_iso3: str
    source_id: str
    signal_category: str | None = None
    metric: str
    unit: str | None = None
    frequency: str
    horizon_periods: int
    split_strategy: str
    train_start: date | None = None
    train_end: date | None = None
    test_start: date | None = None
    test_end: date | None = None
    target_dates: list[date] = []
    observation_ids: JsonList = []
    train_observation_ids: JsonList = []
    test_observation_ids: JsonList = []
    n_train: int = 0
    n_test: int = 0
    dataset_hash: str
    status: str = "ready"
    warnings: JsonList = []
    limitations: JsonList = []
    provenance: dict = Field(default_factory=dict)
    created_at: datetime | None = None


class ForecastBenchmarkDatasetPreview(APIModel):
    dataset_snapshot: ForecastBenchmarkDatasetRead
    train_preview: JsonList = []
    target_template: list[ForecastPredictionTemplateRow] = []


class UploadedPredictionPointRead(APIModel):
    id: int | None = None
    prediction_set_id: int | None = None
    target_date: date
    predicted_value: float
    lower: float | None = None
    upper: float | None = None
    unit: str | None = None
    generated_at: datetime | None = None
    provenance_url: str | None = None


class UploadedPredictionSetRead(APIModel):
    id: int
    benchmark_dataset_snapshot_id: int | None = None
    submitter_id: int | None = None
    model_id: str
    model_name: str
    country_iso3: str
    source_id: str
    metric: str
    unit: str | None = None
    frequency: str | None = None
    horizon_periods: int | None = None
    target_start: date | None = None
    target_end: date | None = None
    provenance_url: str | None = None
    user_notes: str | None = None
    validation_status: str
    submitter_name: str | None = None
    organization: str | None = None
    submission_track: str = "public"
    review_status: str = "unreviewed"
    visibility: str = "public"
    method_summary: str | None = None
    model_url: str | None = None
    code_url: str | None = None
    disclosure_notes: str | None = None
    row_count: int = 0
    matched_dataset_snapshot_id: int | None = None
    warnings: JsonList = []
    limitations: JsonList = []
    errors: JsonList = []
    created_at: datetime
    points: list[UploadedPredictionPointRead] = []


class ForecastBenchmarkRequest(APIModel):
    dataset_snapshot_id: int | None = None
    country_iso3: str | None = None
    source_id: str | None = None
    metric: str | None = None
    signal_category: str | None = None
    unit: str | None = None
    frequency: str = "weekly"
    horizon_periods: int = 4
    model_ids: list[str] | None = None
    uploaded_prediction_set_ids: list[int] | None = None
    start_date: date | None = None
    end_date: date | None = None
    split_strategy: str = "last_n_periods"
    train_start: date | None = None
    train_end: date | None = None
    save: bool = False


class ForecastBenchmarkPointRead(APIModel):
    id: int | None = None
    benchmark_result_id: int | None = None
    date: date
    observed_value: float
    predicted_value: float | None
    lower: float | None = None
    upper: float | None = None
    absolute_error: float | None = None
    percentage_error: float | None = None
    unit: str | None = None


class ForecastBenchmarkResultRead(APIModel):
    id: int | None = None
    benchmark_run_id: int | None = None
    dataset_snapshot_id: int | None = None
    model_id: str
    model_name: str
    display_name: str | None = None
    model_kind: str
    model_family: str | None = None
    result_type: str = "builtin_model"
    status: str
    mae: float | None = None
    rmse: float | None = None
    smape: float | None = None
    n_train: int | None
    n_test: int
    train_start: date | None = None
    train_end: date | None = None
    test_start: date | None = None
    test_end: date | None = None
    rank: int | None = None
    provenance_url: str | None = None
    warnings: JsonList = []
    limitations: JsonList = []
    data_quality_notes: JsonList = []
    metadata: dict = Field(default_factory=dict, validation_alias="metadata_json")
    points: list[ForecastBenchmarkPointRead] = []


class ForecastBenchmarkRead(APIModel):
    id: int | None = None
    dataset_snapshot_id: int | None = None
    country_iso3: str
    source_id: str
    metric: str
    unit: str | None = None
    frequency: str
    horizon_periods: int
    train_start: date | None = None
    train_end: date | None = None
    requested_model_ids: JsonList = []
    uploaded_prediction_set_ids: JsonList = []
    output_status: str
    explanation: str
    warnings: JsonList = []
    limitations: JsonList = []
    comparison: JsonList = []
    leaderboard: JsonList = []
    comparison_points: JsonList = []
    data_quality_notes: JsonList = []
    dataset_snapshot: ForecastBenchmarkDatasetRead | None = None
    benchmark_run: dict | None = None
    created_at: datetime
    results: list[ForecastBenchmarkResultRead] = []
