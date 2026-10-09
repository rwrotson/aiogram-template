# Getting Started

Create a bot with BotFather and copy `.env.example` to `.env`. Replace `APP_BOT_TOKEN` with the bot's token. Then run:

```bash
uv sync --all-extras --all-groups
uv run poe serve
```

The default polling mode removes an old webhook without dropping pending updates. Send `/start` and `/help` to see the command examples. `/survey` asks for a programming language and a framework; `/cancel` clears an unfinished survey. The FSM uses process memory unless `APP_REDIS__DSN` is set and the `redis` extra is installed.

The operational aiohttp server is local by default:

```bash
curl http://127.0.0.1:8000/live
curl http://127.0.0.1:8000/ready
curl http://127.0.0.1:8000/metrics
```

For webhook mode, set `APP_UPDATE_MODE=webhook`, `APP_WEBHOOK_URL` to a public HTTPS URL with a path, and `APP_WEBHOOK_SECRET` to a random value of 1–256 ASCII letters, digits, underscores, or hyphens. Route only that path from your TLS proxy to the aiohttp port. The application registers the webhook and commands with Telegram, retrying on transient failures.

## Quality checks

```bash
uv run poe check
uv run poe test-fast
uv run --all-extras --group docs mkdocs build --strict
```

Tests run in random order. PostgreSQL and Redis integration tests require `APP_POSTGRES_ORM__DSN` and `APP_REDIS__DSN`, respectively. Ordinary tests skip an integration suite when its service is absent; `test-integration-postgres` and `test-integration-redis` fail when the selected service is missing. `test-integration` runs both. CI supplies both services in separate jobs. The repository contains no ORM models or migrations to apply.

## Add a feature

Put business rules and transport-independent types in `src/app/services/`. Define a service port when a use case needs external data, implement it in `src/app/infra/`, and inject the adapter into handlers from the application container. Add handlers on a fresh Router created by a factory under `src/app/bot/`. Test handlers with Aiogram's `feed_raw_update()` and test service behavior separately. See [architecture](architecture.md).
