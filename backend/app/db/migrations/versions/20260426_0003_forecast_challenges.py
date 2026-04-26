"""add forecast challenge snapshots

Revision ID: 20260426_0003
Revises: 20260426_0002
Create Date: 2026-04-26 14:00:00.000000
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260426_0003"
down_revision: str | None = "20260426_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forecast_challenge_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("country_iso3", sa.String(length=3), nullable=False),
        sa.Column("source_id", sa.String(length=96), nullable=False),
        sa.Column("signal_category", sa.String(length=96), nullable=True),
        sa.Column("metric", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=96), nullable=True),
        sa.Column("frequency", sa.String(length=32), nullable=False),
        sa.Column("horizon_periods", sa.Integer(), nullable=False),
        sa.Column("split_strategy", sa.String(length=64), nullable=False),
        sa.Column("cutoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("train_start", sa.Date(), nullable=True),
        sa.Column("train_end", sa.Date(), nullable=True),
        sa.Column("target_start", sa.Date(), nullable=True),
        sa.Column("target_end", sa.Date(), nullable=True),
        sa.Column("target_dates_json", sa.JSON(), nullable=False),
        sa.Column("observation_ids_json", sa.JSON(), nullable=False),
        sa.Column("train_observation_ids_json", sa.JSON(), nullable=False),
        sa.Column("holdout_observation_ids_json", sa.JSON(), nullable=False),
        sa.Column("train_rows_json", sa.JSON(), nullable=False),
        sa.Column("holdout_rows_json", sa.JSON(), nullable=False),
        sa.Column("dataset_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("quality_warnings_json", sa.JSON(), nullable=False),
        sa.Column("limitations_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["country_iso3"], ["countries.iso3"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_forecast_challenge_country_created", "forecast_challenge_snapshots", ["country_iso3", "created_at"])
    op.create_index("ix_forecast_challenge_series", "forecast_challenge_snapshots", ["country_iso3", "source_id", "metric"])
    op.create_index("ix_forecast_challenge_mode_status", "forecast_challenge_snapshots", ["mode", "status"])
    op.create_index("ix_forecast_challenge_hash", "forecast_challenge_snapshots", ["dataset_hash"])


def downgrade() -> None:
    op.drop_table("forecast_challenge_snapshots")
