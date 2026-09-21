"""Add private feedback, semantic memory, and weekly AI state.

Revision ID: 0027
Revises: 0026
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Install exact vector search and versioned feedback/learning state."""

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    _create_feedback_tables()
    _create_intelligence_tables()
    op.execute(
        "INSERT INTO quiz_feedback_rollout (feature, enabled_at) "
        "VALUES ('question_feedback', CURRENT_TIMESTAMP)"
    )


def _create_feedback_tables() -> None:
    _create_feedback_rollout_table()
    _create_linked_feedback_table()
    _create_feedback_operation_table()
    _create_anonymous_review_table()
    _create_feedback_aggregate_table()


def _create_feedback_rollout_table() -> None:
    op.create_table(
        "quiz_feedback_rollout",
        sa.Column("feature", sa.String(length=40), primary_key=True),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=False),
    )


def _create_linked_feedback_table() -> None:
    op.create_table(
        "question_feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "quiz_day_id",
            sa.Uuid(),
            sa.ForeignKey("quiz_days.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            sa.Uuid(),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "couple_id",
            sa.Uuid(),
            sa.ForeignKey("couples.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("sanitized_review", sa.String(length=300)),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("editable_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "quiz_day_id", "question_id", "account_id", name="uq_question_feedback_actor"
        ),
        sa.CheckConstraint("stars BETWEEN 1 AND 5", name="ck_question_feedback_stars"),
        sa.CheckConstraint("revision >= 1", name="ck_question_feedback_revision"),
    )
    op.create_index("ix_question_feedback_expiry", "question_feedback", ["editable_until"])
    op.create_index("ix_question_feedback_question", "question_feedback", ["question_id"])


def _create_feedback_operation_table() -> None:
    op.create_table(
        "question_feedback_operations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "feedback_id",
            sa.Uuid(),
            sa.ForeignKey("question_feedback.id", ondelete="SET NULL"),
        ),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("result_revision", sa.Integer(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "operation_id", name="uq_feedback_operation_actor"),
    )
    op.create_index(
        "ix_feedback_operations_expiry", "question_feedback_operations", ["created_at"]
    )


def _create_anonymous_review_table() -> None:
    op.create_table(
        "anonymous_question_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "question_id",
            sa.Uuid(),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("sanitized_review", sa.String(length=300)),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("stars BETWEEN 1 AND 5", name="ck_anonymous_review_stars"),
    )
    op.create_index(
        "ix_anonymous_reviews_question_week",
        "anonymous_question_reviews",
        ["question_id", "week_start"],
    )
    op.create_index(
        "ix_anonymous_reviews_expiry", "anonymous_question_reviews", ["expires_at"]
    )


def _create_feedback_aggregate_table() -> None:
    op.create_table(
        "feedback_weekly_aggregates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "question_id",
            sa.Uuid(),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("rating_count", sa.Integer(), nullable=False),
        sa.Column("distinct_accounts", sa.Integer(), nullable=False),
        sa.Column("score_sum", sa.Integer(), nullable=False),
        sa.Column("tag_counts", sa.JSON(), nullable=False),
        sa.Column("themes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("question_id", "week_start", name="uq_feedback_aggregate_week"),
        sa.CheckConstraint("rating_count >= 0", name="ck_feedback_aggregate_count"),
        sa.CheckConstraint("distinct_accounts >= 0", name="ck_feedback_aggregate_accounts"),
    )


def _create_intelligence_tables() -> None:
    _create_question_concepts_table()
    _create_ai_state_tables()
    _create_question_reserve_table()
    _create_web_context_table()
    _seed_web_context_sources()


def _create_question_concepts_table() -> None:
    op.create_table(
        "question_concepts",
        sa.Column(
            "question_id",
            sa.Uuid(),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("concept_family", sa.String(length=80), nullable=False),
        sa.Column("concept_summary", sa.String(length=180), nullable=False),
        sa.Column("prompt_embedding", Vector(768)),
        sa.Column("concept_embedding", Vector(768)),
        sa.Column("embedding_model", sa.String(length=120), nullable=False),
        sa.Column("embedding_digest", sa.String(length=80), nullable=False),
        sa.Column("embedded_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_question_concepts_family", "question_concepts", ["concept_family"])
    op.create_index(
        "ix_question_concepts_model",
        "question_concepts",
        ["embedding_model", "embedding_digest"],
    )


def _create_ai_state_tables() -> None:
    op.create_table(
        "ai_policy_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("policy_json", sa.JSON(), nullable=False),
        sa.Column("evaluation_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('staged', 'active', 'rejected', 'superseded', 'rolled_back')",
            name="ck_ai_policy_status",
        ),
    )
    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_key", sa.String(length=100), nullable=False, unique=True),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("policy_version", sa.Integer()),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('running', 'passed', 'failed', 'fallback', 'cancelled')",
            name="ck_ai_run_status",
        ),
    )
    op.create_index(
        "uq_ai_policy_one_active",
        "ai_policy_versions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def _create_question_reserve_table() -> None:
    op.create_table(
        "question_reserve",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("stable_key", sa.String(length=80), nullable=False, unique=True),
        sa.Column("bank_version", sa.Integer(), nullable=False),
        sa.Column("concept_family", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.String(length=240), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("intimacy", sa.Boolean(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("option_icons", sa.JSON(), nullable=False),
        sa.Column("scale_low_label", sa.String(length=32)),
        sa.Column("scale_high_label", sa.String(length=32)),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_question_reserve_available",
        "question_reserve",
        ["intimacy", "consumed_at"],
    )


def _create_web_context_table() -> None:
    op.create_table(
        "web_context_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("base_url", sa.String(length=500), nullable=False, unique=True),
        sa.Column("hostname", sa.String(length=253), nullable=False),
        sa.Column("code_owned", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("added_by", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def _seed_web_context_sources() -> None:
    source_table = sa.table(
        "web_context_sources",
        sa.column("id", sa.Uuid()),
        sa.column("base_url", sa.String()),
        sa.column("hostname", sa.String()),
        sa.column("code_owned", sa.Boolean()),
        sa.column("enabled", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    for base_url, hostname in (
        ("https://www.un.org/en/observances", "www.un.org"),
        ("https://science.nasa.gov/skywatching", "science.nasa.gov"),
        ("https://www.loc.gov/collections", "www.loc.gov"),
        ("https://www.si.edu/spotlight", "www.si.edu"),
    ):
        op.bulk_insert(
            source_table,
            [
                {
                    "id": uuid4(),
                    "base_url": base_url,
                    "hostname": hostname,
                    "code_owned": True,
                    "enabled": True,
                    "created_at": datetime.now(UTC),
                }
            ],
        )


def downgrade() -> None:
    """Remove 1.2 quiz intelligence while preserving all earlier product state."""

    for table in (
        "web_context_sources",
        "question_reserve",
        "ai_runs",
        "ai_policy_versions",
        "question_concepts",
        "feedback_weekly_aggregates",
        "anonymous_question_reviews",
        "question_feedback_operations",
        "question_feedback",
        "quiz_feedback_rollout",
    ):
        op.drop_table(table)
    op.execute("DROP EXTENSION IF EXISTS vector")
