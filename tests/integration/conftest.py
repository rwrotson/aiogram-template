import os

import pytest

SERVICE_VARIABLES = {
    "postgres_integration": "APP_POSTGRES_ORM__DSN",
    "redis_integration": "APP_REDIS__DSN",
}


def _require(marker: str) -> str:
    variable = SERVICE_VARIABLES[marker]
    dsn = os.environ.get(variable)
    if not dsn:
        pytest.fail(f"{variable} is required to run {marker} tests", pytrace=False)
    return dsn


@pytest.fixture(scope="session")
def postgres_dsn() -> str:
    """Capture the PostgreSQL DSN before the test fixture clears APP_* variables."""
    return _require("postgres_integration")


@pytest.fixture(scope="session")
def redis_dsn() -> str:
    """Capture the Redis DSN before the test fixture clears APP_* variables."""
    return _require("redis_integration")
