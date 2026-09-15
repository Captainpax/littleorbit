"""Add durable daily together-time totals and correction notifications.

Revision ID: 0018
Revises: 0017
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create daily totals, backfill existing estimates, and add alert consent."""

    op.create_table(
        "together_days",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("estimated_seconds", sa.Integer(), nullable=False),
        sa.Column("corrected_seconds", sa.Integer()),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("corrected_by", sa.Uuid()),
        sa.Column("correction_reason", sa.String(length=240)),
        sa.Column("corrected_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["corrected_by"], ["accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("couple_id", "day"),
        sa.CheckConstraint(
            "estimated_seconds >= 0 AND estimated_seconds <= 86400",
            name="ck_together_day_estimated_bounds",
        ),
        sa.CheckConstraint(
            "corrected_seconds IS NULL OR "
            "(corrected_seconds >= 0 AND corrected_seconds <= 86400)",
            name="ck_together_day_corrected_bounds",
        ),
        sa.CheckConstraint("revision >= 0", name="ck_together_day_revision"),
    )
    op.create_index(
        "ix_together_days_couple_day", "together_days", ["couple_id", "day"]
    )
    _backfill_days()
    op.add_column(
        "notification_preferences",
        sa.Column(
            "together_time_enabled", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
    )
    _replace_notification_constraint(include_correction=True)


def _backfill_days() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT couple_id, (bucket_start AT TIME ZONE 'UTC')::date AS day, "
            "LEAST(86400, SUM(duration_seconds))::integer AS seconds "
            "FROM together_buckets GROUP BY couple_id, day"
        )
    )
    now = datetime.now(UTC)
    table = sa.table(
        "together_days",
        sa.column("id", sa.Uuid()),
        sa.column("couple_id", sa.Uuid()),
        sa.column("day", sa.Date()),
        sa.column("estimated_seconds", sa.Integer()),
        sa.column("revision", sa.Integer()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    values = [
        {
            "id": uuid4(),
            "couple_id": row.couple_id,
            "day": row.day,
            "estimated_seconds": row.seconds,
            "revision": 0,
            "updated_at": now,
        }
        for row in rows
    ]
    if values:
        op.bulk_insert(table, values)


def _replace_notification_constraint(*, include_correction: bool) -> None:
    op.drop_constraint("ck_notification_event_kind", "notification_events", type_="check")
    kinds = [
        "smooch_received",
        "note_editing",
        "countdown_created",
        "countdown_rescheduled",
        "quiz_available",
        "quiz_partner_finished",
        "quiz_results_ready",
    ]
    if include_correction:
        kinds.append("together_time_corrected")
    rendered = ", ".join(f"'{item}'" for item in kinds)
    op.create_check_constraint(
        "ck_notification_event_kind", "notification_events", f"kind IN ({rendered})"
    )


def downgrade() -> None:
    """Remove durable daily state after deleting unsupported alert rows."""

    op.execute("DELETE FROM notification_events WHERE kind = 'together_time_corrected'")
    _replace_notification_constraint(include_correction=False)
    op.drop_column("notification_preferences", "together_time_enabled")
    op.drop_index("ix_together_days_couple_day", table_name="together_days")
    op.drop_table("together_days")
