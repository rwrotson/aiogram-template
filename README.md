# aiogram-template

A GitHub template for a typed Aiogram Telegram bot. It supports long polling and HTTPS webhooks, starts without a database, and provides optional async clients for PostgreSQL, ClickHouse, MongoDB, and Redis.

## Included

- Aiogram 3 dispatcher, `/start`, `/help`, and a two-question `/survey` FSM example with `/cancel`
- Polling by default, or an aiohttp webhook protected by Telegram's secret header
- Pydantic Settings, structured logs, Prometheus metrics, optional OpenTelemetry traces, and `/live` and `/ready`
- Redis FSM storage when Redis is configured; process-local memory otherwise
- Strict MyPy, Ruff, import-linter layer contracts, pytest with 95% coverage, random test order, uv, pre-commit, and Commitizen
- Docker Compose for development and VPS deployment, multi-architecture GHCR releases, and MkDocs on GitHub Pages

## Quick start

Create a bot with [BotFather](https://t.me/BotFather), then install [uv](https://docs.astral.sh/uv/) and run:

```bash
cp .env.example .env
# Set APP_BOT_TOKEN in .env to the real token.
uv sync --all-extras --all-groups
uv run poe serve
```

Send `/start`, `/help`, or `/survey` to the bot. The process starts an operational HTTP server on `127.0.0.1:8000`:

```bash
curl http://127.0.0.1:8000/live
curl http://127.0.0.1:8000/ready
```

`/ready` checks Telegram, update registration, and configured storage backends. `/live` checks only the local process. With no `APP_REDIS__DSN`, survey state is lost on restart. To persist it, install the `redis` extra and set `APP_REDIS__DSN`. Other storage backends are optional; see [storage](docs/storage.md).

## Webhook mode

Set `APP_UPDATE_MODE=webhook`, `APP_WEBHOOK_URL=https://bot.example.com/telegram/hook`, and a random `APP_WEBHOOK_SECRET`. The URL must use HTTPS and include a dedicated path. The bot registers the webhook and menu commands with Telegram, retrying while Telegram is unavailable. The aiohttp server listens on `APP_HTTP_HOST:APP_HTTP_PORT`; put a TLS reverse proxy in front of the webhook path. Telegram's secret header is checked before an update is handled. See [deployment](docs/deployment.md).

## Development and deployment

```bash
uv run poe check
uv run poe fmt
uv run --all-extras --group docs mkdocs build --strict
uv run pre-commit install
```

`docker compose -f compose.yml -f compose.dev.yml up --build` runs the bot with source reload. Add `--profile redis` or another storage profile for local backing services. For a VPS, set `IMAGE_REF=ghcr.io/OWNER/REPO:X.Y.Z` and a real token in `.env`, then run `docker compose pull && docker compose up -d`. Compose publishes the operational port on host localhost only. The reverse proxy must expose the webhook path, and keep `/metrics`, `/live`, and `/ready` private. The `v*` release workflow publishes amd64 and arm64 images after CI; deployment remains manual.

## Architecture and use as a template

Telegram handlers in `src/app/bot/` call transport-independent services in `src/app/services/`. Infrastructure adapters in `src/app/infra/` implement service ports. `src/app/main.py` owns the bot, dispatcher, aiohttp server, optional storage clients, and shutdown. See [architecture](docs/architecture.md).

After using the GitHub template, change the distribution name in `pyproject.toml` and `DISTRIBUTION` in `src/app/main.py`, the project title in README and `mkdocs.yml`, `APP_NAME`, and the GitHub URLs. Keep the `app` import package unless you update imports, import-linter, coverage, MyPy, and reference generation together. Replace the demonstration handlers and survey with your own features. Keep `.env` and tokens untracked.
