import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING, cast

from app.config import Settings
from app.core.metrics import STORAGE_AVAILABLE

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from clickhouse_connect.driver import AsyncClient
    from psycopg_pool import AsyncConnectionPool
    from pymongo import AsyncMongoClient
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class StorageNotConfiguredError(RuntimeError):
    """Indicate that a requested storage backend has no configuration."""

    def __init__(self, backend: str) -> None:
        self.backend = backend
        super().__init__(f"{backend} is not configured")


class StorageUnavailableError(RuntimeError):
    """Indicate that a configured storage backend cannot be reached."""

    def __init__(self, backend: str) -> None:
        self.backend = backend
        super().__init__(f"{backend} is unavailable")


@dataclass(frozen=True, slots=True)
class StorageHandle:
    """A client and its backend-specific lifecycle operations."""

    acquire: Callable[[], Awaitable[object]]
    check: Callable[[], Awaitable[None]]
    close: Callable[[], Awaitable[None]]

    @classmethod
    def of(
        cls,
        client: object,
        check: Callable[[], Awaitable[None]],
        close: Callable[[], Awaitable[None]],
    ) -> StorageHandle:
        """Wrap a client that is ready as soon as it is constructed."""

        async def acquire() -> object:
            return client

        return cls(acquire=acquire, check=check, close=close)


@dataclass(frozen=True, slots=True)
class BackendSpec[T]:
    """Identify an optional backend and its client factory."""

    name: str
    extra: str
    module: str
    optional_imports: frozenset[str]


POSTGRES_RAW: BackendSpec[AsyncConnectionPool] = BackendSpec(
    "postgres_raw",
    "postgres-raw",
    "app.infra.storage.postgres_raw",
    frozenset({"psycopg", "psycopg_pool"}),
)
POSTGRES_ORM: BackendSpec[async_sessionmaker[AsyncSession]] = BackendSpec(
    "postgres_orm",
    "postgres-orm",
    "app.infra.storage.postgres_orm",
    frozenset({"sqlalchemy", "psycopg"}),
)
CLICKHOUSE: BackendSpec[AsyncClient] = BackendSpec(
    "clickhouse", "clickhouse", "app.infra.storage.clickhouse", frozenset({"clickhouse_connect"})
)
MONGODB: BackendSpec[AsyncMongoClient[dict[str, object]]] = BackendSpec(
    "mongodb", "mongodb", "app.infra.storage.mongodb", frozenset({"pymongo"})
)
REDIS: BackendSpec[Redis] = BackendSpec(
    "redis", "redis", "app.infra.storage.redis", frozenset({"redis"})
)

BACKENDS: tuple[BackendSpec[object], ...] = (POSTGRES_RAW, POSTGRES_ORM, CLICKHOUSE, MONGODB, REDIS)


class StorageManager:
    """Own configured clients without requiring any backend by default."""

    def __init__(self, readiness_timeout: float = 2.0, readiness_cache_ttl: float = 0.0) -> None:
        self.handles: dict[str, StorageHandle] = {}
        self._cleanup = AsyncExitStack()
        self._readiness_timeout = readiness_timeout
        self._readiness_cache_ttl = readiness_cache_ttl
        self._readiness_lock = asyncio.Lock()
        self._readiness: dict[str, str] | None = None
        self._readiness_at = 0.0

    async def get[T](self, spec: BackendSpec[T]) -> T:
        """Return the client for `spec`, connecting lazily where the backend needs it."""
        handle = self.handles.get(spec.name)
        if handle is None:
            raise StorageNotConfiguredError(spec.name)
        try:
            client = await handle.acquire()
        except Exception as exc:
            raise StorageUnavailableError(spec.name) from exc
        return cast("T", client)

    async def _close_handle(self, name: str, handle: StorageHandle) -> None:
        try:
            await handle.close()
        except Exception:
            logger.exception("Failed to close storage backend %s", name)

    async def open(self, settings: Settings) -> None:
        """Create configured clients. Constructors do not require live servers."""
        try:
            for spec in BACKENDS:
                backend_settings = getattr(settings, spec.name)
                if backend_settings is None:
                    continue
                try:
                    module = import_module(spec.module)
                    handle = await module.create_handle(backend_settings)
                except ModuleNotFoundError as exc:
                    if exc.name not in spec.optional_imports:
                        raise
                    message = f"Install the '{spec.extra}' extra to configure {spec.name}"
                    raise RuntimeError(message) from exc
                self._cleanup.push_async_callback(self._close_handle, spec.name, handle)
                self.handles[spec.name] = handle
                STORAGE_AVAILABLE.labels(backend=spec.name).set(0)
        except Exception:
            await self.close()
            raise

    async def _probe(self, name: str, handle: StorageHandle) -> tuple[str, str]:
        try:
            async with asyncio.timeout(self._readiness_timeout):
                await handle.check()
        except Exception:  # noqa: BLE001 - all probe failures mean unavailable
            STORAGE_AVAILABLE.labels(backend=name).set(0)
            return name, "unavailable"
        STORAGE_AVAILABLE.labels(backend=name).set(1)
        return name, "ok"

    async def readiness(self) -> dict[str, str]:
        """Probe configured backends concurrently, reusing a recent result."""
        async with self._readiness_lock:
            now = time.monotonic()
            fresh = now - self._readiness_at < self._readiness_cache_ttl
            if self._readiness is None or not fresh:
                results = await asyncio.gather(
                    *(self._probe(name, handle) for name, handle in self.handles.items())
                )
                self._readiness = dict(results)
                self._readiness_at = now
            return dict(self._readiness)

    async def close(self) -> None:
        """Release every initialized backend."""
        try:
            await self._cleanup.aclose()
        finally:
            for name in self.handles:
                STORAGE_AVAILABLE.remove(name)
            self.handles.clear()
            self._readiness = None
            self._cleanup = AsyncExitStack()
