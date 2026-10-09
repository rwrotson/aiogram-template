import asyncio

import clickhouse_connect
from clickhouse_connect.driver import AsyncClient

from app.config import ClickHouseSettings
from app.infra.storage.base import StorageHandle


async def create_handle(settings: ClickHouseSettings) -> StorageHandle:
    """Defer network initialization so startup survives server outages."""
    client: AsyncClient | None = None
    connect_lock = asyncio.Lock()

    async def acquire() -> AsyncClient:
        nonlocal client
        async with connect_lock:
            if client is None:
                client = await clickhouse_connect.get_async_client(
                    host=settings.host,
                    port=settings.port,
                    username=settings.username,
                    password=settings.password.get_secret_value(),
                    database=settings.database,
                    secure=settings.secure,
                    connect_timeout=settings.connect_timeout,
                )
            return client

    async def check() -> None:
        await (await acquire()).command("SELECT 1")

    async def close() -> None:
        if client is not None:
            await client.close()

    return StorageHandle(acquire=acquire, check=check, close=close)
