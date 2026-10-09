import os

import pytest

SERVICE_VARIABLES = {
    "postgres_integration": "APP_POSTGRES_ORM__DSN",
    "redis_integration": "APP_REDIS__DSN",
}


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip unconfigured services unless their integration tests were selected."""
    markexpr: str = config.option.markexpr
    for item in items:
        for marker, variable in SERVICE_VARIABLES.items():
            if item.get_closest_marker(marker) is None or os.environ.get(variable):
                continue
            if "integration" in markexpr and "not integration" not in markexpr:
                raise pytest.UsageError(f"{variable} is required to run {marker} tests")
            item.add_marker(pytest.mark.skip(reason=f"{variable} is required"))


@pytest.fixture(scope="session")
def postgres_dsn() -> str:
    """Capture the integration DSN before the test fixture clears APP_* variables."""
    return os.environ[SERVICE_VARIABLES["postgres_integration"]]


@pytest.fixture(scope="session")
def redis_dsn() -> str:
    """Capture the Redis DSN before the test fixture clears APP_* variables."""
    return os.environ[SERVICE_VARIABLES["redis_integration"]]
