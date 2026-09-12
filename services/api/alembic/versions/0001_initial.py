"""Create the original Little Orbit authentication and sharing schema.

Revision ID: 0001
Revises:
Create Date: 2026-09-10
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the fixed initial schema without importing mutable application models."""

    _create_accounts()
    _create_couples()
    _create_questions()
    _create_notes()
    _create_location_and_audit()


def _create_accounts() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email_normalized", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("is_adult", sa.Boolean(), nullable=False),
        sa.Column("accepted_terms_version", sa.String(24), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("suspended_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "one_use_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_one_use_token_hash", "one_use_tokens", ["token_hash"], unique=True)
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("authenticated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("admin_mfa_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_session_token_hash", "sessions", ["token_hash"], unique=True)
    op.create_table(
        "admin_mfa",
        sa.Column("account_id", sa.Uuid(), primary_key=True),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("recovery_hashes", sa.JSON(), nullable=False),
        sa.Column("enabled_at", sa.DateTime(timezone=True)),
        sa.Column("last_accepted_counter", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
    )


def _create_couples() -> None:
    op.create_table(
        "couples",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("anniversary_date", sa.Date()),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("proximity_threshold_m", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "couple_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True)),
        sa.Column("intimacy_enabled", sa.Boolean(), nullable=False),
        sa.Column("location_enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("couple_id", "account_id"),
    )
    op.create_index(
        "uq_active_couple_member_account",
        "couple_members",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("left_at IS NULL"),
    )
    op.create_table(
        "pair_codes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("creator_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("pending_partner_id", sa.Uuid()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pending_partner_id"], ["accounts.id"]),
    )
    op.create_index("ix_pair_code_hash", "pair_codes", ["code_hash"], unique=True)


def _create_questions() -> None:
    op.create_table(
        "questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("publish_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("prompt", sa.String(240), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("intimacy", sa.Boolean(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("normalized_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_questions_publish_date", "questions", ["publish_date"])
    op.create_index("ix_questions_normalized_hash", "questions", ["normalized_hash"])
    op.create_table(
        "quiz_answers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("question_id", "account_id"),
    )


def _create_notes() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision >= 0"),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notes_couple_id", "notes", ["couple_id"])
    op.create_table(
        "note_operations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("note_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("resulting_revision", sa.Integer(), nullable=False),
        sa.Column("edit", sa.JSON(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["note_id"], ["notes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["accounts.id"]),
        sa.UniqueConstraint("note_id", "operation_id"),
    )


def _create_location_and_audit() -> None:
    op.create_table(
        "location_samples",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sample_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("couple_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accuracy_m", sa.Float(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["couple_id"], ["couples.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("account_id", "sample_id"),
    )
    op.create_index("ix_location_samples_expires_at", "location_samples", ["expires_at"])
    op.create_table(
        "security_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid()),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["accounts.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_security_events_event_type", "security_events", ["event_type"])


def downgrade() -> None:
    """Drop the initial schema in reverse dependency order."""

    for table in (
        "security_events",
        "location_samples",
        "note_operations",
        "notes",
        "quiz_answers",
        "questions",
        "pair_codes",
        "couple_members",
        "admin_mfa",
        "sessions",
        "one_use_tokens",
        "couples",
        "accounts",
    ):
        op.drop_table(table)
