from redis.asyncio import Redis

from app.config import RedisSettings
from app.infra.storage.base import StorageHandle


async def create_handle(settings: RedisSettings) -> StorageHandle:
    """Create an async Redis connection pool."""
    client = Redis.from_url(
        settings.dsn.get_secret_value(),
        max_connections=settings.max_connections,
        socket_timeout=settings.socket_timeout,
        socket_connect_timeout=settings.socket_connect_timeout,
    )

    async def check() -> None:
        await client.ping()

    return StorageHandle.of(client, check=check, close=client.aclose)
