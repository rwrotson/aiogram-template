import asyncio
import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
import structlog
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.fsm.storage.redis import RedisEventIsolation, RedisStorage
from aiogram.types import Update
from aiohttp import ClientSession
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
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


def message_update() -> dict[str, object]:
    """Build one valid Telegram message update for runtime tests."""
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": 42, "type": "private"},
            "text": "/start",
            "from": {"id": 42, "is_bot": False, "first_name": "User42"},
        },
    }


async def test_polling_serves_health_and_stops_cleanly(
    settings: Settings, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = settings.model_copy(update={"polling_max_concurrent_updates": 7})
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
        polling = cast("AsyncMock", application.dispatcher.start_polling)
        assert polling.await_args is not None
        assert polling.await_args.kwargs["tasks_concurrency_limit"] == 7
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


async def test_webhook_dispatches_real_updates_and_reports_handler_errors(
    settings: Settings, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = settings.model_copy(
        update={
            "update_mode": "webhook",
            "webhook_url": "https://example.com/telegram/hook",
            "webhook_secret": SecretStr("webhook-secret"),
        }
    )
    application = create_app(configured, bot)
    send = AsyncMock(return_value=None)
    monkeypatch.setattr(Bot, "__call__", send)
    url = f"http://127.0.0.1:{configured.http_port}/telegram/hook"
    update = message_update()
    message = cast("dict[str, object]", update["message"])
    message["text"] = "/faq commands"
    await application.start()
    try:
        await wait_registered(application)
        async with ClientSession() as session:
            async with session.post(
                url,
                json=update,
                headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
            ) as response:
                assert response.status == 401
            send.assert_not_awaited()

            async with session.post(
                url,
                json=update,
                headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
            ) as response:
                assert response.status == 200
            assert send.await_args_list[-1].args[0].text == (
                "Use /help to see all commands and /survey to try the FSM example."
            )

            monkeypatch.setattr(
                application.container.faq, "answer", Mock(side_effect=RuntimeError("broken"))
            )
            message["text"] = "/faq storage"
            async with session.post(
                url,
                json=update,
                headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
            ) as response:
                assert response.status == 500
            assert send.await_count == 1
    finally:
        await application.stop()


async def test_webhook_registration_retries_while_http_remains_available(
    settings: Settings, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = settings.model_copy(
        update={
            "update_mode": "webhook",
            "webhook_url": "https://example.com/telegram/hook",
            "webhook_secret": SecretStr("webhook-secret"),
        }
    )
    first_attempt = asyncio.Event()
    attempts = 0

    async def register(*_args: object, **_kwargs: object) -> bool:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            first_attempt.set()
            raise ConnectionError("Telegram unavailable")
        return True

    cast("AsyncMock", bot.set_webhook).side_effect = register
    monkeypatch.setattr(main, "RETRY_DELAY", 0.1)
    application = create_app(configured, bot)
    await application.start()
    try:
        await asyncio.wait_for(first_attempt.wait(), timeout=2)
        async with ClientSession() as session:
            url = f"http://127.0.0.1:{configured.http_port}"
            async with session.get(f"{url}/live") as response:
                assert response.status == 200
            async with session.get(f"{url}/ready") as response:
                assert response.status == 503
                assert (await response.json())["dependencies"]["updates"] == "unavailable"
        await wait_registered(application)
        assert attempts == 2
        assert cast("AsyncMock", bot.set_my_commands).await_count == 2
        cast("AsyncMock", bot.delete_webhook).assert_not_awaited()
    finally:
        await application.stop()


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
            "redis": RedisSettings(
                dsn=SecretStr("redis://localhost/0"),
                max_connections=7,
                socket_timeout=3.0,
                socket_connect_timeout=2.0,
                fsm_ttl_seconds=60,
            ),
            "http_port": free_port(),
        }
    )
    fsm = create_app(configured, bot).dispatcher.fsm
    assert isinstance(fsm.storage, RedisStorage)
    assert isinstance(fsm.events_isolation, RedisEventIsolation)
    assert fsm.events_isolation.redis is fsm.storage.redis
    assert fsm.storage.state_ttl == 60
    assert fsm.storage.data_ttl == 60
    pool = fsm.storage.redis.connection_pool
    assert pool.max_connections == 7
    assert pool.connection_kwargs["socket_timeout"] == 3.0
    assert pool.connection_kwargs["socket_connect_timeout"] == 2.0


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


async def test_shutdown_waits_for_active_update_before_closing_bot(
    settings: Settings, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = create_app(settings, bot)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def wait_for_stop(*_args: object, **_kwargs: object) -> None:
        await asyncio.Event().wait()

    async def handle(_event: object, _data: dict[str, object]) -> None:
        entered.set()
        await release.wait()

    monkeypatch.setattr(application.dispatcher, "start_polling", wait_for_stop)
    await application.start()
    await wait_registered(application)
    event = Update.model_validate(message_update())
    update_task = asyncio.create_task(application.update_middleware(handle, event, {}))
    await entered.wait()
    stop_task = asyncio.create_task(application.stop())
    await asyncio.sleep(0.05)
    assert not stop_task.done()
    cast("AsyncMock", bot.session.close).assert_not_awaited()
    release.set()
    await asyncio.wait_for(stop_task, timeout=2)
    await update_task
    cast("AsyncMock", bot.session.close).assert_awaited_once()


async def test_shutdown_cancels_update_after_grace_period(
    settings: Settings, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = settings.model_copy(update={"shutdown_grace_seconds": 0.01})
    application = create_app(configured, bot)
    entered = asyncio.Event()

    async def wait_for_stop(*_args: object, **_kwargs: object) -> None:
        await asyncio.Event().wait()

    async def handle(_event: object, _data: dict[str, object]) -> None:
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(application.dispatcher, "start_polling", wait_for_stop)
    await application.start()
    await wait_registered(application)
    event = Update.model_validate(message_update())
    update_task = asyncio.create_task(application.update_middleware(handle, event, {}))
    await entered.wait()
    await asyncio.wait_for(application.stop(), timeout=2)
    with pytest.raises(asyncio.CancelledError):
        await update_task
    assert application.update_middleware.active_count == 0
    cast("AsyncMock", bot.session.close).assert_awaited_once()


async def test_webhook_shutdown_waits_for_active_request(
    settings: Settings, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = settings.model_copy(
        update={
            "update_mode": "webhook",
            "webhook_url": "https://example.com/telegram/hook",
            "webhook_secret": SecretStr("webhook-secret"),
        }
    )
    application = create_app(configured, bot)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def handle(_event: object, _data: dict[str, object]) -> None:
        entered.set()
        await release.wait()

    async def feed_update(_bot: Bot, update: Update, **_kwargs: object) -> None:
        await application.update_middleware(handle, update, {})

    monkeypatch.setattr(application.dispatcher, "feed_update", feed_update)
    await application.start()
    await wait_registered(application)
    url = f"http://127.0.0.1:{configured.http_port}/telegram/hook"
    async with ClientSession() as session:
        request_task = asyncio.create_task(
            session.post(
                url,
                json=message_update(),
                headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
            )
        )
        await entered.wait()
        stop_task = asyncio.create_task(application.stop())
        await asyncio.sleep(0.05)
        cast("AsyncMock", bot.session.close).assert_not_awaited()
        release.set()
        response = await asyncio.wait_for(request_task, timeout=2)
        assert response.status == 200
        response.release()
        await asyncio.wait_for(stop_task, timeout=2)
    cast("AsyncMock", bot.session.close).assert_awaited_once()


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


async def test_sequential_applications_use_their_own_tracers(
    settings: Settings,
    bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    global_provider = trace.get_tracer_provider()
    exporters: list[InMemorySpanExporter] = []

    def make_provider(_endpoint: str | None, _service_name: str) -> TracerProvider:
        provider = TracerProvider()
        exporter = InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        exporters.append(exporter)
        return provider

    async def wait_for_stop(*_args: object, **_kwargs: object) -> None:
        await asyncio.Event().wait()

    async def handle(_event: object, _data: dict[str, object]) -> None:
        structlog.get_logger().info("traced_update")

    monkeypatch.setattr(main, "configure_tracing", make_provider)
    configured = settings.model_copy(update={"otlp_endpoint": "http://collector:4318/v1/traces"})
    for _ in range(2):
        application = create_app(configured, bot)
        monkeypatch.setattr(application.dispatcher, "start_polling", wait_for_stop)
        await application.start()
        try:
            await wait_registered(application)
            event = Update.model_validate(message_update())
            await application.update_middleware(handle, event, {})
        finally:
            await application.stop()

    assert trace.get_tracer_provider() is global_provider
    traces = [exporter.get_finished_spans()[0].context.trace_id for exporter in exporters]
    assert len(traces) == 2
    assert traces[0] != traces[1]
    logged = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")
    ]
    update_logs = [entry for entry in logged if entry.get("event") == "traced_update"]
    assert [entry["trace_id"] for entry in update_logs] == [
        format(value, "032x") for value in traces
    ]


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
