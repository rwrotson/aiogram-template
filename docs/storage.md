# Optional storage

The bot starts with no database. It provides optional asynchronous clients for raw PostgreSQL (`postgres-raw`), SQLAlchemy PostgreSQL (`postgres-orm`), ClickHouse (`clickhouse`), MongoDB (`mongodb`), and Redis (`redis`). Add the matching project extra before setting its `APP_*` configuration. For example:

```bash
uv sync --extra redis
# Set APP_REDIS__DSN in .env, then start the bot.
uv run poe serve
```

`StorageManager` creates configured clients during startup without requiring a live server. `/ready` probes them concurrently with `APP_READINESS_TIMEOUT`, caches results for `APP_READINESS_CACHE_TTL`, and reports an outage without stopping the process. `/live` does not probe external systems. A feature requests a typed backend through `StorageManager.get(SPEC)`; service code depends on its own port, not on the driver. Client cleanup happens at shutdown or after failed startup.

Redis also enables persistent Aiogram FSM storage. It uses a separate connection owned by the dispatcher. Without Redis, the survey uses MemoryStorage. A configured Redis outage is reported by `/ready`; the bot does not silently switch FSM storage.

The `postgres-orm` extra includes an engine and session factory for future adapters, but this template has no ORM tables, migrations, or Alembic. Add a migration tool and revisions when your application adds models. CI's PostgreSQL integration test checks that the configured ORM client connects and passes readiness.
