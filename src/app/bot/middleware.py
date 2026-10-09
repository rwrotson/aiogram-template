import asyncio
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

    def __init__(self) -> None:
        self._active: set[asyncio.Task[object]] = set()
        self._idle = asyncio.Event()
        self._idle.set()

    @property
    def active_count(self) -> int:
        """Return the number of updates still being handled."""
        return len(self._active)

    async def drain(self, grace_seconds: float) -> None:
        """Wait for active updates, then cancel those that outlive the grace period."""
        try:
            await asyncio.wait_for(self._idle.wait(), timeout=grace_seconds)
        except TimeoutError:
            active = set(self._active)
            structlog.get_logger().warning("updates_grace_expired", count=len(active))
            for task in active:
                task.cancel()
            if active:
                _, pending = await asyncio.wait(active, timeout=2)
                if pending:
                    structlog.get_logger().warning("updates_did_not_stop", count=len(pending))

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[object]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> object:
        """Trace one update and record its outcome without user data in labels."""
        update_id = getattr(event, "update_id", None)
        update_type = getattr(event, "event_type", "unknown")
        task = asyncio.current_task()
        if task is not None:
            self._active.add(task)
            self._idle.clear()
        tokens = structlog.contextvars.bind_contextvars(update_id=update_id)
        started = time.perf_counter()
        outcome = "ok"
        UPDATE_IN_PROGRESS.inc()
        try:
            with trace.get_tracer("app.bot").start_as_current_span("telegram.update"):
                return await handler(event, data)
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except Exception:
            outcome = "error"
            structlog.get_logger().exception("update_failed", update_type=update_type)
            raise
        finally:
            UPDATES.labels(update_type=update_type, outcome=outcome).inc()
            UPDATE_DURATION.labels(update_type=update_type).observe(time.perf_counter() - started)
            UPDATE_IN_PROGRESS.dec()
            structlog.contextvars.reset_contextvars(**tokens)
            if task is not None:
                self._active.discard(task)
                if not self._active:
                    self._idle.set()
