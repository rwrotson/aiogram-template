import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from prometheus_client import Counter, Gauge, Histogram

UPDATES = Counter(
    "app_telegram_updates_total",
    "Telegram updates by type and outcome",
    ["update_type", "outcome"],
)
UPDATE_DURATION = Histogram(
    "app_telegram_update_duration_seconds", "Telegram update handling duration", ["update_type"]
)
UPDATE_IN_PROGRESS = Gauge(
    "app_telegram_updates_in_progress", "Telegram updates currently being handled"
)
STORAGE_AVAILABLE = Gauge(
    "app_storage_available", "Availability of a configured storage backend", ["backend"]
)
DATABASE_OPERATIONS = Counter(
    "app_database_operations_total",
    "Database operations by backend, operation and result",
    ["backend", "operation", "result"],
)
DATABASE_DURATION = Histogram(
    "app_database_operation_duration_seconds",
    "Database operation duration by backend and operation",
    ["backend", "operation"],
)


@asynccontextmanager
async def observe_database_operation(backend: str, operation: str) -> AsyncIterator[None]:
    """Record an operation's duration and success or failure."""
    started = time.perf_counter()
    result = "ok"
    try:
        yield
    except Exception:
        result = "error"
        raise
    finally:
        DATABASE_OPERATIONS.labels(backend=backend, operation=operation, result=result).inc()
        DATABASE_DURATION.labels(backend=backend, operation=operation).observe(
            time.perf_counter() - started
        )
