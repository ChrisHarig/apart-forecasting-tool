"""add challenge prediction sets

Revision ID: 20260426_0004
Revises: 20260426_0003
Create Date: 2026-04-26 15:00:00.000000
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260426_0004"
down_revision: str | None = "20260426_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prediction_sets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("prediction_source", sa.String(length=64), nullable=False),
        sa.Column("submission_track", sa.String(length=64), nullable=False),
        sa.Column("review_status", sa.String(length=64), nullable=False),
        sa.Column("validation_status", sa.String(length=64), nullable=False),
        sa.Column("scoring_status", sa.String(length=64), nullable=False),
        sa.Column("country_iso3", sa.String(length=3), nullable=False),
        sa.Column("source_id", sa.String(length=96), nullable=False),
        sa.Column("signal_category", sa.String(length=96), nullable=True),
        sa.Column("metric", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=96), nullable=True),
        sa.Column("frequency", sa.String(length=32), nullable=True),
        sa.Column("horizon_periods", sa.Integer(), nullable=True),
        sa.Column("submitter_name", sa.String(length=255), nullable=True),
        sa.Column("submitter_email", sa.String(length=255), nullable=True),
        sa.Column("organization", sa.String(length=255), nullable=True),
        sa.Column("method_summary", sa.Text(), nullable=True),
        sa.Column("model_url", sa.String(length=1024), nullable=True),
        sa.Column("code_url", sa.String(length=1024), nullable=True),
        sa.Column("provenance_url", sa.String(length=1024), nullable=True),
        sa.Column("limitations_json", sa.JSON(), nullable=False),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["challenge_id"], ["forecast_challenge_snapshots.id"]),
        sa.ForeignKeyConstraint(["country_iso3"], ["countries.iso3"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prediction_sets_challenge_model", "prediction_sets", ["challenge_id", "model_id"])
    op.create_index("ix_prediction_sets_series", "prediction_sets", ["country_iso3", "source_id", "metric"])
    op.create_index("ix_prediction_sets_source_track", "prediction_sets", ["prediction_source", "submission_track"])
    op.create_index("ix_prediction_sets_challenge_id", "prediction_sets", ["challenge_id"])
    op.create_index("ix_prediction_sets_model_id", "prediction_sets", ["model_id"])
    op.create_index("ix_prediction_sets_country_iso3", "prediction_sets", ["country_iso3"])
    op.create_index("ix_prediction_sets_signal_category", "prediction_sets", ["signal_category"])
    op.create_index("ix_prediction_sets_prediction_source", "prediction_sets", ["prediction_source"])
    op.create_index("ix_prediction_sets_submission_track", "prediction_sets", ["submission_track"])
    op.create_index("ix_prediction_sets_review_status", "prediction_sets", ["review_status"])
    op.create_index("ix_prediction_sets_validation_status", "prediction_sets", ["validation_status"])
    op.create_index("ix_prediction_sets_scoring_status", "prediction_sets", ["scoring_status"])

    op.create_table(
        "prediction_points",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prediction_set_id", sa.Integer(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("predicted_value", sa.Float(), nullable=False),
        sa.Column("lower", sa.Float(), nullable=True),
        sa.Column("upper", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=96), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provenance_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["prediction_set_id"], ["prediction_sets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prediction_points_set_date", "prediction_points", ["prediction_set_id", "target_date"])
    op.create_index("ix_prediction_points_prediction_set_id", "prediction_points", ["prediction_set_id"])
    op.create_index("ix_prediction_points_target_date", "prediction_points", ["target_date"])


def downgrade() -> None:
    op.drop_table("prediction_points")
    op.drop_table("prediction_sets")
