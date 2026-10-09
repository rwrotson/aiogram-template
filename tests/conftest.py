import logging
import os
import socket
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import structlog
from aiogram import Bot
from pydantic import SecretStr

from app.config import Settings
from app.infra.storage import base


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep developer settings and the local .env file out of tests."""
    for name in list(os.environ):
        if name.startswith("APP_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    """Restore global logging after each application test."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers, root.level = handlers, level
    structlog.reset_defaults()


@pytest.fixture
def settings() -> Settings:
    """Create isolated settings with a syntactically valid dummy token."""
    return Settings(environment="test", bot_token=SecretStr("42:TEST"), http_port=free_port())


def free_port() -> int:
    """Reserve an unused local port for a test server."""
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return int(connection.getsockname()[1])


@pytest.fixture
def bot(monkeypatch: pytest.MonkeyPatch) -> Bot:
    """Return a bot whose Telegram API calls are mocked by tests."""
    instance = Bot("42:TEST")
    monkeypatch.setattr(instance, "get_me", AsyncMock(return_value=SimpleNamespace(id=42)))
    monkeypatch.setattr(instance, "delete_webhook", AsyncMock(return_value=True))
    monkeypatch.setattr(instance, "set_webhook", AsyncMock(return_value=True))
    monkeypatch.setattr(instance, "set_my_commands", AsyncMock(return_value=True))
    monkeypatch.setattr(instance.session, "close", AsyncMock())
    return instance


@pytest.fixture
def fake_backends(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Replace optional client factories with one configurable mock."""
    create_handle = AsyncMock()
    monkeypatch.setattr(
        base, "import_module", lambda _: SimpleNamespace(create_handle=create_handle)
    )
    return create_handle
