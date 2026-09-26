"""Add self-hosted, per-device notification delivery.

Revision ID: 0015
Revises: 0014
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create preferences, installations, short-lived events, and acknowledgements."""

    _create_preferences()
    _create_devices()
    _create_events()
    _create_deliveries()
    _backfill_pending_smooches()


def _create_preferences() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("master_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("smooches_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("note_editing_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("daily_quiz_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("countdowns_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("weekly_summary_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
    )


def _create_devices() -> None:
    op.create_table(
        "notification_devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("app_version_code", sa.Integer(), nullable=False),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "device_id"),
    )
    op.create_index(
        "ix_notification_device_active",
        "notification_devices",
        ["account_id", "last_seen_at", "disabled_at"],
    )


def _create_events() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid()),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("dedupe_key", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("legacy_consumed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["recipient_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipient_id", "dedupe_key"),
        sa.CheckConstraint(
            "kind IN ('smooch_received', 'note_editing')", name="ck_notification_event_kind"
        ),
    )
    op.create_index(
        "ix_notification_event_pending",
        "notification_events",
        ["recipient_id", "expires_at", "created_at"],
    )


def _create_deliveries() -> None:
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("displayed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["event_id"], ["notification_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id"], ["notification_devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "device_id"),
    )
    op.create_index(
        "ix_notification_delivery_pending",
        "notification_deliveries",
        ["device_id", "displayed_at"],
    )


def _backfill_pending_smooches() -> None:
    op.execute(
        sa.text("""
        INSERT INTO notification_events (
            id, recipient_id, couple_id, actor_id, kind, source_id,
            dedupe_key, created_at, expires_at, legacy_consumed_at
        )
        SELECT id, recipient_id, couple_id, sender_id, 'smooch_received', id,
               'smooch:' || id::text, sent_at, sent_at + interval '24 hours', NULL
        FROM smooches
        WHERE delivered_at IS NULL
          AND recipient_id IS NOT NULL
          AND sent_at > now() - interval '24 hours'
        ON CONFLICT DO NOTHING
    """)
    )


def downgrade() -> None:
    """Remove the RC12.1 notification ledger."""

    op.drop_table("notification_deliveries")
    op.drop_index("ix_notification_event_pending", table_name="notification_events")
    op.drop_table("notification_events")
    op.drop_index("ix_notification_device_active", table_name="notification_devices")
    op.drop_table("notification_devices")
    op.drop_table("notification_preferences")
