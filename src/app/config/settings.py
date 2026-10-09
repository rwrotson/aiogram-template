from collections.abc import Iterator
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, SettingsConfigDict

MAX_WEBHOOK_SECRET_LENGTH = 256


class PostgresRawSettings(BaseModel):
    """psycopg connection pool for hand-written SQL."""

    dsn: SecretStr = Field(description="libpq DSN, for example postgresql://user:pass@host/db")
    min_size: int = Field(default=0, ge=0, description="Connections kept open when idle")
    max_size: int = Field(default=10, ge=1, description="Maximum pool size")
    connect_timeout: float = Field(
        default=5.0, gt=0, description="Seconds to wait for a connection"
    )


class PostgresOrmSettings(BaseModel):
    """SQLAlchemy async engine used by the ORM adapters and Alembic."""

    dsn: SecretStr = Field(description="SQLAlchemy URL, for example postgresql+psycopg://...")
    pool_size: int = Field(default=5, ge=1, description="Persistent connections in the pool")
    max_overflow: int = Field(default=10, ge=0, description="Extra connections above pool_size")
    pool_timeout: float = Field(default=10.0, gt=0, description="Seconds to wait for a pooled one")
    connect_timeout: int = Field(default=5, gt=0, description="Seconds to establish a connection")


class ClickHouseSettings(BaseModel):
    """ClickHouse HTTP client; the connection is opened on first use."""

    host: str = Field(description="Server hostname")
    port: int = Field(default=8123, description="HTTP(S) port")
    username: str = Field(default="default", description="User name")
    password: SecretStr = Field(default=SecretStr(""), description="Password")
    database: str = Field(default="default", description="Default database")
    secure: bool = Field(default=False, description="Use HTTPS")
    connect_timeout: float = Field(default=5.0, gt=0, description="Seconds to connect")


class MongoDBSettings(BaseModel):
    """PyMongo async client."""

    dsn: SecretStr = Field(description="MongoDB connection string")
    max_pool_size: int = Field(default=100, ge=1, description="Maximum connections per server")
    server_selection_timeout: float = Field(
        default=5.0, gt=0, description="Seconds to find an available server"
    )


class RedisSettings(BaseModel):
    """redis.asyncio client with a connection pool."""

    dsn: SecretStr = Field(description="Redis URL, for example redis://host:6379/0")
    max_connections: int | None = Field(default=None, ge=1, description="Pool limit; unbounded")
    socket_timeout: float = Field(default=5.0, gt=0, description="Seconds per command")
    socket_connect_timeout: float = Field(default=5.0, gt=0, description="Seconds to connect")


class Settings(BaseSettings):
    """Load application and optional storage settings from the environment."""

    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", env_nested_delimiter="__", extra="ignore"
    )

    name: str = Field(default="Aiogram App", description="Telemetry service name")
    bot_token: SecretStr = Field(description="Telegram bot token from BotFather")
    update_mode: Literal["polling", "webhook"] = Field(
        default="polling", description="How Telegram updates reach the bot"
    )
    webhook_url: str | None = Field(default=None, description="Public HTTPS webhook URL with path")
    webhook_secret: SecretStr | None = Field(
        default=None, description="Secret sent in Telegram webhook request headers"
    )
    http_host: str = Field(default="127.0.0.1", description="Host for health and webhook server")
    http_port: int = Field(default=8000, ge=1, le=65535, description="Health and webhook port")
    environment: Literal["development", "production", "test"] = Field(
        default="development", description="Deployment environment"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Root log level"
    )
    log_format: Literal["json", "console"] | None = Field(
        default=None, description="Log renderer; console in development and json otherwise"
    )
    otlp_endpoint: str | None = Field(
        default=None, description="OTLP/HTTP traces endpoint; tracing is off when unset"
    )
    readiness_timeout: float = Field(
        default=2.0, gt=0, description="Seconds allowed for each storage readiness probe"
    )
    readiness_cache_ttl: float = Field(
        default=5.0, ge=0, description="Seconds to reuse the last readiness result"
    )
    postgres_raw: PostgresRawSettings | None = None
    postgres_orm: PostgresOrmSettings | None = None
    clickhouse: ClickHouseSettings | None = None
    mongodb: MongoDBSettings | None = None
    redis: RedisSettings | None = None

    @model_validator(mode="after")
    def validate_webhook(self) -> Settings:
        """Require a secure webhook endpoint and secret in webhook mode."""
        if self.update_mode != "webhook":
            return self
        if self.webhook_url is None or self.webhook_secret is None:
            raise ValueError("webhook mode requires APP_WEBHOOK_URL and APP_WEBHOOK_SECRET")
        url = urlsplit(self.webhook_url)
        if (
            url.scheme != "https"
            or not url.netloc
            or not url.path.startswith("/")
            or url.path == "/"
            or url.path in {"/live", "/ready", "/metrics"}
            or url.query
            or url.fragment
        ):
            raise ValueError("APP_WEBHOOK_URL must be HTTPS with a dedicated path")
        secret = self.webhook_secret.get_secret_value()
        if not 1 <= len(secret) <= MAX_WEBHOOK_SECRET_LENGTH or any(
            not (char.isascii() and (char.isalnum() or char in "_-")) for char in secret
        ):
            raise ValueError("APP_WEBHOOK_SECRET must contain 1-256 ASCII letters, digits, _ or -")
        return self

    @property
    def resolved_log_format(self) -> Literal["json", "console"]:
        """Select the explicit log format or the environment default."""
        if self.log_format is not None:
            return self.log_format
        return "console" if self.environment == "development" else "json"


def nested_model(field: FieldInfo) -> type[BaseModel] | None:
    """Return the settings model of an optional nested section, if the field is one."""
    for candidate in getattr(field.annotation, "__args__", (field.annotation,)):
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            return candidate
    return None


def env_fields(
    model: type[BaseModel] = Settings, prefix: str = "APP_"
) -> Iterator[tuple[str, FieldInfo]]:
    """Yield every leaf setting with its environment variable name."""
    for name, field in model.model_fields.items():
        variable = f"{prefix}{name.upper()}"
        section = nested_model(field)
        if section is None:
            yield variable, field
        else:
            yield from env_fields(section, f"{variable}__")


def load_settings() -> Settings:
    """Load environment and .env settings for one application instance."""
    return Settings()
