"""Create the initial Little Orbit schema.

Revision ID: 0001
Revises:
Create Date: 2026-09-10
"""

from alembic import op
from little_orbit_api import models  # noqa: F401
from little_orbit_api.database import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables represented by the accepted 1.0 initial model."""

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Drop the initial schema in reverse dependency order."""

    Base.metadata.drop_all(bind=op.get_bind())
