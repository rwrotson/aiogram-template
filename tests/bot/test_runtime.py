import asyncio
from collections.abc import Callable
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.fsm.storage.redis import RedisEventIsolation, RedisStorage
from aiohttp import ClientSession
from pydantic import SecretStr

from app import main
from app.config import RedisSettings, Settings
from app.main import COMMANDS, BotApplication, create_app
from tests.conftest import free_port
from tests.fakes import make_handle


async def wait_registered(application: BotApplication) -> None:
    """Wait briefly for background Telegram registration."""
    for _ in range(100):
        if application._registered:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Telegram setup did not complete")


async def test_polling_serves_health_and_stops_cleanly(
    settings: Settings, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = create_app(settings, bot)
    pending = asyncio.Event()

    async def wait_for_stop(*_args: object, **_kwargs: object) -> None:
        await pending.wait()

    monkeypatch.setattr(
        application.dispatcher, "start_polling", AsyncMock(side_effect=wait_for_stop)
    )
    await application.start()
    try:
        await wait_registered(application)
        async with ClientSession() as session:
            url = f"http://127.0.0.1:{settings.http_port}"
            async with session.get(f"{url}/live") as response:
                assert response.status == 200
            async with session.get(f"{url}/ready") as response:
                assert response.status == 200
                assert (await response.json())["dependencies"] == {
                    "telegram": "ok",
                    "updates": "ok",
                }
            async with session.get(f"{url}/metrics") as response:
                assert response.status == 200
                assert "app_telegram_updates_total" in await response.text()
        cast("AsyncMock", bot.delete_webhook).assert_awaited_once_with(drop_pending_updates=False)
        cast("AsyncMock", bot.set_my_commands).assert_awaited_once_with(COMMANDS)
    finally:
        await application.stop()
    cast("AsyncMock", bot.session.close).assert_awaited_once()


async def test_webhook_requires_secret_and_processes_before_ack(
    settings: Settings, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = settings.model_copy(
        update={
            "update_mode": "webhook",
            "webhook_url": "https://example.com/telegram/hook",
            "webhook_secret": SecretStr("webhook-secret"),
        }
    )
    application = create_app(settings, bot)
    feed = AsyncMock(return_value=None)
    monkeypatch.setattr(application.dispatcher, "feed_update", feed)

    async def inspect_shutdown(**_kwargs: object) -> None:
        assert cast("AsyncMock", bot.session.close).await_count == 0

    application.dispatcher.shutdown.register(inspect_shutdown)
    await application.start()
    try:
        await wait_registered(application)
        url = f"http://127.0.0.1:{settings.http_port}/telegram/hook"
        async with ClientSession() as session:
            async with session.post(url, json={"update_id": 1}) as response:
                assert response.status == 401
            async with session.post(
                url,
                json={"update_id": 1},
                headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
            ) as response:
                assert response.status == 200
        feed.assert_awaited_once()
        feed.side_effect = RuntimeError("handler failed")
        async with (
            ClientSession() as session,
            session.post(
                url,
                json={"update_id": 2},
                headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
            ) as response,
        ):
            assert response.status == 500
        set_webhook = cast("AsyncMock", bot.set_webhook)
        set_webhook.assert_awaited_once()
        assert set_webhook.await_args is not None
        assert set_webhook.await_args.kwargs["drop_pending_updates"] is False
    finally:
        await application.stop()
    cast("AsyncMock", bot.session.close).assert_awaited_once()


async def test_unavailable_telegram_marks_ready_unavailable(settings: Settings, bot: Bot) -> None:
    cast("AsyncMock", bot.get_me).side_effect = ConnectionError("down")
    cast("AsyncMock", bot.set_my_commands).side_effect = ConnectionError("down")
    application = create_app(settings, bot)
    await application.start()
    try:
        async with (
            ClientSession() as session,
            session.get(f"http://127.0.0.1:{settings.http_port}/ready") as response,
        ):
            assert response.status == 503
            assert (await response.json())["dependencies"]["telegram"] == "unavailable"
    finally:
        await application.stop()


def test_fsm_uses_memory_without_redis(settings: Settings, bot: Bot) -> None:
    fsm = create_app(settings, bot).dispatcher.fsm
    assert isinstance(fsm.storage, MemoryStorage)
    assert isinstance(fsm.events_isolation, SimpleEventIsolation)


def test_fsm_uses_redis_when_configured(settings: Settings, bot: Bot) -> None:
    configured = settings.model_copy(
        update={
            "redis": RedisSettings(dsn=SecretStr("redis://localhost/0")),
            "http_port": free_port(),
        }
    )
    fsm = create_app(configured, bot).dispatcher.fsm
    assert isinstance(fsm.storage, RedisStorage)
    assert isinstance(fsm.events_isolation, RedisEventIsolation)
    assert fsm.events_isolation.redis is fsm.storage.redis


async def test_polling_owns_dispatcher_lifecycle_once(
    settings: Settings, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = create_app(settings, bot)
    started = asyncio.Event()
    events: list[str] = []

    async def startup(**_kwargs: object) -> None:
        events.append("startup")
        started.set()

    async def shutdown(**_kwargs: object) -> None:
        events.append("shutdown")

    application.dispatcher.startup.register(startup)
    application.dispatcher.shutdown.register(shutdown)

    async def wait_for_stop(*_args: object, **_kwargs: object) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(application.dispatcher, "_polling", wait_for_stop)
    await application.start()
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        assert events == ["startup"]
    finally:
        await application.stop()
    assert events == ["startup", "shutdown"]


async def test_registration_retries_without_stopping_http(
    settings: Settings, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    cast("AsyncMock", bot.set_my_commands).side_effect = [ConnectionError("down"), True]
    monkeypatch.setattr(main, "RETRY_DELAY", 0.01)
    application = create_app(settings, bot)
    pending = asyncio.Event()

    async def wait_for_stop(*_args: object, **_kwargs: object) -> None:
        await pending.wait()

    monkeypatch.setattr(application.dispatcher, "start_polling", wait_for_stop)
    await application.start()
    try:
        await wait_registered(application)
        assert cast("AsyncMock", bot.set_my_commands).await_count == 2
        assert cast("AsyncMock", bot.delete_webhook).await_count == 2
    finally:
        await application.stop()


async def test_ready_reports_configured_storage_outage(
    settings: Settings, bot: Bot, fake_backends: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def unavailable() -> None:
        raise ConnectionError("down")

    fake_backends.return_value = make_handle(object(), check=unavailable)
    configured = settings.model_copy(
        update={"redis": RedisSettings(dsn=SecretStr("redis://localhost/0"))}
    )
    application = create_app(configured, bot)
    pending = asyncio.Event()

    async def wait_for_stop(*_args: object, **_kwargs: object) -> None:
        await pending.wait()

    monkeypatch.setattr(application.dispatcher, "start_polling", wait_for_stop)
    await application.start()
    try:
        await wait_registered(application)
        async with (
            ClientSession() as session,
            session.get(f"http://127.0.0.1:{settings.http_port}/ready") as response,
        ):
            assert response.status == 503
            assert (await response.json())["dependencies"]["redis"] == "unavailable"
    finally:
        await application.stop()


async def test_failed_startup_closes_bot_and_storage(
    settings: Settings, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = create_app(settings, bot)
    monkeypatch.setattr(application.storage, "open", AsyncMock(side_effect=RuntimeError("broken")))
    with pytest.raises(RuntimeError, match="broken"):
        await application.start()
    cast("AsyncMock", bot.session.close).assert_awaited_once()
    assert application.storage.handles == {}


async def test_stop_before_polling_closes_fsm(
    settings: Settings, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = create_app(settings, bot)
    close_fsm = AsyncMock()
    monkeypatch.setattr(application.dispatcher.fsm, "close", close_fsm)
    cast("AsyncMock", bot.delete_webhook).side_effect = ConnectionError("down")
    await application.start()
    await application.stop()
    close_fsm.assert_awaited_once()


async def test_polling_failure_still_closes_resources(
    settings: Settings, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = create_app(settings, bot)
    monkeypatch.setattr(
        application.dispatcher,
        "start_polling",
        AsyncMock(side_effect=RuntimeError("polling failed")),
    )
    await application.start()
    supervisor = application._supervisor
    assert supervisor is not None
    with pytest.raises(RuntimeError, match="polling failed"):
        await supervisor
    await application.stop()
    cast("AsyncMock", bot.session.close).assert_awaited_once()
    assert application.storage.handles == {}


async def test_polling_startup_failure_closes_fsm(
    settings: Settings, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = create_app(settings, bot)
    close_fsm = AsyncMock()
    monkeypatch.setattr(application.dispatcher.fsm, "close", close_fsm)

    async def fail_startup(**_kwargs: object) -> None:
        raise RuntimeError("startup failed")

    application.dispatcher.startup.register(fail_startup)
    await application.start()
    supervisor = application._supervisor
    assert supervisor is not None
    with pytest.raises(RuntimeError, match="startup failed"):
        await supervisor
    await application.stop()
    close_fsm.assert_awaited_once()
    cast("AsyncMock", bot.session.close).assert_awaited_once()


async def test_polling_shutdown_failure_does_not_delay_cleanup(
    settings: Settings, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = create_app(settings, bot)
    started = asyncio.Event()

    async def record_startup(**_kwargs: object) -> None:
        started.set()

    async def fail_shutdown(**_kwargs: object) -> None:
        raise RuntimeError("shutdown failed")

    async def wait_for_stop(*_args: object, **_kwargs: object) -> None:
        await asyncio.Event().wait()

    application.dispatcher.startup.register(record_startup)
    application.dispatcher.shutdown.register(fail_shutdown)
    monkeypatch.setattr(application.dispatcher, "_polling", wait_for_stop)
    await application.start()
    await asyncio.wait_for(started.wait(), timeout=2)
    await asyncio.wait_for(application.stop(), timeout=2)
    cast("AsyncMock", bot.session.close).assert_awaited_once()
    assert application.storage.handles == {}


async def test_webhook_shutdown_hook_failure_still_closes_resources(
    settings: Settings, bot: Bot
) -> None:
    configured = settings.model_copy(
        update={
            "update_mode": "webhook",
            "webhook_url": "https://example.com/telegram/hook",
            "webhook_secret": SecretStr("webhook-secret"),
        }
    )
    application = create_app(configured, bot)

    async def fail_shutdown(**_kwargs: object) -> None:
        raise RuntimeError("shutdown failed")

    application.dispatcher.shutdown.register(fail_shutdown)
    await application.start()
    await wait_registered(application)
    with pytest.raises(RuntimeError, match="shutdown failed"):
        await application.stop()
    cast("AsyncMock", bot.session.close).assert_awaited_once()
    assert application.storage.handles == {}


async def test_run_starts_and_stops_on_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    lifecycle = SimpleNamespace(
        settings=SimpleNamespace(update_mode="webhook"), start=AsyncMock(), stop=AsyncMock()
    )
    monkeypatch.setattr(main, "create_app", lambda: lifecycle)
    loop = asyncio.get_running_loop()

    def signal_immediately(_signal: object, callback: Callable[[], None]) -> None:
        callback()

    monkeypatch.setattr(loop, "add_signal_handler", signal_immediately)
    await main.run()
    lifecycle.start.assert_awaited_once()
    lifecycle.stop.assert_awaited_once()


async def test_run_exits_when_polling_stops_unexpectedly(monkeypatch: pytest.MonkeyPatch) -> None:
    lifecycle = SimpleNamespace(
        settings=SimpleNamespace(update_mode="polling"),
        start=AsyncMock(),
        stop=AsyncMock(),
        _supervisor=None,
    )

    async def start() -> None:
        lifecycle._supervisor = asyncio.create_task(asyncio.sleep(0))

    lifecycle.start.side_effect = start
    monkeypatch.setattr(main, "create_app", lambda: lifecycle)
    monkeypatch.setattr(asyncio.get_running_loop(), "add_signal_handler", lambda *_args: None)
    with pytest.raises(RuntimeError, match="polling stopped unexpectedly"):
        await main.run()
    lifecycle.stop.assert_awaited_once()
