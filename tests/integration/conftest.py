import os

import pytest

DSN_VARIABLE = "APP_POSTGRES_ORM__DSN"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration tests without a database, unless they were explicitly selected."""
    if os.environ.get(DSN_VARIABLE):
        return
    markexpr: str = config.option.markexpr
    if "integration" in markexpr and "not integration" not in markexpr:
        raise pytest.UsageError(f"{DSN_VARIABLE} is required to run integration tests")
    skip = pytest.mark.skip(reason=f"{DSN_VARIABLE} is required")
    for item in items:
        if item.get_closest_marker("integration"):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def postgres_dsn() -> str:
    """Capture the integration DSN before the test fixture clears APP_* variables."""
    return os.environ[DSN_VARIABLE]
