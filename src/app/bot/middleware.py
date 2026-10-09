import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from opentelemetry import trace

from app.core.metrics import UPDATE_DURATION, UPDATE_IN_PROGRESS, UPDATES


class UpdateMiddleware(BaseMiddleware):
    """Record bounded update telemetry and bind update IDs to logs."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[object]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> object:
        """Trace one update and record its outcome without user data in labels."""
        update_id = getattr(event, "update_id", None)
        update_type = getattr(event, "event_type", "unknown")
        tokens = structlog.contextvars.bind_contextvars(update_id=update_id)
        started = time.perf_counter()
        outcome = "ok"
        UPDATE_IN_PROGRESS.inc()
        try:
            with trace.get_tracer("app.bot").start_as_current_span("telegram.update"):
                return await handler(event, data)
        except Exception:
            outcome = "error"
            structlog.get_logger().exception("update_failed", update_type=update_type)
            raise
        finally:
            UPDATES.labels(update_type=update_type, outcome=outcome).inc()
            UPDATE_DURATION.labels(update_type=update_type).observe(time.perf_counter() - started)
            UPDATE_IN_PROGRESS.dec()
            structlog.contextvars.reset_contextvars(**tokens)
