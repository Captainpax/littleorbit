"""Add the content-free, lease-fenced GPU work queue.

Revision ID: 0032
Revises: 0031
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create content-free scheduling state and align the admin job vocabulary."""

    op.create_table(
        "ai_work_queue",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_token", sa.Uuid()),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "kind IN ('weekly_learning', 'weekly_generation', "
            "'admin_learning', 'admin_generation', 'admin_regeneration')",
            name="ck_ai_work_kind",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_ai_work_attempt_count"),
        sa.CheckConstraint(
            "lease_token IS NULL OR heartbeat_at IS NOT NULL",
            name="ck_ai_work_lease_heartbeat",
        ),
    )
    op.create_index(
        "ix_ai_work_due", "ai_work_queue", ["next_attempt_at", "scheduled_at"]
    )
    op.create_index(
        "uq_ai_work_weekly_schedule",
        "ai_work_queue",
        ["kind", "scheduled_at"],
        unique=True,
        postgresql_where=sa.text(
            "kind IN ('weekly_learning', 'weekly_generation')"
        ),
    )
    op.drop_constraint("ck_admin_job_kind", "admin_job_requests", type_="check")
    op.create_check_constraint(
        "ck_admin_job_kind",
        "admin_job_requests",
        "kind IN ('learn_quizzes', 'generate_quizzes', 'regenerate_quizzes', "
        "'backup', 'test_restore')",
    )


def downgrade() -> None:
    """Remove GPU scheduling state and restore the earlier admin vocabulary."""

    op.drop_constraint("ck_admin_job_kind", "admin_job_requests", type_="check")
    op.execute(
        sa.text(
            "UPDATE admin_job_requests "
            "SET kind = 'generate_quizzes', "
            "status = CASE WHEN status IN ('pending', 'running') "
            "THEN 'cancelled' ELSE status END, "
            "finished_at = CASE WHEN status IN ('pending', 'running') "
            "THEN COALESCE(finished_at, CURRENT_TIMESTAMP) ELSE finished_at END "
            "WHERE kind = 'regenerate_quizzes'"
        )
    )
    op.create_check_constraint(
        "ck_admin_job_kind",
        "admin_job_requests",
        "kind IN ('learn_quizzes', 'generate_quizzes', 'backup', 'test_restore')",
    )
    op.drop_table("ai_work_queue")
