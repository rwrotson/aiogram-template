import os
import re
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings, load_settings
from app.config.settings import env_fields

ENV_EXAMPLE = Path(__file__).parents[2] / ".env.example"
TOKEN = SecretStr("42:TEST")


def test_defaults_and_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BOT_TOKEN", "42:TEST")
    defaults = load_settings()
    assert defaults.name == "Aiogram App"
    assert defaults.update_mode == "polling"
    assert defaults.postgres_orm is None
    assert defaults.resolved_log_format == "console"

    monkeypatch.setenv("APP_REDIS__DSN", "redis://user:hunter2@redis:6379/0")
    configured = load_settings()
    assert configured.redis is not None
    assert "hunter2" not in repr(configured)
    assert "42:TEST" not in repr(configured)


def test_process_environment_overrides_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    Path(".env").write_text("APP_BOT_TOKEN=42:TEST\nAPP_NAME=From file\n")
    monkeypatch.setenv("APP_NAME", "From process")
    assert Settings().name == "From process"


def test_webhook_requires_https_url_and_secret() -> None:
    with pytest.raises(ValidationError, match="APP_WEBHOOK_URL"):
        Settings(bot_token=TOKEN, update_mode="webhook")
    with pytest.raises(ValidationError, match="dedicated path"):
        Settings(
            bot_token=TOKEN,
            update_mode="webhook",
            webhook_url="http://example.com/hook",
            webhook_secret=SecretStr("secret"),
        )
    valid = Settings(
        bot_token=TOKEN,
        update_mode="webhook",
        webhook_url="https://example.com/hook",
        webhook_secret=SecretStr("secret"),
    )
    assert valid.webhook_url == "https://example.com/hook"
    with pytest.raises(ValidationError, match="ASCII letters"):
        Settings(
            bot_token=TOKEN,
            update_mode="webhook",
            webhook_url="https://example.com/hook",
            webhook_secret=SecretStr("invalid secret"),
        )
    assert Settings(bot_token=TOKEN, environment="production").resolved_log_format == "json"


def test_env_example_documents_every_setting() -> None:
    documented = set(re.findall(r"^#? ?(APP_[A-Z_]+)=", ENV_EXAMPLE.read_text(), re.MULTILINE))
    settings = {name for name, _ in env_fields()}
    assert settings - documented == set()
    assert documented - settings == {"APP_PORT"}


def test_no_app_variables_leak_into_tests() -> None:
    assert not [name for name in os.environ if name.startswith("APP_")]
