"""add submitter metadata and review decisions

Revision ID: 20260426_0006
Revises: 20260426_0005
Create Date: 2026-04-26 17:00:00.000000
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260426_0006"
down_revision: str | None = "20260426_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "submitters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("organization", sa.String(length=255), nullable=True),
        sa.Column("affiliation_type", sa.String(length=96), nullable=True),
        sa.Column("verification_status", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_submitters_display_name", "submitters", ["display_name"])
    op.create_index("ix_submitters_email", "submitters", ["email"])
    op.create_index("ix_submitters_organization", "submitters", ["organization"])
    op.create_index("ix_submitters_verification_status", "submitters", ["verification_status"])
    op.create_index("ix_submitters_verification", "submitters", ["verification_status"])
    op.create_index("ix_submitters_display_org", "submitters", ["display_name", "organization"])

    with op.batch_alter_table("prediction_sets") as batch_op:
        batch_op.add_column(sa.Column("submitter_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("visibility", sa.String(length=32), nullable=False, server_default="public"))
        batch_op.add_column(sa.Column("disclosure_notes", sa.Text(), nullable=True))
        batch_op.create_foreign_key("fk_prediction_sets_submitter_id", "submitters", ["submitter_id"], ["id"])
        batch_op.create_index("ix_prediction_sets_submitter_id", ["submitter_id"])
        batch_op.create_index("ix_prediction_sets_visibility", ["visibility"])

    op.create_table(
        "review_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prediction_set_id", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(length=64), nullable=False),
        sa.Column("reviewer_name", sa.String(length=255), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["prediction_set_id"], ["prediction_sets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_decisions_prediction_set_id", "review_decisions", ["prediction_set_id"])
    op.create_index("ix_review_decisions_review_status", "review_decisions", ["review_status"])
    op.create_index(
        "ix_review_decisions_prediction_set_created",
        "review_decisions",
        ["prediction_set_id", "created_at"],
    )

    with op.batch_alter_table("uploaded_prediction_sets") as batch_op:
        batch_op.add_column(sa.Column("submitter_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("submitter_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("submitter_email", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("organization", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("submission_track", sa.String(length=64), nullable=False, server_default="public"))
        batch_op.add_column(sa.Column("review_status", sa.String(length=64), nullable=False, server_default="unreviewed"))
        batch_op.add_column(sa.Column("visibility", sa.String(length=32), nullable=False, server_default="public"))
        batch_op.add_column(sa.Column("method_summary", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("model_url", sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column("code_url", sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column("disclosure_notes", sa.Text(), nullable=True))
        batch_op.create_foreign_key("fk_uploaded_prediction_sets_submitter_id", "submitters", ["submitter_id"], ["id"])
        batch_op.create_index("ix_uploaded_prediction_sets_submitter_id", ["submitter_id"])
        batch_op.create_index("ix_uploaded_prediction_sets_submission_track", ["submission_track"])
        batch_op.create_index("ix_uploaded_prediction_sets_review_status", ["review_status"])
        batch_op.create_index("ix_uploaded_prediction_sets_visibility", ["visibility"])


def downgrade() -> None:
    op.drop_table("review_decisions")
    with op.batch_alter_table("uploaded_prediction_sets") as batch_op:
        batch_op.drop_index("ix_uploaded_prediction_sets_visibility")
        batch_op.drop_index("ix_uploaded_prediction_sets_review_status")
        batch_op.drop_index("ix_uploaded_prediction_sets_submission_track")
        batch_op.drop_index("ix_uploaded_prediction_sets_submitter_id")
        batch_op.drop_constraint("fk_uploaded_prediction_sets_submitter_id", type_="foreignkey")
        batch_op.drop_column("disclosure_notes")
        batch_op.drop_column("code_url")
        batch_op.drop_column("model_url")
        batch_op.drop_column("method_summary")
        batch_op.drop_column("visibility")
        batch_op.drop_column("review_status")
        batch_op.drop_column("submission_track")
        batch_op.drop_column("organization")
        batch_op.drop_column("submitter_email")
        batch_op.drop_column("submitter_name")
        batch_op.drop_column("submitter_id")
    with op.batch_alter_table("prediction_sets") as batch_op:
        batch_op.drop_index("ix_prediction_sets_visibility")
        batch_op.drop_index("ix_prediction_sets_submitter_id")
        batch_op.drop_constraint("fk_prediction_sets_submitter_id", type_="foreignkey")
        batch_op.drop_column("disclosure_notes")
        batch_op.drop_column("visibility")
        batch_op.drop_column("submitter_id")
    op.drop_table("submitters")
