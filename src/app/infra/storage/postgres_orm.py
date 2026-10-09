from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import PostgresOrmSettings
from app.infra.storage.base import StorageHandle


async def create_handle(settings: PostgresOrmSettings) -> StorageHandle:
    """Create an engine and per-request session factory."""
    engine = create_async_engine(
        settings.dsn.get_secret_value(),
        pool_pre_ping=True,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_timeout=settings.pool_timeout,
        connect_args={"connect_timeout": settings.connect_timeout},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def check() -> None:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    return StorageHandle.of(factory, check=check, close=engine.dispose)
