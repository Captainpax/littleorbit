"""Add themed quiz plans, reviewed RAG, and durable context snapshots.

Revision ID: 0030
Revises: 0029
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Install additive thematic intelligence without changing past quiz content."""

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    _extend_existing_records()
    _create_week_plans()
    _create_retrieval_state()
    _add_generation_provenance()
    _seed_context_source()


def _extend_existing_records() -> None:
    op.add_column(
        "question_concepts",
        sa.Column("depth", sa.String(16), nullable=False, server_default="reflective"),
    )
    op.add_column(
        "question_concepts",
        sa.Column("theme_role", sa.String(16), nullable=False, server_default="variety"),
    )
    op.add_column(
        "question_concepts",
        sa.Column("theme_tags", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "feedback_weekly_aggregates",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for _name, column in (
        ("concept_summary", sa.Column("concept_summary", sa.String(180), nullable=False, server_default="Reviewed reserve concept")),
        ("depth", sa.Column("depth", sa.String(16), nullable=False, server_default="reflective")),
        ("theme_tags", sa.Column("theme_tags", sa.JSON(), nullable=False, server_default="[]")),
        ("content_hash", sa.Column("content_hash", sa.String(64))),
        ("review_tier", sa.Column("review_tier", sa.String(24), nullable=False, server_default="legacy-reviewed")),
        ("last_used_on", sa.Column("last_used_on", sa.Date())),
    ):
        op.add_column("question_reserve", column)
    op.execute(
        "UPDATE question_reserve "
        "SET content_hash = encode(digest(convert_to(prompt, 'UTF8'), 'sha256'), 'hex') "
        "WHERE content_hash IS NULL"
    )
    op.alter_column("question_reserve", "content_hash", nullable=False)
    op.create_unique_constraint(
        "uq_question_reserve_content_hash", "question_reserve", ["content_hash"]
    )
    for _name, column in (
        ("concept_family", sa.Column("concept_family", sa.String(80), nullable=False, server_default="legacy")),
        ("concept_summary", sa.Column("concept_summary", sa.String(180), nullable=False, server_default="Legacy reviewed concept")),
        ("depth", sa.Column("depth", sa.String(16), nullable=False, server_default="reflective")),
        ("theme_tags", sa.Column("theme_tags", sa.JSON(), nullable=False, server_default="[]")),
    ):
        op.add_column("curated_bank_questions", column)
    op.execute(
        "UPDATE curated_bank_questions SET concept_family = stable_key "
        "WHERE concept_family = 'legacy'"
    )


def _create_week_plans() -> None:
    op.create_table(
        "quiz_week_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("locale", sa.String(24), nullable=False),
        sa.Column("arc_title", sa.String(80), nullable=False),
        sa.Column("arc_summary", sa.String(240), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.Integer()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("week_start", name="uq_quiz_week_plan_start"),
        sa.CheckConstraint(
            "status IN ('planned', 'published', 'failed')", name="ck_week_plan_status"
        ),
    )
    op.create_table(
        "quiz_day_themes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "week_plan_id",
            sa.Uuid(),
            sa.ForeignKey("quiz_week_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("day_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(80), nullable=False),
        sa.Column("summary", sa.String(240), nullable=False),
        sa.Column("observance", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("local_date", name="uq_quiz_day_theme_date"),
        sa.UniqueConstraint("week_plan_id", "day_index", name="uq_quiz_day_theme_index"),
        sa.CheckConstraint("day_index BETWEEN 0 AND 6", name="ck_quiz_day_theme_index"),
    )


def _create_retrieval_state() -> None:
    op.create_table(
        "ai_knowledge_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_key", sa.String(80), nullable=False),
        sa.Column("document_path", sa.String(240), nullable=False),
        sa.Column("revision_digest", sa.String(64), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("body", sa.String(2400), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("embedding_model", sa.String(120), nullable=False),
        sa.Column("embedding_digest", sa.String(80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "document_key", "revision_digest", "chunk_index", name="uq_ai_knowledge_chunk"
        ),
    )
    op.create_index(
        "ix_ai_knowledge_active", "ai_knowledge_chunks", ["document_key", "active"]
    )
    op.create_table(
        "web_context_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_key", sa.String(80), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("excerpt", sa.String(4000), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "source_key", "content_digest", name="uq_web_context_snapshot_digest"
        ),
    )
    op.create_index(
        "ix_web_context_snapshots_fresh",
        "web_context_snapshots",
        ["source_key", "expires_at"],
    )
    op.create_table(
        "ai_learning_cursors",
        sa.Column("name", sa.String(40), primary_key=True),
        sa.Column("feedback_updated_through", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=False),
    )


def _add_generation_provenance() -> None:
    op.add_column(
        "generation_batches",
        sa.Column(
            "day_theme_id",
            sa.Uuid(),
            sa.ForeignKey("quiz_day_themes.id", ondelete="SET NULL"),
        ),
    )
    op.add_column("generation_batches", sa.Column("knowledge_revision", sa.String(64)))
    op.add_column("generation_batches", sa.Column("context_digest", sa.String(64)))


def _seed_context_source() -> None:
    op.execute(
        "INSERT INTO web_context_sources "
        "(id, base_url, hostname, code_owned, enabled, created_at) VALUES "
        "(gen_random_uuid(), "
        "'https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/', "
        "'www.opm.gov', TRUE, TRUE, CURRENT_TIMESTAMP) ON CONFLICT (base_url) DO NOTHING"
    )


def downgrade() -> None:
    """Remove 1.3 intelligence state while preserving older quiz records."""

    op.drop_column("generation_batches", "context_digest")
    op.drop_column("generation_batches", "knowledge_revision")
    op.drop_column("generation_batches", "day_theme_id")
    for table in (
        "ai_learning_cursors",
        "web_context_snapshots",
        "ai_knowledge_chunks",
        "quiz_day_themes",
        "quiz_week_plans",
    ):
        op.drop_table(table)
    for column in ("theme_tags", "depth", "concept_summary", "concept_family"):
        op.drop_column("curated_bank_questions", column)
    op.drop_constraint("uq_question_reserve_content_hash", "question_reserve", type_="unique")
    for column in (
        "last_used_on",
        "review_tier",
        "content_hash",
        "theme_tags",
        "depth",
        "concept_summary",
    ):
        op.drop_column("question_reserve", column)
    op.drop_column("feedback_weekly_aggregates", "updated_at")
    for column in ("theme_tags", "theme_role", "depth"):
        op.drop_column("question_concepts", column)
