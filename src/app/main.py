import asyncio
import signal
from contextlib import suppress
from urllib.parse import urlsplit

import structlog
from aiogram import Bot
from aiogram.fsm.storage.base import BaseStorage
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


class BotApplication:
    """Own one bot, dispatcher, storage manager and operational HTTP server."""

    def __init__(self, settings: Settings, bot: Bot | None = None) -> None:
        self.settings = settings
        self.bot = bot or Bot(settings.bot_token.get_secret_value())
        self.storage = StorageManager(settings.readiness_timeout, settings.readiness_cache_ttl)
        fsm_storage: BaseStorage
        if settings.redis is None:
            fsm_storage = MemoryStorage()
        else:
            import aiogram.fsm.storage.redis as redis_storage  # noqa: PLC0415 - optional Redis extra

            fsm_storage = redis_storage.RedisStorage.from_url(settings.redis.dsn.get_secret_value())
        self.dispatcher = create_dispatcher(fsm_storage)
        self.container = AppContainer(settings=settings, storage=self.storage)
        self.http = web.Application()
        self.http.router.add_get("/live", self.live)
        self.http.router.add_get("/ready", self.ready)
        self.http.router.add_get("/metrics", self.metrics)
        if settings.update_mode == "webhook":
            if settings.webhook_url is None or settings.webhook_secret is None:
                raise ValueError("webhook settings are required")
            SimpleRequestHandler(
                dispatcher=self.dispatcher,
                bot=self.bot,
                handle_in_background=False,
                secret_token=settings.webhook_secret.get_secret_value(),
                container=self.container,
            ).register(self.http, path=urlsplit(settings.webhook_url).path)
        self._runner: web.AppRunner | None = None
        self._supervisor: asyncio.Task[None] | None = None
        self._registered = False
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

    async def _serve_updates(self) -> None:
        logger = structlog.get_logger()
        while True:
            try:
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
                    logger.info("webhook_registered")
                    return
                self._registered = True
                await self.dispatcher.start_polling(
                    self.bot,
                    handle_signals=False,
                    close_bot_session=False,
                    container=self.container,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("telegram_setup_failed")
            self._registered = False
            await asyncio.sleep(RETRY_DELAY)

    async def start(self) -> None:
        """Start shared resources and retry Telegram setup in the background."""
        configure_logging(self.settings.log_level, self.settings.resolved_log_format)
        self._tracer = configure_tracing(self.settings.otlp_endpoint, self.settings.name)
        try:
            await self.storage.open(self.settings)
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

    async def stop(self) -> None:
        """Stop update processing and close each owned resource."""
        self._registered = False
        if self._supervisor is not None:
            self._supervisor.cancel()
            with suppress(asyncio.CancelledError):
                await self._supervisor
            self._supervisor = None
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        await self.dispatcher.emit_shutdown(bot=self.bot, container=self.container)
        await self.bot.session.close()
        await self.storage.close()
        if self._tracer is not None:
            self._tracer.shutdown()
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
    try:
        await stopped.wait()
    finally:
        await application.stop()


if __name__ == "__main__":
    asyncio.run(run())
