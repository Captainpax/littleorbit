"""Add an indexed PostgreSQL trigram gate for global question wording.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable trigram comparison and index public question prompts."""

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "ix_questions_prompt_trgm",
        "questions",
        ["prompt"],
        postgresql_using="gin",
        postgresql_ops={"prompt": "gin_trgm_ops"},
    )


def downgrade() -> None:
    """Remove the app-owned index while retaining the shared extension."""

    op.drop_index("ix_questions_prompt_trgm", table_name="questions")
