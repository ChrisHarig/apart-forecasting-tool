"""add forecast challenge scores

Revision ID: 20260426_0005
Revises: 20260426_0004
Create Date: 2026-04-26 16:00:00.000000
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260426_0005"
down_revision: str | None = "20260426_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forecast_scores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("prediction_set_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("mae", sa.Float(), nullable=True),
        sa.Column("rmse", sa.Float(), nullable=True),
        sa.Column("smape", sa.Float(), nullable=True),
        sa.Column("n_scored", sa.Integer(), nullable=False),
        sa.Column("n_expected", sa.Integer(), nullable=False),
        sa.Column("rank_smape", sa.Integer(), nullable=True),
        sa.Column("rank_rmse", sa.Integer(), nullable=True),
        sa.Column("rank_mae", sa.Integer(), nullable=True),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.Column("limitations_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["challenge_id"], ["forecast_challenge_snapshots.id"]),
        sa.ForeignKeyConstraint(["prediction_set_id"], ["prediction_sets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_forecast_scores_challenge_id", "forecast_scores", ["challenge_id"])
    op.create_index("ix_forecast_scores_prediction_set_id", "forecast_scores", ["prediction_set_id"])
    op.create_index("ix_forecast_scores_status", "forecast_scores", ["status"])
    op.create_index("ix_forecast_scores_challenge_status", "forecast_scores", ["challenge_id", "status"])
    op.create_index("ix_forecast_scores_prediction_set", "forecast_scores", ["prediction_set_id"])


def downgrade() -> None:
    op.drop_table("forecast_scores")
