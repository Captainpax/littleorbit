"""Test-only environment guards shared by the API suite."""

import os


def _select_explicit_test_database() -> None:
    """Make the destructive PostgreSQL fixtures use their explicitly named URL."""

    test_url = os.getenv("LITTLE_ORBIT_TEST_DATABASE_URL")
    if not test_url:
        return
    if not test_url.startswith("postgresql+asyncpg://"):
        raise RuntimeError("The isolated test database must use postgresql+asyncpg")
    os.environ["DATABASE_URL"] = test_url


_select_explicit_test_database()
