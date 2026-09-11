"""Add the encrypted SMTP outbox.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-10
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the outbox for databases initialized before email delivery landed."""

    op.execute("""
        CREATE TABLE IF NOT EXISTS mail_outbox (
            id UUID PRIMARY KEY,
            recipient VARCHAR(320) NOT NULL,
            subject VARCHAR(160) NOT NULL,
            encrypted_body TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TIMESTAMPTZ NOT NULL,
            delivered_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL
        )
    """)


def downgrade() -> None:
    """Remove the outbox table."""

    op.execute("DROP TABLE IF EXISTS mail_outbox")
