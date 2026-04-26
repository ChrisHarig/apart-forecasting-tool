from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Country(Base):
    __tablename__ = "countries"

    iso3: Mapped[str] = mapped_column(String(3), primary_key=True)
    iso2: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    iso_numeric: Mapped[str | None] = mapped_column(String(3), nullable=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    subregion: Mapped[str | None] = mapped_column(String(128), nullable=True)
    centroid: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    observations: Mapped[list["Observation"]] = relationship(back_populates="country")
    locations: Mapped[list["Location"]] = relationship(back_populates="country")


class DataSource(TimestampMixin, Base):
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(96), index=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    official_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    access_type: Mapped[str | None] = mapped_column(String(96), nullable=True)
    license: Mapped[str | None] = mapped_column(String(255), nullable=True)
    geographic_coverage: Mapped[str | None] = mapped_column(String(255), nullable=True)
    temporal_resolution: Mapped[str | None] = mapped_column(String(96), nullable=True)
    update_cadence: Mapped[str | None] = mapped_column(String(96), nullable=True)
    adapter_status: Mapped[str] = mapped_column(String(64), default="placeholder")
    reliability_tier: Mapped[str] = mapped_column(String(64), default="unknown")
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    provenance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    coverage: Mapped[list["SourceCoverage"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    observations: Mapped[list["Observation"]] = relationship(back_populates="source")


class SourceCoverage(Base):
    __tablename__ = "source_coverage"
    __table_args__ = (
        UniqueConstraint("source_id", "country_iso3", "granularity", name="uq_source_country_granularity"),
        Index("ix_source_coverage_country_status", "country_iso3", "coverage_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id"), index=True)
    country_iso3: Mapped[str] = mapped_column(ForeignKey("countries.iso3"), index=True)
    coverage_status: Mapped[str] = mapped_column(String(32), default="unknown")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    granularity: Mapped[str | None] = mapped_column(String(96), nullable=True)
    admin_levels_available: Mapped[list] = mapped_column(JSON, default=list)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped["DataSource"] = relationship(back_populates="coverage")


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        Index("ix_locations_country_type", "country_iso3", "location_type"),
        Index("ix_locations_lat_lon", "latitude", "longitude"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_iso3: Mapped[str] = mapped_column(ForeignKey("countries.iso3"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    location_type: Mapped[str] = mapped_column(String(64), index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    admin1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    admin2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    # TODO(PostGIS): replace lat/lon indexes with a geometry(Point, 4326) column and GiST index.
    country: Mapped["Country"] = relationship(back_populates="locations")
    observations: Mapped[list["Observation"]] = relationship(back_populates="location")


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        Index("ix_observations_country_metric_time", "country_iso3", "metric", "observed_at"),
        Index("ix_observations_source_time", "source_id", "observed_at"),
        Index("ix_observations_signal_category", "signal_category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id"), index=True)
    country_iso3: Mapped[str] = mapped_column(ForeignKey("countries.iso3"), index=True)
    admin1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    admin2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signal_category: Mapped[str] = mapped_column(String(96))
    metric: Mapped[str] = mapped_column(String(255), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(96), nullable=True)
    normalized_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    pathogen: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sample_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uncertainty_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    reporting_lag_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    provenance_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    raw_payload_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    source: Mapped["DataSource"] = relationship(back_populates="observations")
    country: Mapped["Country"] = relationship(back_populates="observations")
    location: Mapped["Location | None"] = relationship(back_populates="observations")


class NewsEvent(Base):
    __tablename__ = "news_events"
    __table_args__ = (
        UniqueConstraint("deduplication_key", name="uq_news_deduplication_key"),
        Index("ix_news_country_event_date", "country_iso3", "event_date"),
        Index("ix_news_signal_category", "signal_category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_iso3: Mapped[str] = mapped_column(ForeignKey("countries.iso3"), index=True)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    headline: Mapped[str] = mapped_column(String(512))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    related_pathogen: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signal_category: Mapped[str] = mapped_column(String(96), default="open_source_news")
    severity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    deduplication_key: Mapped[str] = mapped_column(String(512))


class DataQualityReport(Base):
    __tablename__ = "data_quality_reports"
    __table_args__ = (Index("ix_quality_country_signal_time", "country_iso3", "signal_category", "generated_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_iso3: Mapped[str] = mapped_column(ForeignKey("countries.iso3"), index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True, index=True)
    signal_category: Mapped[str] = mapped_column(String(96), index=True)
    completeness_score: Mapped[float] = mapped_column(Float, default=0.0)
    recency_score: Mapped[float] = mapped_column(Float, default=0.0)
    reporting_lag_score: Mapped[float] = mapped_column(Float, default=0.0)
    spatial_coverage_score: Mapped[float] = mapped_column(Float, default=0.0)
    temporal_coverage_score: Mapped[float] = mapped_column(Float, default=0.0)
    uncertainty_score: Mapped[float] = mapped_column(Float, default=0.0)
    overall_readiness_score: Mapped[float] = mapped_column(Float, default=0.0)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class FeatureAvailability(Base):
    __tablename__ = "feature_availability"
    __table_args__ = (
        UniqueConstraint("country_iso3", "as_of_date", "feature_name", name="uq_country_feature_as_of"),
        Index("ix_feature_country_status", "country_iso3", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_iso3: Mapped[str] = mapped_column(ForeignKey("countries.iso3"), index=True)
    as_of_date: Mapped[date] = mapped_column(Date, index=True)
    feature_name: Mapped[str] = mapped_column(String(255), index=True)
    signal_category: Mapped[str] = mapped_column(String(96), index=True)
    status: Mapped[str] = mapped_column(String(32), default="unknown")
    source_ids: Mapped[list] = mapped_column(JSON, default=list)
    latest_observation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    coverage_window_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ModelRun(Base):
    __tablename__ = "model_runs"
    __table_args__ = (Index("ix_model_runs_country_requested", "country_iso3", "requested_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_iso3: Mapped[str] = mapped_column(ForeignKey("countries.iso3"), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    horizon_days: Mapped[int] = mapped_column(Integer)
    target_signal: Mapped[str] = mapped_column(String(255))
    selected_model_id: Mapped[str] = mapped_column(String(128), default="insufficient_data")
    model_eligibility: Mapped[dict] = mapped_column(JSON, default=dict)
    input_feature_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    data_quality_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    output_status: Mapped[str] = mapped_column(String(64), default="insufficient_data")
    explanation: Mapped[str] = mapped_column(Text)
    warnings: Mapped[list] = mapped_column(JSON, default=list)

    output_points: Mapped[list["ModelOutputPoint"]] = relationship(back_populates="model_run", cascade="all, delete-orphan")


class ModelOutputPoint(Base):
    __tablename__ = "model_output_points"
    __table_args__ = (Index("ix_model_output_run_date_metric", "model_run_id", "date", "metric"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_run_id: Mapped[int] = mapped_column(ForeignKey("model_runs.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    metric: Mapped[str] = mapped_column(String(255))
    value: Mapped[float] = mapped_column(Float)
    lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(96), nullable=True)

    model_run: Mapped["ModelRun"] = relationship(back_populates="output_points")


class ForecastModel(TimestampMixin, Base):
    __tablename__ = "forecast_models"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    model_kind: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="uploaded_predictions")
    provenance_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)

    uploaded_prediction_points: Mapped[list["UploadedForecastPredictionPoint"]] = relationship(
        back_populates="model",
        cascade="all, delete-orphan",
    )


class UploadedForecastPredictionPoint(Base):
    __tablename__ = "uploaded_forecast_prediction_points"
    __table_args__ = (
        Index(
            "ix_uploaded_forecast_lookup",
            "country_iso3",
            "source_id",
            "metric",
            "target_date",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("forecast_models.id"), index=True)
    country_iso3: Mapped[str] = mapped_column(ForeignKey("countries.iso3"), index=True)
    source_id: Mapped[str] = mapped_column(String(96), index=True)
    metric: Mapped[str] = mapped_column(String(255), index=True)
    unit: Mapped[str | None] = mapped_column(String(96), nullable=True)
    target_date: Mapped[date] = mapped_column(Date, index=True)
    predicted_value: Mapped[float] = mapped_column(Float)
    lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provenance_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    limitations: Mapped[list] = mapped_column(JSON, default=list)

    model: Mapped["ForecastModel"] = relationship(back_populates="uploaded_prediction_points")


class ForecastBenchmarkDatasetSnapshot(Base):
    __tablename__ = "forecast_benchmark_dataset_snapshots"
    __table_args__ = (
        Index("ix_forecast_dataset_country_created", "country_iso3", "created_at"),
        Index("ix_forecast_dataset_series", "country_iso3", "source_id", "metric"),
        Index("ix_forecast_dataset_hash", "dataset_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_iso3: Mapped[str] = mapped_column(ForeignKey("countries.iso3"), index=True)
    source_id: Mapped[str] = mapped_column(String(96), index=True)
    signal_category: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    metric: Mapped[str] = mapped_column(String(255), index=True)
    unit: Mapped[str | None] = mapped_column(String(96), nullable=True)
    frequency: Mapped[str] = mapped_column(String(32), default="weekly")
    horizon_periods: Mapped[int] = mapped_column(Integer, default=4)
    split_strategy: Mapped[str] = mapped_column(String(64), default="last_n_periods")
    train_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    train_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    test_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    test_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_dates_json: Mapped[list] = mapped_column(JSON, default=list)
    observation_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    train_observation_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    test_observation_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    train_rows_json: Mapped[list] = mapped_column(JSON, default=list)
    test_rows_json: Mapped[list] = mapped_column(JSON, default=list)
    dataset_hash: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(64), default="ready")
    quality_warnings_json: Mapped[list] = mapped_column(JSON, default=list)
    limitations_json: Mapped[list] = mapped_column(JSON, default=list)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    runs: Mapped[list["ForecastBenchmarkRun"]] = relationship(back_populates="dataset_snapshot")
    prediction_sets: Mapped[list["UploadedPredictionSet"]] = relationship(back_populates="dataset_snapshot")


class ForecastChallengeSnapshot(Base):
    __tablename__ = "forecast_challenge_snapshots"
    __table_args__ = (
        Index("ix_forecast_challenge_country_created", "country_iso3", "created_at"),
        Index("ix_forecast_challenge_series", "country_iso3", "source_id", "metric"),
        Index("ix_forecast_challenge_mode_status", "mode", "status"),
        Index("ix_forecast_challenge_hash", "dataset_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(String(64), index=True)
    country_iso3: Mapped[str] = mapped_column(ForeignKey("countries.iso3"), index=True)
    source_id: Mapped[str] = mapped_column(String(96), index=True)
    signal_category: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    metric: Mapped[str] = mapped_column(String(255), index=True)
    unit: Mapped[str | None] = mapped_column(String(96), nullable=True)
    frequency: Mapped[str] = mapped_column(String(32), default="weekly")
    horizon_periods: Mapped[int] = mapped_column(Integer, default=4)
    split_strategy: Mapped[str] = mapped_column(String(64), default="last_n_periods")
    cutoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    train_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    train_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_dates_json: Mapped[list] = mapped_column(JSON, default=list)
    observation_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    train_observation_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    holdout_observation_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    train_rows_json: Mapped[list] = mapped_column(JSON, default=list)
    holdout_rows_json: Mapped[list] = mapped_column(JSON, default=list)
    dataset_hash: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(64), default="draft", index=True)
    quality_warnings_json: Mapped[list] = mapped_column(JSON, default=list)
    limitations_json: Mapped[list] = mapped_column(JSON, default=list)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=utc_now)

    prediction_sets: Mapped[list["PredictionSet"]] = relationship(back_populates="challenge", cascade="all, delete-orphan")
    scores: Mapped[list["ForecastScore"]] = relationship(back_populates="challenge", cascade="all, delete-orphan")


class Submitter(Base):
    __tablename__ = "submitters"
    __table_args__ = (
        Index("ix_submitters_verification", "verification_status"),
        Index("ix_submitters_display_org", "display_name", "organization"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    affiliation_type: Mapped[str | None] = mapped_column(String(96), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(64), default="unverified", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=utc_now)

    prediction_sets: Mapped[list["PredictionSet"]] = relationship(back_populates="submitter")
    uploaded_prediction_sets: Mapped[list["UploadedPredictionSet"]] = relationship(back_populates="submitter")


class PredictionSet(Base):
    __tablename__ = "prediction_sets"
    __table_args__ = (
        Index("ix_prediction_sets_challenge_model", "challenge_id", "model_id"),
        Index("ix_prediction_sets_series", "country_iso3", "source_id", "metric"),
        Index("ix_prediction_sets_source_track", "prediction_source", "submission_track"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("forecast_challenge_snapshots.id"), index=True)
    model_id: Mapped[str] = mapped_column(String(128), index=True)
    model_name: Mapped[str] = mapped_column(String(255))
    prediction_source: Mapped[str] = mapped_column(String(64), default="built_in", index=True)
    submission_track: Mapped[str] = mapped_column(String(64), default="internal_baseline", index=True)
    review_status: Mapped[str] = mapped_column(String(64), default="approved", index=True)
    validation_status: Mapped[str] = mapped_column(String(64), default="valid_for_snapshot", index=True)
    scoring_status: Mapped[str] = mapped_column(String(64), default="unscored", index=True)
    submitter_id: Mapped[int | None] = mapped_column(ForeignKey("submitters.id"), nullable=True, index=True)
    country_iso3: Mapped[str] = mapped_column(ForeignKey("countries.iso3"), index=True)
    source_id: Mapped[str] = mapped_column(String(96), index=True)
    signal_category: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    metric: Mapped[str] = mapped_column(String(255), index=True)
    unit: Mapped[str | None] = mapped_column(String(96), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(32), nullable=True)
    horizon_periods: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitter_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitter_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    method_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    code_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    provenance_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    visibility: Mapped[str] = mapped_column(String(32), default="public", index=True)
    disclosure_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations_json: Mapped[list] = mapped_column(JSON, default=list)
    warnings_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=utc_now)

    challenge: Mapped["ForecastChallengeSnapshot"] = relationship(back_populates="prediction_sets")
    submitter: Mapped["Submitter | None"] = relationship(back_populates="prediction_sets")
    points: Mapped[list["PredictionPoint"]] = relationship(back_populates="prediction_set", cascade="all, delete-orphan")
    scores: Mapped[list["ForecastScore"]] = relationship(back_populates="prediction_set", cascade="all, delete-orphan")
    review_decisions: Mapped[list["ReviewDecision"]] = relationship(
        back_populates="prediction_set",
        cascade="all, delete-orphan",
    )


class PredictionPoint(Base):
    __tablename__ = "prediction_points"
    __table_args__ = (Index("ix_prediction_points_set_date", "prediction_set_id", "target_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_set_id: Mapped[int] = mapped_column(ForeignKey("prediction_sets.id"), index=True)
    target_date: Mapped[date] = mapped_column(Date, index=True)
    predicted_value: Mapped[float] = mapped_column(Float)
    lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(96), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provenance_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    prediction_set: Mapped["PredictionSet"] = relationship(back_populates="points")


class ForecastScore(Base):
    __tablename__ = "forecast_scores"
    __table_args__ = (
        Index("ix_forecast_scores_challenge_status", "challenge_id", "status"),
        Index("ix_forecast_scores_prediction_set", "prediction_set_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("forecast_challenge_snapshots.id"), index=True)
    prediction_set_id: Mapped[int] = mapped_column(ForeignKey("prediction_sets.id"), index=True)
    status: Mapped[str] = mapped_column(String(64), default="pending_truth", index=True)
    mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    rmse: Mapped[float | None] = mapped_column(Float, nullable=True)
    smape: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_scored: Mapped[int] = mapped_column(Integer, default=0)
    n_expected: Mapped[int] = mapped_column(Integer, default=0)
    rank_smape: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank_rmse: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank_mae: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings_json: Mapped[list] = mapped_column(JSON, default=list)
    limitations_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=utc_now)

    challenge: Mapped["ForecastChallengeSnapshot"] = relationship(back_populates="scores")
    prediction_set: Mapped["PredictionSet"] = relationship(back_populates="scores")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    __table_args__ = (Index("ix_review_decisions_prediction_set_created", "prediction_set_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_set_id: Mapped[int] = mapped_column(ForeignKey("prediction_sets.id"), index=True)
    review_status: Mapped[str] = mapped_column(String(64), index=True)
    reviewer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    prediction_set: Mapped["PredictionSet"] = relationship(back_populates="review_decisions")


class UploadedPredictionSet(Base):
    __tablename__ = "uploaded_prediction_sets"
    __table_args__ = (
        Index("ix_uploaded_prediction_sets_lookup", "country_iso3", "source_id", "metric"),
        Index("ix_uploaded_prediction_sets_snapshot", "benchmark_dataset_snapshot_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    benchmark_dataset_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("forecast_benchmark_dataset_snapshots.id"),
        nullable=True,
        index=True,
    )
    model_id: Mapped[str] = mapped_column(String(128), index=True)
    model_name: Mapped[str] = mapped_column(String(255))
    country_iso3: Mapped[str] = mapped_column(ForeignKey("countries.iso3"), index=True)
    source_id: Mapped[str] = mapped_column(String(96), index=True)
    metric: Mapped[str] = mapped_column(String(255), index=True)
    unit: Mapped[str | None] = mapped_column(String(96), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(32), nullable=True)
    horizon_periods: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    provenance_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    user_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(64), default="stored_unmatched")
    submitter_id: Mapped[int | None] = mapped_column(ForeignKey("submitters.id"), nullable=True, index=True)
    submitter_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitter_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submission_track: Mapped[str] = mapped_column(String(64), default="public", index=True)
    review_status: Mapped[str] = mapped_column(String(64), default="unreviewed", index=True)
    visibility: Mapped[str] = mapped_column(String(32), default="public", index=True)
    method_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    code_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    disclosure_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations_json: Mapped[list] = mapped_column(JSON, default=list)
    validation_warnings_json: Mapped[list] = mapped_column(JSON, default=list)
    validation_errors_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    dataset_snapshot: Mapped["ForecastBenchmarkDatasetSnapshot | None"] = relationship(back_populates="prediction_sets")
    submitter: Mapped["Submitter | None"] = relationship(back_populates="uploaded_prediction_sets")
    points: Mapped[list["UploadedPredictionPoint"]] = relationship(
        back_populates="prediction_set",
        cascade="all, delete-orphan",
    )


class UploadedPredictionPoint(Base):
    __tablename__ = "uploaded_prediction_points"
    __table_args__ = (Index("ix_uploaded_prediction_points_set_date", "prediction_set_id", "target_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_set_id: Mapped[int] = mapped_column(ForeignKey("uploaded_prediction_sets.id"), index=True)
    target_date: Mapped[date] = mapped_column(Date, index=True)
    predicted_value: Mapped[float] = mapped_column(Float)
    lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(96), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provenance_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    prediction_set: Mapped["UploadedPredictionSet"] = relationship(back_populates="points")


class ForecastBenchmarkRun(Base):
    __tablename__ = "forecast_benchmark_runs"
    __table_args__ = (
        Index("ix_forecast_benchmark_country_created", "country_iso3", "created_at"),
        Index("ix_forecast_benchmark_series", "country_iso3", "source_id", "metric"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("forecast_benchmark_dataset_snapshots.id"),
        nullable=True,
        index=True,
    )
    country_iso3: Mapped[str] = mapped_column(ForeignKey("countries.iso3"), index=True)
    source_id: Mapped[str] = mapped_column(String(96), index=True)
    metric: Mapped[str] = mapped_column(String(255), index=True)
    unit: Mapped[str | None] = mapped_column(String(96), nullable=True)
    frequency: Mapped[str] = mapped_column(String(32), default="weekly")
    horizon_periods: Mapped[int] = mapped_column(Integer, default=4)
    train_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    train_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    requested_model_ids: Mapped[list] = mapped_column(JSON, default=list)
    uploaded_prediction_set_ids: Mapped[list] = mapped_column(JSON, default=list)
    output_status: Mapped[str] = mapped_column(String(64), default="complete")
    explanation: Mapped[str] = mapped_column(Text)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    comparison: Mapped[list] = mapped_column(JSON, default=list)
    data_quality_notes: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    dataset_snapshot: Mapped["ForecastBenchmarkDatasetSnapshot | None"] = relationship(back_populates="runs")
    results: Mapped[list["ForecastBenchmarkResult"]] = relationship(
        back_populates="benchmark_run",
        cascade="all, delete-orphan",
    )


class ForecastBenchmarkResult(Base):
    __tablename__ = "forecast_benchmark_results"
    __table_args__ = (Index("ix_forecast_benchmark_result_run_model", "benchmark_run_id", "model_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    benchmark_run_id: Mapped[int] = mapped_column(ForeignKey("forecast_benchmark_runs.id"), index=True)
    dataset_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("forecast_benchmark_dataset_snapshots.id"),
        nullable=True,
        index=True,
    )
    model_id: Mapped[str] = mapped_column(String(128), index=True)
    model_name: Mapped[str] = mapped_column(String(255))
    model_kind: Mapped[str] = mapped_column(String(64))
    result_type: Mapped[str] = mapped_column(String(64), default="builtin_model")
    status: Mapped[str] = mapped_column(String(64), default="complete")
    mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    rmse: Mapped[float | None] = mapped_column(Float, nullable=True)
    smape: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_train: Mapped[int] = mapped_column(Integer, default=0)
    n_test: Mapped[int] = mapped_column(Integer, default=0)
    train_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    train_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    test_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    test_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provenance_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    data_quality_notes: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    benchmark_run: Mapped["ForecastBenchmarkRun"] = relationship(back_populates="results")
    points: Mapped[list["ForecastBenchmarkPredictionPoint"]] = relationship(
        back_populates="benchmark_result",
        cascade="all, delete-orphan",
    )


class ForecastBenchmarkPredictionPoint(Base):
    __tablename__ = "forecast_benchmark_prediction_points"
    __table_args__ = (Index("ix_forecast_benchmark_point_result_date", "benchmark_result_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    benchmark_result_id: Mapped[int] = mapped_column(ForeignKey("forecast_benchmark_results.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    observed_value: Mapped[float] = mapped_column(Float)
    predicted_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    absolute_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    percentage_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(96), nullable=True)

    benchmark_result: Mapped["ForecastBenchmarkResult"] = relationship(back_populates="points")
