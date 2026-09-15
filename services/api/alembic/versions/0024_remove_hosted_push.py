"""Remove hosted notification transport addressing.

Revision ID: 0024
Revises: 0023
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Delete every server-side address and delivery-attempt field."""

    op.drop_index("uq_notification_device_push_hash", table_name="notification_devices")
    for column in (
        "push_token_invalidated_at",
        "push_failure_count",
        "push_last_success_at",
        "push_last_attempt_at",
        "push_token_refreshed_at",
        "push_token_hash",
        "push_token_encrypted",
    ):
        op.drop_column("notification_devices", column)


def downgrade() -> None:
    """Restore the retired columns only for a controlled rollback to RC14."""

    op.add_column("notification_devices", sa.Column("push_token_encrypted", sa.Text()))
    op.add_column(
        "notification_devices", sa.Column("push_token_hash", sa.String(length=64))
    )
    op.add_column(
        "notification_devices", sa.Column("push_token_refreshed_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "notification_devices", sa.Column("push_last_attempt_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "notification_devices", sa.Column("push_last_success_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "notification_devices",
        sa.Column("push_failure_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "notification_devices",
        sa.Column("push_token_invalidated_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "uq_notification_device_push_hash",
        "notification_devices",
        ["push_token_hash"],
        unique=True,
        postgresql_where=sa.text("push_token_hash IS NOT NULL"),
    )
