import asyncio

import pytest
from aiogram import Bot
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.redis import RedisEventIsolation, RedisStorage
from pydantic import SecretStr

from app.config import RedisSettings, Settings
from app.main import create_app

pytestmark = [pytest.mark.integration, pytest.mark.redis_integration]


async def test_redis_fsm_persists_data_and_expires_it(
    settings: Settings, bot: Bot, redis_dsn: str
) -> None:
    configured = settings.model_copy(
        update={"redis": RedisSettings(dsn=SecretStr(redis_dsn), fsm_ttl_seconds=1)}
    )
    application = create_app(configured, bot)
    await application.storage.open(configured)
    try:
        assert await application.storage.readiness() == {"redis": "ok"}
        storage = application.dispatcher.fsm.storage
        assert isinstance(storage, RedisStorage)
        key = StorageKey(bot_id=bot.id, chat_id=42, user_id=42)
        await storage.set_state(key, "Survey:language")
        await storage.set_data(key, {"language": "Python"})
        assert await storage.get_state(key) == "Survey:language"
        assert await storage.get_data(key) == {"language": "Python"}
        await asyncio.sleep(1.1)
        assert await storage.get_state(key) is None
        assert await storage.get_data(key) == {}
    finally:
        await application.stop()


async def test_redis_fsm_serializes_updates_for_one_user(
    settings: Settings, bot: Bot, redis_dsn: str
) -> None:
    configured = settings.model_copy(update={"redis": RedisSettings(dsn=SecretStr(redis_dsn))})
    application = create_app(configured, bot)
    isolation = application.dispatcher.fsm.events_isolation
    assert isinstance(isolation, RedisEventIsolation)
    key = StorageKey(bot_id=bot.id, chat_id=43, user_id=43)
    attempted = asyncio.Event()
    acquired = asyncio.Event()

    async def acquire_again() -> None:
        attempted.set()
        async with isolation.lock(key):
            acquired.set()

    try:
        async with isolation.lock(key):
            contender = asyncio.create_task(acquire_again())
            await attempted.wait()
            await asyncio.sleep(0.05)
            assert not acquired.is_set()
        await asyncio.wait_for(contender, timeout=2)
        assert acquired.is_set()
    finally:
        await application.stop()
