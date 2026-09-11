"""Add monotonic, verifiable Android release metadata.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PACKAGE = "com.littleorbit.mobile"
SIGNER = "43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337"


def upgrade() -> None:
    """Add updater identity fields and backfill the two known signed candidates."""

    op.add_column("apk_releases", sa.Column("version_code", sa.Integer(), nullable=True))
    op.add_column("apk_releases", sa.Column("size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("apk_releases", sa.Column("package_name", sa.String(160), nullable=True))
    op.add_column("apk_releases", sa.Column("signer_sha256", sa.String(64), nullable=True))
    op.add_column(
        "apk_releases", sa.Column("minimum_supported_version_code", sa.Integer(), nullable=True)
    )
    op.add_column(
        "apk_releases", sa.Column("required_after", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(
        sa.text(
            """
            UPDATE apk_releases
            SET version_code = CASE version
                    WHEN '1.0.0-rc.1' THEN 1
                    WHEN '1.0.0-rc.2' THEN 2
                END,
                size_bytes = CASE version
                    WHEN '1.0.0-rc.1' THEN 15209575
                    WHEN '1.0.0-rc.2' THEN 15210947
                END,
                package_name = :package,
                signer_sha256 = :signer,
                minimum_supported_version_code = 1
            WHERE version IN ('1.0.0-rc.1', '1.0.0-rc.2')
            """
        ).bindparams(package=PACKAGE, signer=SIGNER)
    )
    op.create_unique_constraint("uq_apk_releases_version_code", "apk_releases", ["version_code"])
    op.create_check_constraint(
        "ck_apk_releases_version_code_positive",
        "apk_releases",
        "version_code IS NULL OR version_code > 0",
    )
    op.create_check_constraint(
        "ck_apk_releases_size_positive", "apk_releases", "size_bytes IS NULL OR size_bytes > 0"
    )
    op.create_check_constraint(
        "ck_apk_releases_floor_valid",
        "apk_releases",
        "minimum_supported_version_code IS NULL OR "
        "minimum_supported_version_code BETWEEN 1 AND version_code",
    )


def downgrade() -> None:
    """Remove updater-specific release metadata."""

    op.drop_constraint("ck_apk_releases_floor_valid", "apk_releases", type_="check")
    op.drop_constraint("ck_apk_releases_size_positive", "apk_releases", type_="check")
    op.drop_constraint("ck_apk_releases_version_code_positive", "apk_releases", type_="check")
    op.drop_constraint("uq_apk_releases_version_code", "apk_releases", type_="unique")
    for name in (
        "required_after",
        "minimum_supported_version_code",
        "signer_sha256",
        "package_name",
        "size_bytes",
        "version_code",
    ):
        op.drop_column("apk_releases", name)
