"""Add shared countdown, together-time, reporting, and lifecycle records.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-10
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _upgrade_questions_and_notes() -> None:
    """Add couple scope and idempotent note creation."""

    op.add_column("questions", sa.Column("couple_id", sa.Uuid(), nullable=True))
    op.add_column("questions", sa.Column("created_by", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_questions_couple_id", "questions", "couples", ["couple_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_questions_created_by",
        "questions",
        "accounts",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_questions_couple_id", "questions", ["couple_id"])
    op.drop_constraint("uq_questions_date_normalized_hash", "questions", type_="unique")
    op.create_index(
        "uq_questions_scope_normalized_hash",
        "questions",
        ["publish_date", "couple_id", "normalized_hash"],
        unique=True,
        postgresql_nulls_not_distinct=True,
    )
    op.add_column("notes", sa.Column("creation_operation_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE notes SET creation_operation_id = id WHERE creation_operation_id IS NULL")
    op.alter_column("notes", "creation_operation_id", nullable=False)
    op.create_unique_constraint(
        "uq_notes_creation_operation_id", "notes", ["creation_operation_id"]
    )



def _create_together_buckets() -> None:
    """Create non-overlapping together-time minute storage."""

    op.create_table(
        "together_buckets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("estimated_distance_m", sa.Float(), nullable=False),
        sa.Column("corrected_by", sa.Uuid(), nullable=True),
        sa.Column("correction_reason", sa.String(240), nullable=True),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "duration_seconds >= 0 AND duration_seconds <= 60",
            name="ck_together_bucket_duration",
        ),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["corrected_by"], ["accounts.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("couple_id", "bucket_start", name="uq_together_bucket_minute"),
    )
    op.create_index("ix_together_buckets_couple_id", "together_buckets", ["couple_id"])



def _create_countdown_tables() -> None:
    """Create shared countdown state and idempotency records."""

    op.create_table(
        "countdowns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("occurs_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("notes", sa.String(1000), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision >= 0", name="ck_countdown_revision"),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["accounts.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_countdowns_couple_id", "countdowns", ["couple_id"])



def _create_review_and_lifecycle_tables() -> None:
    """Create question review, deletion, and AI provenance records."""

    op.create_table(
        "countdown_operations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("countdown_id", sa.Uuid(), nullable=False),
        sa.Column("resulting_revision", sa.Integer(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["countdown_id"], ["countdowns.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("couple_id", "operation_id", name="uq_countdown_operation"),
    )

    op.create_table(
        "question_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("reporter_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("question_id", "couple_id", name="uq_question_report_couple"),
    )

    op.create_table(
        "deletion_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), nullable=True, unique=True),
        sa.Column("execute_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "generation_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("publish_date", sa.Date(), nullable=False, unique=True),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("model_digest", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("validation_results", sa.JSON(), nullable=False),
        sa.Column("selected_question_ids", sa.JSON(), nullable=False),
        sa.Column("fallback_reason", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    """Create the remaining server-side 1.0 feature records."""

    _upgrade_questions_and_notes()
    _create_together_buckets()
    _create_countdown_tables()
    _create_review_and_lifecycle_tables()


def downgrade() -> None:
    """Remove 1.0 feature records and return questions to global scope."""

    for table in (
        "generation_batches",
        "deletion_jobs",
        "question_reports",
        "countdown_operations",
        "countdowns",
        "together_buckets",
    ):
        op.drop_table(table)
    op.drop_index("uq_questions_scope_normalized_hash", table_name="questions")
    op.create_unique_constraint(
        "uq_questions_date_normalized_hash",
        "questions",
        ["publish_date", "normalized_hash"],
    )
    op.drop_index("ix_questions_couple_id", table_name="questions")
    op.drop_constraint("fk_questions_created_by", "questions", type_="foreignkey")
    op.drop_constraint("fk_questions_couple_id", "questions", type_="foreignkey")
    op.drop_column("questions", "created_by")
    op.drop_column("questions", "couple_id")
    op.drop_constraint("uq_notes_creation_operation_id", "notes", type_="unique")
    op.drop_column("notes", "creation_operation_id")
