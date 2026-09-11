"""Scope generated-question uniqueness to a publication date.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-10
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Permit audited bank reuse while preventing duplicate questions on one day."""

    op.execute(
        "ALTER TABLE questions DROP CONSTRAINT IF EXISTS questions_normalized_hash_key"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_questions_date_normalized_hash'
            ) THEN
                ALTER TABLE questions
                ADD CONSTRAINT uq_questions_date_normalized_hash
                UNIQUE (publish_date, normalized_hash);
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    """Restore the original global uniqueness rule when stored rows permit it."""

    op.execute(
        "ALTER TABLE questions DROP CONSTRAINT IF EXISTS uq_questions_date_normalized_hash"
    )
    op.create_unique_constraint(
        "questions_normalized_hash_key", "questions", ["normalized_hash"]
    )
