"""Allow account erasure to anonymize retained operational history.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Use database-enforced anonymization for references that must outlive an account."""

    op.drop_constraint(
        "pair_codes_pending_partner_id_fkey", "pair_codes", type_="foreignkey"
    )
    op.create_foreign_key(
        "pair_codes_pending_partner_id_fkey",
        "pair_codes",
        "accounts",
        ["pending_partner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("note_operations", "actor_id", existing_type=sa.Uuid(), nullable=True)
    op.drop_constraint("note_operations_actor_id_fkey", "note_operations", type_="foreignkey")
    op.create_foreign_key(
        "note_operations_actor_id_fkey",
        "note_operations",
        "accounts",
        ["actor_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Restore strict references after removing anonymized note-operation rows."""

    op.drop_constraint("note_operations_actor_id_fkey", "note_operations", type_="foreignkey")
    op.execute("DELETE FROM note_operations WHERE actor_id IS NULL")
    op.alter_column("note_operations", "actor_id", existing_type=sa.Uuid(), nullable=False)
    op.create_foreign_key(
        "note_operations_actor_id_fkey",
        "note_operations",
        "accounts",
        ["actor_id"],
        ["id"],
    )
    op.drop_constraint(
        "pair_codes_pending_partner_id_fkey", "pair_codes", type_="foreignkey"
    )
    op.create_foreign_key(
        "pair_codes_pending_partner_id_fkey",
        "pair_codes",
        "accounts",
        ["pending_partner_id"],
        ["id"],
    )
