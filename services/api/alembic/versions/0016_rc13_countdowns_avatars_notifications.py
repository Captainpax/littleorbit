"""Add RC13 countdown timing, private reminders, assigned avatars, and alert kinds.

Revision ID: 0016
Revises: 0015
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply additive countdown fields and replace account photos with pair avatars."""

    op.add_column(
        "countdowns",
        sa.Column("timing_kind", sa.String(16), server_default="timed", nullable=False),
    )
    op.add_column("countdowns", sa.Column("occurs_on", sa.Date(), nullable=True))
    op.create_check_constraint(
        "ck_countdown_timing_kind", "countdowns", "timing_kind IN ('timed', 'all_day')"
    )
    _create_reminders()
    _replace_profile_photos()
    _expand_notification_kinds()


def _create_reminders() -> None:
    op.create_table(
        "countdown_reminders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("countdown_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("offset_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["countdown_id"], ["countdowns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("countdown_id", "account_id", "offset_minutes"),
        sa.CheckConstraint(
            "offset_minutes IN (0, 60, 1440, 10080)", name="ck_countdown_reminder_offset"
        ),
    )
    op.create_index("ix_countdown_reminders_countdown_id", "countdown_reminders", ["countdown_id"])
    op.create_index("ix_countdown_reminders_account_id", "countdown_reminders", ["account_id"])


def _replace_profile_photos() -> None:
    op.create_table(
        "relationship_avatars",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("subject_account_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("image_webp", sa.LargeBinary(), nullable=False),
        sa.Column("thumbnail_webp", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("thumbnail_sha256", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by_account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("couple_id", "subject_account_id"),
        sa.CheckConstraint(
            "subject_account_id <> assigned_by_account_id", name="ck_relationship_avatar_partner"
        ),
    )
    op.create_index("ix_relationship_avatars_couple_id", "relationship_avatars", ["couple_id"])
    op.create_index(
        "ix_relationship_avatars_subject_account_id",
        "relationship_avatars",
        ["subject_account_id"],
    )
    # The approved privacy migration deliberately clears every former self-uploaded image.
    op.drop_table("account_profile_photos")


def _expand_notification_kinds() -> None:
    op.drop_constraint("ck_notification_event_kind", "notification_events", type_="check")
    kinds = (
        "'smooch_received', 'note_editing', 'countdown_created', "
        "'countdown_rescheduled', 'quiz_available', 'quiz_partner_finished', "
        "'quiz_results_ready'"
    )
    op.create_check_constraint(
        "ck_notification_event_kind", "notification_events", f"kind IN ({kinds})"
    )


def downgrade() -> None:
    """Restore the prior schema without recreating intentionally cleared photo bytes."""

    op.drop_constraint("ck_notification_event_kind", "notification_events", type_="check")
    op.execute(
        "DELETE FROM notification_events "
        "WHERE kind NOT IN ('smooch_received', 'note_editing')"
    )
    op.create_check_constraint(
        "ck_notification_event_kind",
        "notification_events",
        "kind IN ('smooch_received', 'note_editing')",
    )
    op.create_table(
        "account_profile_photos",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("image_webp", sa.LargeBinary(), nullable=False),
        sa.Column("thumbnail_webp", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("thumbnail_sha256", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
    )
    op.drop_table("relationship_avatars")
    op.drop_table("countdown_reminders")
    op.drop_constraint("ck_countdown_timing_kind", "countdowns", type_="check")
    op.drop_column("countdowns", "occurs_on")
    op.drop_column("countdowns", "timing_kind")
