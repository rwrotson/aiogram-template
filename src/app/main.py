import asyncio
import signal
from contextlib import AsyncExitStack, suppress
from urllib.parse import urlsplit

import structlog
from aiogram import Bot
from aiogram.fsm.storage.base import BaseEventIsolation, BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.bot.factory import create_dispatcher
from app.config import Settings, load_settings
from app.container import AppContainer
from app.core.logging import configure_logging
from app.core.telemetry import configure_tracing
from app.infra.storage.base import StorageManager

DISTRIBUTION = "aiogram-app"
RETRY_DELAY = 5.0
COMMANDS = [
    BotCommand(command="start", description="Greet the user"),
    BotCommand(command="help", description="Show commands"),
    BotCommand(command="survey", description="Start a short survey"),
    BotCommand(command="cancel", description="Cancel the survey"),
]


class ApplicationWebhookHandler(SimpleRequestHandler):
    """Leave the bot session open until application shutdown finishes."""

    async def close(self) -> None:
        """Let the application close the bot session after dispatcher hooks."""


class BotApplication:
    """Own one bot, dispatcher, storage manager and operational HTTP server."""

    def __init__(self, settings: Settings, bot: Bot | None = None) -> None:
        self.settings = settings
        self.bot = bot or Bot(settings.bot_token.get_secret_value())
        self.storage = StorageManager(settings.readiness_timeout, settings.readiness_cache_ttl)
        fsm_storage: BaseStorage
        events_isolation: BaseEventIsolation | None = None
        if settings.redis is None:
            fsm_storage = MemoryStorage()
        else:
            import aiogram.fsm.storage.redis as redis_storage  # noqa: PLC0415 - optional Redis extra

            redis_fsm_storage = redis_storage.RedisStorage.from_url(
                settings.redis.dsn.get_secret_value()
            )
            fsm_storage = redis_fsm_storage
            events_isolation = redis_fsm_storage.create_isolation()
        self.dispatcher = create_dispatcher(fsm_storage, events_isolation)
        self._fsm_closed = False
        self.dispatcher.shutdown.register(self._mark_fsm_closed)
        self.container = AppContainer(settings=settings, storage=self.storage)
        self.http = web.Application()
        self.http.router.add_get("/live", self.live)
        self.http.router.add_get("/ready", self.ready)
        self.http.router.add_get("/metrics", self.metrics)
        if settings.update_mode == "webhook":
            if settings.webhook_url is None or settings.webhook_secret is None:
                raise ValueError("webhook settings are required")
            ApplicationWebhookHandler(
                dispatcher=self.dispatcher,
                bot=self.bot,
                handle_in_background=False,
                secret_token=settings.webhook_secret.get_secret_value(),
                container=self.container,
            ).register(self.http, path=urlsplit(settings.webhook_url).path)
        self._runner: web.AppRunner | None = None
        self._supervisor: asyncio.Task[None] | None = None
        self._registered = False
        self._polling_started = False
        self._tracer: TracerProvider | None = None

    async def live(self, _: web.Request) -> web.Response:
        """Report that the process and operational server are alive."""
        return web.json_response({"status": "ok"})

    async def ready(self, _: web.Request) -> web.Response:
        """Report Telegram setup and dependency availability."""
        dependencies = await self.storage.readiness()
        try:
            async with asyncio.timeout(self.settings.readiness_timeout):
                await self.bot.get_me()
            telegram = "ok"
        except Exception:  # noqa: BLE001 - any probe failure means unavailable
            telegram = "unavailable"
        dependencies["telegram"] = telegram
        dependencies["updates"] = "ok" if self._registered else "unavailable"
        healthy = all(value == "ok" for value in dependencies.values())
        return web.json_response(
            {"status": "ok" if healthy else "unavailable", "dependencies": dependencies},
            status=200 if healthy else 503,
        )

    async def metrics(self, _: web.Request) -> web.Response:
        """Expose Prometheus metrics on the operational port."""
        await self.storage.readiness()
        return web.Response(body=generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})

    async def _configure_telegram(self) -> None:
        if self.settings.update_mode == "polling":
            await self.bot.delete_webhook(drop_pending_updates=False)
        await self.bot.set_my_commands(COMMANDS)
        if self.settings.update_mode == "webhook":
            if self.settings.webhook_url is None or self.settings.webhook_secret is None:
                raise ValueError("webhook settings are required")
            await self.bot.set_webhook(
                self.settings.webhook_url,
                secret_token=self.settings.webhook_secret.get_secret_value(),
                drop_pending_updates=False,
                allowed_updates=self.dispatcher.resolve_used_update_types(),
            )
            self._registered = True
            structlog.get_logger().info("webhook_registered")

    async def _mark_fsm_closed(self) -> None:
        self._fsm_closed = True

    async def _close_fsm_if_needed(self) -> None:
        if not self._fsm_closed:
            await self.dispatcher.fsm.close()
            self._fsm_closed = True

    async def _serve_updates(self) -> None:
        logger = structlog.get_logger()
        while True:
            try:
                await self._configure_telegram()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("telegram_setup_failed")
                await asyncio.sleep(RETRY_DELAY)
                continue

            if self.settings.update_mode == "webhook":
                return

            self._registered = True
            self._polling_started = True
            try:
                await self.dispatcher.start_polling(
                    self.bot,
                    handle_signals=False,
                    close_bot_session=False,
                    container=self.container,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("polling_failed")
                raise
            finally:
                self._registered = False
            return

    async def start(self) -> None:
        """Start shared resources and retry Telegram setup in the background."""
        configure_logging(self.settings.log_level, self.settings.resolved_log_format)
        self._tracer = configure_tracing(self.settings.otlp_endpoint, self.settings.name)
        try:
            await self.storage.open(self.settings)
            if self.settings.update_mode == "webhook":
                await self.dispatcher.emit_startup(bot=self.bot, container=self.container)
            self._runner = web.AppRunner(self.http)
            await self._runner.setup()
            site = web.TCPSite(self._runner, self.settings.http_host, self.settings.http_port)
            await site.start()
            self._supervisor = asyncio.create_task(self._serve_updates())
            structlog.get_logger().info("application_started", mode=self.settings.update_mode)
        except Exception:
            await self.stop()
            raise

    async def _stop_updates(self) -> None:
        self._registered = False
        supervisor = self._supervisor
        if supervisor is None:
            return
        if self.settings.update_mode == "polling" and self._polling_started:
            with suppress(RuntimeError, TimeoutError):
                async with asyncio.timeout(20):
                    await self.dispatcher.stop_polling()
        if supervisor.done():
            if not supervisor.cancelled():
                try:
                    supervisor.result()
                except Exception:  # noqa: BLE001 - a worker failure must not skip resource cleanup
                    structlog.get_logger().exception("update_task_failed")
        else:
            supervisor.cancel()
            with suppress(asyncio.CancelledError):
                await supervisor
        self._supervisor = None

    async def stop(self) -> None:
        """Stop update processing and close each owned resource."""
        cleanup = AsyncExitStack()
        if self._tracer is not None:
            cleanup.callback(self._tracer.shutdown)
        cleanup.push_async_callback(self.storage.close)
        cleanup.push_async_callback(self.bot.session.close)
        if self.settings.update_mode == "webhook":
            cleanup.push_async_callback(
                self.dispatcher.emit_shutdown, bot=self.bot, container=self.container
            )
        else:
            cleanup.push_async_callback(self._close_fsm_if_needed)
        if self._runner is not None:
            cleanup.push_async_callback(self._runner.cleanup)
        try:
            await self._stop_updates()
        finally:
            try:
                await cleanup.aclose()
            finally:
                self._runner = None
                self._tracer = None
                structlog.get_logger().info("application_stopped")


def create_app(settings: Settings | None = None, bot: Bot | None = None) -> BotApplication:
    """Build an isolated bot application from explicit or environment settings."""
    return BotApplication(settings or load_settings(), bot)


async def run() -> None:
    """Run the bot until the process receives a shutdown signal."""
    application = create_app()
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(name, stopped.set)
    await application.start()
    stop_wait = asyncio.create_task(stopped.wait())
    try:
        if application.settings.update_mode == "webhook":
            await stop_wait
        elif application._supervisor is not None:
            done, _ = await asyncio.wait(
                {stop_wait, application._supervisor}, return_when=asyncio.FIRST_COMPLETED
            )
            if application._supervisor in done and not stopped.is_set():
                application._supervisor.result()
                raise RuntimeError("polling stopped unexpectedly")
    finally:
        stop_wait.cancel()
        await application.stop()


if __name__ == "__main__":
    asyncio.run(run())
