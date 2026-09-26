"""Add one-use Big Orbit PIN and restricted bootstrap sessions.

Revision ID: 0031
Revises: 0030
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create terminal-issued PIN and privilege-separated setup state."""

    op.drop_constraint(
        "ck_admin_challenge_purpose", "admin_device_challenges", type_="check"
    )
    op.create_check_constraint(
        "ck_admin_challenge_purpose",
        "admin_device_challenges",
        "purpose IN ('enrollment', 'session', 'bootstrap')",
    )
    op.create_table(
        "admin_bootstrap_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pin_hash", sa.String(64), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "failed_attempts BETWEEN 0 AND 5", name="ck_bootstrap_pin_attempts"
        ),
    )
    op.create_index(
        "ix_bootstrap_credentials_expiry",
        "admin_bootstrap_credentials",
        ["expires_at"],
    )
    op.create_table(
        "admin_bootstrap_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "device_id",
            sa.Uuid(),
            sa.ForeignKey("admin_devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("mfa_required", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_bootstrap_sessions_expiry", "admin_bootstrap_sessions", ["expires_at"]
    )


def downgrade() -> None:
    """Remove bootstrap state and restore the earlier challenge vocabulary."""

    op.drop_table("admin_bootstrap_sessions")
    op.drop_table("admin_bootstrap_credentials")
    op.drop_constraint(
        "ck_admin_challenge_purpose", "admin_device_challenges", type_="check"
    )
    op.create_check_constraint(
        "ck_admin_challenge_purpose",
        "admin_device_challenges",
        "purpose IN ('enrollment', 'session')",
    )
