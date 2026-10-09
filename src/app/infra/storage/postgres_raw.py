from psycopg_pool import AsyncConnectionPool

from app.config import PostgresRawSettings
from app.infra.storage.base import StorageHandle


async def create_handle(settings: PostgresRawSettings) -> StorageHandle:
    """Create a non-blocking PostgreSQL pool."""
    pool = AsyncConnectionPool(
        conninfo=settings.dsn.get_secret_value(),
        min_size=settings.min_size,
        max_size=settings.max_size,
        timeout=settings.connect_timeout,
        open=False,
    )
    await pool.open(wait=False)

    async def check() -> None:
        async with pool.connection(timeout=settings.connect_timeout) as connection:
            await connection.execute("SELECT 1")

    return StorageHandle.of(pool, check=check, close=pool.close)
