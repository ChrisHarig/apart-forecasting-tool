"""add forecast benchmark tables

Revision ID: 20260425_0001
Revises:
Create Date: 2026-04-25 18:30:00.000000
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260425_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forecast_models",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("model_kind", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("provenance_url", sa.String(length=1024), nullable=True),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_forecast_models_name", "forecast_models", ["name"])
    op.create_index("ix_forecast_models_model_kind", "forecast_models", ["model_kind"])

    op.create_table(
        "uploaded_forecast_prediction_points",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("country_iso3", sa.String(length=3), nullable=False),
        sa.Column("source_id", sa.String(length=96), nullable=False),
        sa.Column("metric", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=96), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("predicted_value", sa.Float(), nullable=False),
        sa.Column("lower", sa.Float(), nullable=True),
        sa.Column("upper", sa.Float(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provenance_url", sa.String(length=1024), nullable=True),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["country_iso3"], ["countries.iso3"]),
        sa.ForeignKeyConstraint(["model_id"], ["forecast_models.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uploaded_forecast_prediction_points_model_id", "uploaded_forecast_prediction_points", ["model_id"])
    op.create_index("ix_uploaded_forecast_prediction_points_country_iso3", "uploaded_forecast_prediction_points", ["country_iso3"])
    op.create_index("ix_uploaded_forecast_prediction_points_source_id", "uploaded_forecast_prediction_points", ["source_id"])
    op.create_index("ix_uploaded_forecast_prediction_points_metric", "uploaded_forecast_prediction_points", ["metric"])
    op.create_index("ix_uploaded_forecast_prediction_points_target_date", "uploaded_forecast_prediction_points", ["target_date"])
    op.create_index(
        "ix_uploaded_forecast_lookup",
        "uploaded_forecast_prediction_points",
        ["country_iso3", "source_id", "metric", "target_date"],
    )

    op.create_table(
        "forecast_benchmark_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("country_iso3", sa.String(length=3), nullable=False),
        sa.Column("source_id", sa.String(length=96), nullable=False),
        sa.Column("metric", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=96), nullable=True),
        sa.Column("frequency", sa.String(length=32), nullable=False),
        sa.Column("horizon_periods", sa.Integer(), nullable=False),
        sa.Column("train_start", sa.Date(), nullable=True),
        sa.Column("train_end", sa.Date(), nullable=True),
        sa.Column("requested_model_ids", sa.JSON(), nullable=False),
        sa.Column("output_status", sa.String(length=64), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("comparison", sa.JSON(), nullable=False),
        sa.Column("data_quality_notes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["country_iso3"], ["countries.iso3"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_forecast_benchmark_runs_country_iso3", "forecast_benchmark_runs", ["country_iso3"])
    op.create_index(
        "ix_forecast_benchmark_country_created",
        "forecast_benchmark_runs",
        ["country_iso3", "created_at"],
    )
    op.create_index(
        "ix_forecast_benchmark_series",
        "forecast_benchmark_runs",
        ["country_iso3", "source_id", "metric"],
    )

    op.create_table(
        "forecast_benchmark_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("benchmark_run_id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("mae", sa.Float(), nullable=True),
        sa.Column("rmse", sa.Float(), nullable=True),
        sa.Column("smape", sa.Float(), nullable=True),
        sa.Column("n_train", sa.Integer(), nullable=False),
        sa.Column("n_test", sa.Integer(), nullable=False),
        sa.Column("train_start", sa.Date(), nullable=True),
        sa.Column("train_end", sa.Date(), nullable=True),
        sa.Column("test_start", sa.Date(), nullable=True),
        sa.Column("test_end", sa.Date(), nullable=True),
        sa.Column("provenance_url", sa.String(length=1024), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("data_quality_notes", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["benchmark_run_id"], ["forecast_benchmark_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_forecast_benchmark_results_benchmark_run_id", "forecast_benchmark_results", ["benchmark_run_id"])
    op.create_index("ix_forecast_benchmark_results_model_id", "forecast_benchmark_results", ["model_id"])
    op.create_index(
        "ix_forecast_benchmark_result_run_model",
        "forecast_benchmark_results",
        ["benchmark_run_id", "model_id"],
    )

    op.create_table(
        "forecast_benchmark_prediction_points",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("benchmark_result_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("observed_value", sa.Float(), nullable=False),
        sa.Column("predicted_value", sa.Float(), nullable=False),
        sa.Column("lower", sa.Float(), nullable=True),
        sa.Column("upper", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=96), nullable=True),
        sa.ForeignKeyConstraint(["benchmark_result_id"], ["forecast_benchmark_results.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_forecast_benchmark_point_result_date",
        "forecast_benchmark_prediction_points",
        ["benchmark_result_id", "date"],
    )
    op.create_index(
        "ix_forecast_benchmark_prediction_points_benchmark_result_id",
        "forecast_benchmark_prediction_points",
        ["benchmark_result_id"],
    )


def downgrade() -> None:
    op.drop_table("forecast_benchmark_prediction_points")
    op.drop_table("forecast_benchmark_results")
    op.drop_table("forecast_benchmark_runs")
    op.drop_table("uploaded_forecast_prediction_points")
    op.drop_table("forecast_models")
