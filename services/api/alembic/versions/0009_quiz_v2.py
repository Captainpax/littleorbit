"""Add revisioned daily quiz snapshots and interaction version two.

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create constrained quiz-day state while retaining legacy answers."""

    _add_question_columns()
    _create_question_indexes()
    _create_quiz_day_tables()
    _create_quiz_member_table()
    _create_quiz_draft_table()
    _create_quiz_operation_table()
    _add_generation_metadata()


def _add_question_columns() -> None:
    """Add interaction rendering and custom scheduling metadata."""

    op.add_column(
        "questions", sa.Column("option_icons", sa.JSON(), nullable=False, server_default="[]")
    )
    op.add_column("questions", sa.Column("scale_low_label", sa.String(32)))
    op.add_column("questions", sa.Column("scale_high_label", sa.String(32)))
    op.add_column(
        "questions",
        sa.Column("interaction_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("questions", sa.Column("display_order", sa.Integer()))
    op.add_column("questions", sa.Column("custom_slot", sa.Integer()))
    op.add_column(
        "questions",
        sa.Column("surprise", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def _create_question_indexes() -> None:
    """Prevent duplicate global positions and couple custom slots."""

    op.create_index(
        "uq_global_question_order",
        "questions",
        ["publish_date", "display_order"],
        unique=True,
        postgresql_where=sa.text(
            "couple_id IS NULL AND intimacy IS FALSE AND display_order IS NOT NULL"
        ),
    )
    op.create_index(
        "uq_custom_question_slot",
        "questions",
        ["couple_id", "publish_date", "custom_slot"],
        unique=True,
        postgresql_where=sa.text("couple_id IS NOT NULL AND custom_slot IS NOT NULL"),
    )


def _create_quiz_day_tables() -> None:
    """Create stable daily snapshots and their ordered question links."""

    op.create_table(
        "quiz_days",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "couple_id",
            sa.Uuid(),
            sa.ForeignKey("couples.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quiz_date", sa.Date(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revealed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision >= 0"),
        sa.UniqueConstraint("couple_id", "quiz_date"),
    )
    op.create_index("ix_quiz_days_couple_id", "quiz_days", ["couple_id"])
    op.create_index("ix_quiz_days_quiz_date", "quiz_days", ["quiz_date"])
    op.create_table(
        "quiz_day_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _foreign_uuid("quiz_day_id", "quiz_days.id", "CASCADE"),
        _foreign_uuid("question_id", "questions.id", "RESTRICT"),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position BETWEEN 1 AND 5"),
        sa.UniqueConstraint("quiz_day_id", "position"),
        sa.UniqueConstraint("quiz_day_id", "question_id"),
    )
    op.create_index("ix_quiz_day_questions_quiz_day_id", "quiz_day_questions", ["quiz_day_id"])
    op.create_index("ix_quiz_day_questions_question_id", "quiz_day_questions", ["question_id"])


def _create_quiz_member_table() -> None:
    """Store each member's reversible pre-reveal finish marker."""

    op.create_table(
        "quiz_day_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _foreign_uuid("quiz_day_id", "quiz_days.id", "CASCADE"),
        _foreign_uuid("account_id", "accounts.id", "CASCADE"),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("quiz_day_id", "account_id"),
    )
    op.create_index("ix_quiz_day_members_quiz_day_id", "quiz_day_members", ["quiz_day_id"])
    op.create_index("ix_quiz_day_members_account_id", "quiz_day_members", ["account_id"])


def _create_quiz_draft_table() -> None:
    """Store one revisioned private draft per account and question."""

    op.create_table(
        "quiz_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _foreign_uuid("quiz_day_id", "quiz_days.id", "CASCADE"),
        _foreign_uuid("question_id", "questions.id", "RESTRICT"),
        _foreign_uuid("account_id", "accounts.id", "CASCADE"),
        sa.Column("answer", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision >= 1"),
        sa.UniqueConstraint("quiz_day_id", "question_id", "account_id"),
    )
    for column in ("quiz_day_id", "question_id", "account_id"):
        op.create_index(f"ix_quiz_drafts_{column}", "quiz_drafts", [column])


def _create_quiz_operation_table() -> None:
    """Store content-free idempotency outcomes for quiz mutations."""

    op.create_table(
        "quiz_operations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _foreign_uuid("couple_id", "couples.id", "CASCADE"),
        sa.Column(
            "account_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL")
        ),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("couple_id", "account_id", "operation_id"),
    )
    op.create_index("ix_quiz_operations_couple_id", "quiz_operations", ["couple_id"])
    op.create_index("ix_quiz_operations_account_id", "quiz_operations", ["account_id"])


def _add_generation_metadata() -> None:
    """Retain reviewable candidates, duration, icons, and scale anchors."""

    op.add_column(
        "generation_batches",
        sa.Column("candidate_snapshot", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column("generation_batches", sa.Column("duration_ms", sa.Integer()))
    op.add_column(
        "curated_bank_questions",
        sa.Column("option_icons", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column("curated_bank_questions", sa.Column("scale_low_label", sa.String(32)))
    op.add_column("curated_bank_questions", sa.Column("scale_high_label", sa.String(32)))


def _foreign_uuid(name: str, target: str, ondelete: str) -> sa.Column[Any]:
    """Build one non-null UUID foreign-key column."""

    return sa.Column(name, sa.Uuid(), sa.ForeignKey(target, ondelete=ondelete), nullable=False)


def downgrade() -> None:
    """Remove v2 state while leaving legacy quiz tables intact."""

    op.drop_column("curated_bank_questions", "scale_high_label")
    op.drop_column("curated_bank_questions", "scale_low_label")
    op.drop_column("curated_bank_questions", "option_icons")
    op.drop_column("generation_batches", "duration_ms")
    op.drop_column("generation_batches", "candidate_snapshot")
    op.drop_table("quiz_operations")
    op.drop_table("quiz_drafts")
    op.drop_table("quiz_day_members")
    op.drop_table("quiz_day_questions")
    op.drop_table("quiz_days")
    op.drop_index("uq_custom_question_slot", table_name="questions")
    op.drop_index("uq_global_question_order", table_name="questions")
    for column in (
        "surprise", "custom_slot", "display_order", "interaction_version",
        "scale_high_label", "scale_low_label", "option_icons",
    ):
        op.drop_column("questions", column)
