import pytest
from pydantic import SecretStr

from app.config import PostgresOrmSettings, Settings
from app.infra.storage.base import POSTGRES_ORM, StorageManager

pytestmark = [pytest.mark.integration, pytest.mark.postgres_integration]


async def test_postgres_orm_connects_and_reports_ready(postgres_dsn: str) -> None:
    settings = Settings(
        bot_token=SecretStr("42:TEST"),
        postgres_orm=PostgresOrmSettings(dsn=SecretStr(postgres_dsn)),
    )
    manager = StorageManager()
    await manager.open(settings)
    try:
        assert await manager.readiness() == {"postgres_orm": "ok"}
        assert await manager.get(POSTGRES_ORM) is not None
    finally:
        await manager.close()
