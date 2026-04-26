"""add forecast benchmark dataset snapshots

Revision ID: 20260426_0002
Revises: 20260425_0001
Create Date: 2026-04-26 12:00:00.000000
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260426_0002"
down_revision: str | None = "20260425_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    op.create_table(
        "forecast_benchmark_dataset_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("country_iso3", sa.String(length=3), nullable=False),
        sa.Column("source_id", sa.String(length=96), nullable=False),
        sa.Column("signal_category", sa.String(length=96), nullable=True),
        sa.Column("metric", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=96), nullable=True),
        sa.Column("frequency", sa.String(length=32), nullable=False),
        sa.Column("horizon_periods", sa.Integer(), nullable=False),
        sa.Column("split_strategy", sa.String(length=64), nullable=False),
        sa.Column("train_start", sa.Date(), nullable=True),
        sa.Column("train_end", sa.Date(), nullable=True),
        sa.Column("test_start", sa.Date(), nullable=True),
        sa.Column("test_end", sa.Date(), nullable=True),
        sa.Column("target_dates_json", sa.JSON(), nullable=False),
        sa.Column("observation_ids_json", sa.JSON(), nullable=False),
        sa.Column("train_observation_ids_json", sa.JSON(), nullable=False),
        sa.Column("test_observation_ids_json", sa.JSON(), nullable=False),
        sa.Column("train_rows_json", sa.JSON(), nullable=False),
        sa.Column("test_rows_json", sa.JSON(), nullable=False),
        sa.Column("dataset_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("quality_warnings_json", sa.JSON(), nullable=False),
        sa.Column("limitations_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["country_iso3"], ["countries.iso3"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_forecast_dataset_country_created", "forecast_benchmark_dataset_snapshots", ["country_iso3", "created_at"])
    op.create_index("ix_forecast_dataset_series", "forecast_benchmark_dataset_snapshots", ["country_iso3", "source_id", "metric"])
    op.create_index("ix_forecast_dataset_hash", "forecast_benchmark_dataset_snapshots", ["dataset_hash"])

    op.create_table(
        "uploaded_prediction_sets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("benchmark_dataset_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("country_iso3", sa.String(length=3), nullable=False),
        sa.Column("source_id", sa.String(length=96), nullable=False),
        sa.Column("metric", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=96), nullable=True),
        sa.Column("frequency", sa.String(length=32), nullable=True),
        sa.Column("horizon_periods", sa.Integer(), nullable=True),
        sa.Column("target_start", sa.Date(), nullable=True),
        sa.Column("target_end", sa.Date(), nullable=True),
        sa.Column("provenance_url", sa.String(length=1024), nullable=True),
        sa.Column("user_notes", sa.Text(), nullable=True),
        sa.Column("validation_status", sa.String(length=64), nullable=False),
        sa.Column("limitations_json", sa.JSON(), nullable=False),
        sa.Column("validation_warnings_json", sa.JSON(), nullable=False),
        sa.Column("validation_errors_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["benchmark_dataset_snapshot_id"], ["forecast_benchmark_dataset_snapshots.id"]),
        sa.ForeignKeyConstraint(["country_iso3"], ["countries.iso3"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uploaded_prediction_sets_lookup", "uploaded_prediction_sets", ["country_iso3", "source_id", "metric"])
    op.create_index("ix_uploaded_prediction_sets_snapshot", "uploaded_prediction_sets", ["benchmark_dataset_snapshot_id"])
    op.create_index("ix_uploaded_prediction_sets_model_id", "uploaded_prediction_sets", ["model_id"])

    op.create_table(
        "uploaded_prediction_points",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prediction_set_id", sa.Integer(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("predicted_value", sa.Float(), nullable=False),
        sa.Column("lower", sa.Float(), nullable=True),
        sa.Column("upper", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=96), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provenance_url", sa.String(length=1024), nullable=True),
        sa.ForeignKeyConstraint(["prediction_set_id"], ["uploaded_prediction_sets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uploaded_prediction_points_prediction_set_id", "uploaded_prediction_points", ["prediction_set_id"])
    op.create_index("ix_uploaded_prediction_points_target_date", "uploaded_prediction_points", ["target_date"])
    op.create_index("ix_uploaded_prediction_points_set_date", "uploaded_prediction_points", ["prediction_set_id", "target_date"])

    op.add_column("forecast_benchmark_runs", sa.Column("dataset_snapshot_id", sa.Integer(), nullable=True))
    op.add_column("forecast_benchmark_runs", sa.Column("uploaded_prediction_set_ids", sa.JSON(), nullable=True))
    if dialect != "sqlite":
        op.create_foreign_key(
            "fk_forecast_benchmark_runs_dataset_snapshot_id",
            "forecast_benchmark_runs",
            "forecast_benchmark_dataset_snapshots",
            ["dataset_snapshot_id"],
            ["id"],
        )
    op.create_index("ix_forecast_benchmark_runs_dataset_snapshot_id", "forecast_benchmark_runs", ["dataset_snapshot_id"])

    op.add_column("forecast_benchmark_results", sa.Column("dataset_snapshot_id", sa.Integer(), nullable=True))
    op.add_column("forecast_benchmark_results", sa.Column("result_type", sa.String(length=64), nullable=True))
    op.add_column("forecast_benchmark_results", sa.Column("rank", sa.Integer(), nullable=True))
    op.add_column("forecast_benchmark_results", sa.Column("metadata", sa.JSON(), nullable=True))
    op.add_column("forecast_benchmark_results", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    if dialect != "sqlite":
        op.create_foreign_key(
            "fk_forecast_benchmark_results_dataset_snapshot_id",
            "forecast_benchmark_results",
            "forecast_benchmark_dataset_snapshots",
            ["dataset_snapshot_id"],
            ["id"],
        )
    op.create_index("ix_forecast_benchmark_results_dataset_snapshot_id", "forecast_benchmark_results", ["dataset_snapshot_id"])

    op.add_column("forecast_benchmark_prediction_points", sa.Column("absolute_error", sa.Float(), nullable=True))
    op.add_column("forecast_benchmark_prediction_points", sa.Column("percentage_error", sa.Float(), nullable=True))


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    op.drop_column("forecast_benchmark_prediction_points", "percentage_error")
    op.drop_column("forecast_benchmark_prediction_points", "absolute_error")
    op.drop_index("ix_forecast_benchmark_results_dataset_snapshot_id", table_name="forecast_benchmark_results")
    if dialect != "sqlite":
        op.drop_constraint(
            "fk_forecast_benchmark_results_dataset_snapshot_id",
            "forecast_benchmark_results",
            type_="foreignkey",
        )
    op.drop_column("forecast_benchmark_results", "created_at")
    op.drop_column("forecast_benchmark_results", "metadata")
    op.drop_column("forecast_benchmark_results", "rank")
    op.drop_column("forecast_benchmark_results", "result_type")
    op.drop_column("forecast_benchmark_results", "dataset_snapshot_id")
    op.drop_index("ix_forecast_benchmark_runs_dataset_snapshot_id", table_name="forecast_benchmark_runs")
    if dialect != "sqlite":
        op.drop_constraint(
            "fk_forecast_benchmark_runs_dataset_snapshot_id",
            "forecast_benchmark_runs",
            type_="foreignkey",
        )
    op.drop_column("forecast_benchmark_runs", "uploaded_prediction_set_ids")
    op.drop_column("forecast_benchmark_runs", "dataset_snapshot_id")
    op.drop_table("uploaded_prediction_points")
    op.drop_table("uploaded_prediction_sets")
    op.drop_table("forecast_benchmark_dataset_snapshots")
