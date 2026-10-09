from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

from app.infra.storage.base import StorageHandle


def make_handle(
    client: object,
    check: Callable[[], Awaitable[None]] | None = None,
    close: Callable[[], Awaitable[None]] | None = None,
) -> StorageHandle:
    """Wrap a fake client with optional probe and cleanup callbacks."""
    return StorageHandle.of(client, check=check or AsyncMock(), close=close or AsyncMock())
