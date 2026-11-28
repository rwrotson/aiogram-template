# aiogram-template

A GitHub template for a typed Aiogram Telegram bot. It supports long polling and HTTPS webhooks, starts without a database, and provides optional async clients for PostgreSQL, ClickHouse, MongoDB, and Redis.

## What Is Included

- Aiogram 3 dispatcher, `/start`, `/help`, `/faq`, and a two-question `/survey` FSM example with `/cancel`
- Polling by default, or an aiohttp webhook protected by Telegram's secret header
- Bounded polling concurrency and a grace period for active handlers at shutdown
- Pydantic Settings (`APP_*`, nested with `__`), structured logs, Prometheus metrics, optional OpenTelemetry traces, and `/live`, `/ready`, `/metrics` endpoints
- Optional storage backends as uv extras (`postgres-raw`, `postgres-orm`, `clickhouse`, `mongodb`, `redis`); Redis FSM storage when configured, process memory otherwise
- import-linter contracts for the layers (`main` → `bot` → `container` → `infra` → `services | core | config`), per-package ordering, and a ban on importing transitive dependencies directly
- Strict MyPy, Ruff, pytest in parallel and random order with network sockets blocked (except loopback) and a 95% coverage gate, poethepoet tasks, pre-commit hooks, Commitizen
- Claude Code hooks and per-area agent guides in `docs/agents/`
- Docker Compose for development and VPS deployment, multi-architecture GHCR images, and a ProperDocs site on GitHub Pages

## Stack

- **[Aiogram](https://docs.aiogram.dev/)** — Telegram Bot API framework
- **[aiohttp](https://docs.aiohttp.org/)** — webhook and operational HTTP server
- **[Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)** — environment-based configuration
- **[structlog](https://www.structlog.org/)**, **[prometheus-client](https://github.com/prometheus/client_python)**, **[OpenTelemetry](https://opentelemetry.io/)** — logs, metrics, traces
- **[uv](https://docs.astral.sh/uv/)** — package management
- **[Ruff](https://docs.astral.sh/ruff/)** — linting and formatting
- **[MyPy](https://mypy.readthedocs.io/)** — strict type checking
- **[pytest](https://docs.pytest.org/)** + **[pytest-xdist](https://github.com/pytest-dev/pytest-xdist)** + **[pytest-randomly](https://github.com/pytest-dev/pytest-randomly)** — parallel tests in random order with coverage enforcement
- **[import-linter](https://import-linter.readthedocs.io/)** — layer boundary contracts
- **[poethepoet](https://poethepoet.natn.io/)** — task runner
- **[commitizen](https://commitizen-tools.github.io/commitizen/)** — Conventional Commits, versioning, and CHANGELOG
- **[ProperDocs](https://properdocs.org/)** + **[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)** — documentation site

## Requirements

- Python 3.14+
- uv
- A Telegram bot token (see [Credentials](#credentials))
- Docker, only for container runs and deployment

## Getting Started

```bash
uv sync --all-extras --all-groups --locked
uv run pre-commit install
cp .env.example .env
# Set APP_BOT_TOKEN in .env to the real token.
```

## Usage

```bash
uv run poe serve
```

Send `/start`, `/help`, `/faq commands`, `/faq storage`, or `/survey` to the bot. The process also starts an operational HTTP server on `127.0.0.1:8000`:

```bash
curl http://127.0.0.1:8000/live
curl http://127.0.0.1:8000/ready
curl http://127.0.0.1:8000/metrics
```

`/ready` checks Telegram, update registration, and configured storage; `/live` checks only the local process. The basic install (`uv sync`) needs no database or storage drivers. Without `APP_REDIS__DSN`, survey state is lost on restart; to persist it, run `uv sync --extra redis` and set `APP_REDIS__DSN`. See [storage](docs/storage.md).

### Webhook mode

Set `APP_UPDATE_MODE=webhook`, `APP_WEBHOOK_URL` to a public HTTPS URL with a dedicated path (for example `https://bot.example.com/telegram/hook`), and `APP_WEBHOOK_SECRET`. The bot registers the webhook and menu commands with Telegram, retrying while Telegram is unavailable. Put a TLS reverse proxy in front of the webhook path only. See [deployment](docs/deployment.md).

### Docker

```bash
docker compose -f compose.yml -f compose.dev.yml up --build    # development with source reload
docker compose -f compose.yml -f compose.dev.yml --profile redis up --build
```

On a VPS, set `IMAGE_REF=ghcr.io/OWNER/REPO:X.Y.Z` and a real token in `.env`, then run `docker compose pull && docker compose up -d`. Compose publishes the operational port on host localhost only; the reverse proxy must keep `/metrics`, `/live`, and `/ready` private. The VPS update is manual.

## Development

Run development tasks with [poethepoet](https://poethepoet.natn.io/):

```bash
uv run poe check            # format check, lint, import contracts, type check, tests with coverage
uv run poe quick            # lint, import contracts, type check
uv run poe fmt
uv run poe fmt-check
uv run poe lint
uv run poe lint-imports
uv run poe typecheck
uv run poe test
uv run poe test-fast        # tests without coverage
uv run poe test-live        # tests/integration; needs --live, reads .env, fails without a DSN
uv run poe test-live -m redis_integration    # one backend: postgres_integration or redis_integration
uv run poe docs
uv run poe audit
```

`test` and `test-fast` do not collect `tests/integration`. PostgreSQL and Redis integration tests need `APP_POSTGRES_ORM__DSN` and `APP_REDIS__DSN`; CI runs them in separate jobs with service containers. Other tests run in parallel with network sockets blocked except loopback.

Claude Code hooks in `.claude/` format and autofix the Python file just edited and run `poe quick` at the end of a turn when Python files changed. Personal overrides go in `.claude/settings.local.json`, which is git-ignored. Agent instructions are in `AGENTS.md` and `docs/agents/`.

## Docs

```bash
uv run --all-extras --group docs properdocs serve
uv run --all-extras --group docs properdocs build --strict
```

Source is in `docs/`. ProperDocs generates the API reference from public docstrings and the configuration page from `Settings`. The release workflow deploys the site to GitHub Pages for version tags.

## Versioning & Changelog

This template uses [Conventional Commits](https://www.conventionalcommits.org/) enforced by a `commit-msg` pre-commit hook.

```bash
uv run cz bump
git push origin main --tags

uv run cz changelog --dry-run
```

Bump type is inferred automatically: `fix:` → patch, `feat:` → minor, `feat!:` / `BREAKING CHANGE` → major (minor while the version is `0.x`). `cz bump` creates the tag locally; pushing it starts the release workflow.

## Configuration

Settings are loaded by `app.config.settings.Settings` from `APP_*` environment variables and `.env`; defaults are in code and the process environment wins. Storage sections are nested with `__`:

| Prefix | Controls |
|--------|----------|
| `APP_BOT_TOKEN`, `APP_UPDATE_MODE`, `APP_WEBHOOK_*` | Telegram token and update delivery |
| `APP_HTTP_*`, `APP_READINESS_*` | Operational HTTP server and readiness checks |
| `APP_LOG_*`, `APP_OTLP_ENDPOINT` | Logging and optional traces |
| `APP_POSTGRES_RAW__*`, `APP_POSTGRES_ORM__*`, `APP_CLICKHOUSE__*`, `APP_MONGODB__*`, `APP_REDIS__*` | Optional storage backends |

```env
APP_BOT_TOKEN=123456:replace-with-your-bot-token
APP_REDIS__DSN=redis://localhost:6379/0
```

See `.env.example` and the generated configuration page in the documentation site for every setting.

### Credentials

`APP_BOT_TOKEN` (required):

1. Open [@BotFather](https://t.me/BotFather) in Telegram and send `/newbot`.
2. Enter a display name and a username ending in `bot`.
3. Copy the token BotFather returns (`123456:ABC...`) and set it as `APP_BOT_TOKEN` in `.env`, or in the deployment environment.
4. To rotate a leaked token, send `/revoke` to BotFather, choose the bot, and update `APP_BOT_TOKEN`.

`APP_WEBHOOK_SECRET` (required when `APP_UPDATE_MODE=webhook`):

1. Generate a random value of 1–256 ASCII letters, digits, underscores, or hyphens, for example `openssl rand -hex 32`.
2. Set it as `APP_WEBHOOK_SECRET`. The bot sends it to Telegram when registering the webhook, and Telegram returns it in the `X-Telegram-Bot-Api-Secret-Token` header, which is checked before an update is handled.
3. To rotate it, change the value and restart the bot so the webhook is registered again.

Keep `.env` and tokens untracked.

## Project Structure

```
src/
└── app/
    ├── main.py              # create_app(): bot, dispatcher, aiohttp server, startup and shutdown
    ├── container.py         # application-scoped dependencies
    ├── bot/                 # routers, handlers, middleware, FSM states, router factory
    ├── services/            # use cases, errors, ports (greeting, FAQ)
    ├── infra/               # service port implementations
    │   └── storage/         # optional async clients, readiness checks, BackendSpec registry
    ├── config/              # Settings (APP_*)
    └── core/                # logging, metrics, telemetry
tests/                       # mirrors the layers; integration/ runs only with --live
docs/                        # site source; agents/ holds agent guides and is not published
```

See [architecture](docs/architecture.md).

## CI/CD

`.github/workflows/ci.yml` runs on pushes and pull requests. Actions are pinned to commit SHAs.

| Job | What it does |
|-----|-------------|
| `quality` | ruff format check, ruff lint, import-linter contracts, strict mypy |
| `test` | parallel tests in random order, 95% coverage enforced |
| `lowest` | tests against the lowest allowed direct dependencies, with all extras |
| `integration-postgres`, `integration-redis` | `poe test-live` against a service container |
| `build` | package build, `properdocs build --strict`, pip-audit, trivy filesystem scan (CRITICAL/HIGH, fixed only) |
| `container` | production image build, a smoke test that `/live` answers with a dummy token, and trivy image scan (CRITICAL/HIGH, fixed only) |

Dependabot opens PRs for uv dependencies, Docker, Docker Compose, GitHub Actions, and pre-commit hooks.

`.github/workflows/release.yml` runs on version tags (`v*`) or via `workflow_dispatch`. It runs CI first, then:

| Job | What it does |
|-----|-------------|
| `image` | checks that the tag matches the project version, builds and scans the image, and publishes amd64 and arm64 images to GHCR (tags only) |
| `docs` | builds the docs with ProperDocs and deploys them to GitHub Pages (version tags only) |

A manual run builds and scans the image but publishes nothing and deploys no docs. Set Pages Source to **GitHub Actions** and allow `v*` tags in the `github-pages` environment. The VPS update stays manual.

## Using This Template

The distribution (`aiogram-app`), import package (`app`), and environment prefix (`APP_`) have separate names. Follow the [renaming checklist](docs/notes.md#renaming-the-template) when copying this template into a new project.

### Remove the Examples

Replace the demonstration features when your first real one exists:

- `src/app/services/greeting.py`, `src/app/services/faq.py`, `src/app/infra/faq.py`, and their tests
- the survey, `/faq`, and greeting handlers and FSM states in `src/app/bot/`, with their tests in `tests/bot/`
- the container wiring and the example mentions in README and `docs/`

### Remove Storage

A bot without databases can drop `src/app/infra/storage/` and its tests.

- the storage extras and drivers in `pyproject.toml`, the storage sections in `Settings` and `.env.example`, and the `app.infra.storage` import-linter contracts
- `tests/integration/`, the integration jobs in `ci.yml`, and the database profiles in `compose.dev.yml`
- Redis FSM storage and readiness checks in the container and `docs/storage.md`

Then run `uv lock`, `uv run poe check`, and `uv run --all-extras --group docs properdocs build --strict`.

## Author

Igor Lashkov — rwrotson@yandex.ru
