from pymongo import AsyncMongoClient

from app.config import MongoDBSettings
from app.infra.storage.base import StorageHandle


async def create_handle(settings: MongoDBSettings) -> StorageHandle:
    """Create a MongoDB client scoped to this event loop."""
    client: AsyncMongoClient[dict[str, object]] = AsyncMongoClient(
        settings.dsn.get_secret_value(),
        maxPoolSize=settings.max_pool_size,
        serverSelectionTimeoutMS=int(settings.server_selection_timeout * 1000),
    )

    async def check() -> None:
        await client.admin.command("ping")

    return StorageHandle.of(client, check=check, close=client.close)
