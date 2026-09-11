"""Add curated content, release metadata, and non-secret runtime controls.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-10
"""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create privacy-safe owner-managed content and configuration records."""

    op.create_table(
        "curated_bank_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("stable_key", sa.String(48), nullable=False, unique=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("prompt", sa.String(240), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("intimacy", sa.Boolean(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["accounts.id"], ondelete="SET NULL"),
    )
    op.create_table(
        "apk_releases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version", sa.String(40), nullable=False, unique=True),
        sa.Column("apk_url", sa.Text(), nullable=False),
        sa.Column("github_release_url", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("minimum_android", sa.Integer(), nullable=False),
        sa.Column("release_notes", sa.String(4000), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["accounts.id"], ondelete="SET NULL"),
    )
    op.create_table(
        "runtime_settings",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["accounts.id"], ondelete="SET NULL"),
    )


def downgrade() -> None:
    """Remove owner-managed records."""

    op.drop_table("runtime_settings")
    op.drop_table("apk_releases")
    op.drop_table("curated_bank_questions")
