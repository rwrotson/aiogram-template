from unittest.mock import AsyncMock, create_autospec

import pytest
from clickhouse_connect.driver import AsyncClient
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from pydantic import SecretStr
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncConnection as SqlAlchemyConnection
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.config import (
    ClickHouseSettings,
    MongoDBSettings,
    PostgresOrmSettings,
    PostgresRawSettings,
    RedisSettings,
)
from app.infra.storage import clickhouse, mongodb, postgres_orm, postgres_raw, redis

# Driver-based mock specs detect adapter incompatibilities in the lowest-dependency CI job.


async def test_postgres_raw_client_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = create_autospec(AsyncConnection, instance=True)
    pool = create_autospec(AsyncConnectionPool, instance=True)
    pool.connection.return_value.__aenter__.return_value = connection
    created: dict[str, object] = {}

    def make_pool(**kwargs: object) -> object:
        created.update(kwargs)
        return pool

    monkeypatch.setattr(postgres_raw, "AsyncConnectionPool", make_pool)

    handle = await postgres_raw.create_handle(
        PostgresRawSettings(dsn=SecretStr("postgresql://localhost/test"), max_size=3)
    )
    assert created["conninfo"] == "postgresql://localhost/test"
    assert created["max_size"] == 3
    acquired = await handle.acquire()
    await handle.check()
    connection.execute.assert_awaited_once_with("SELECT 1")
    await handle.close()
    pool.close.assert_awaited_once()
    assert acquired is pool


async def test_postgres_orm_client_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = create_autospec(SqlAlchemyConnection, instance=True)
    engine = create_autospec(AsyncEngine, instance=True)
    engine.connect.return_value.__aenter__.return_value = connection
    factory = create_autospec(async_sessionmaker, instance=True)
    engine_kwargs: dict[str, object] = {}

    def make_engine(_dsn: str, **kwargs: object) -> object:
        engine_kwargs.update(kwargs)
        return engine

    monkeypatch.setattr(postgres_orm, "create_async_engine", make_engine)
    monkeypatch.setattr(postgres_orm, "async_sessionmaker", lambda *_args, **_kwargs: factory)

    handle = await postgres_orm.create_handle(
        PostgresOrmSettings(dsn=SecretStr("postgresql+psycopg://localhost/test"), pool_size=2)
    )
    assert engine_kwargs["pool_size"] == 2
    assert await handle.acquire() is factory
    await handle.check()
    connection.execute.assert_awaited_once()
    await handle.close()
    engine.dispose.assert_awaited_once()


async def test_mongodb_client_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    client = create_autospec(AsyncMongoClient, instance=True)
    client.admin = create_autospec(AsyncDatabase, instance=True)
    monkeypatch.setattr(mongodb, "AsyncMongoClient", lambda *_args, **_kwargs: client)

    handle = await mongodb.create_handle(MongoDBSettings(dsn=SecretStr("mongodb://localhost")))
    acquired = await handle.acquire()
    await handle.check()
    client.admin.command.assert_awaited_once_with("ping")
    await handle.close()
    client.close.assert_awaited_once()
    assert acquired is client


async def test_redis_client_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    client = create_autospec(Redis, instance=True)
    # redis-py declares commands as sync methods returning awaitables, so autospec cannot tell.
    client.ping = AsyncMock()
    monkeypatch.setattr("app.infra.storage.redis.Redis.from_url", lambda *_args, **_kwargs: client)

    handle = await redis.create_handle(RedisSettings(dsn=SecretStr("redis://localhost")))
    acquired = await handle.acquire()
    await handle.check()
    client.ping.assert_awaited_once()
    await handle.close()
    client.aclose.assert_awaited_once()
    assert acquired is client


async def test_clickhouse_connects_lazily_and_reconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    client = create_autospec(AsyncClient, instance=True)
    factory = AsyncMock(side_effect=[ConnectionError("down"), client])
    monkeypatch.setattr("app.infra.storage.clickhouse.clickhouse_connect.get_async_client", factory)
    handle = await clickhouse.create_handle(ClickHouseSettings(host="localhost"))
    await handle.close()
    factory.assert_not_awaited()

    with pytest.raises(ConnectionError):
        await handle.check()
    await handle.check()
    acquired = await handle.acquire()
    assert factory.await_count == 2
    client.command.assert_awaited_once_with("SELECT 1")
    await handle.close()
    client.close.assert_awaited_once()
    assert acquired is client
