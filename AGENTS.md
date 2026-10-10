# Repository guide

This repository is a GitHub template for an Aiogram Telegram bot. The distribution is `aiogram-app`, the import package is `app`, and Python 3.14+ is required.

## Commands

Use uv for dependencies and commands:

```bash
uv sync --all-extras --all-groups
uv run poe serve
uv run poe check          # fmt-check, lint, lint-imports, typecheck, test
uv run --all-extras --group docs properdocs build --strict
```

Individual tasks: `fmt`, `fmt-check`, `lint`, `lint-imports`, `typecheck`, `test`, `test-fast` (no coverage), `test-integration`, `test-integration-postgres`, `test-integration-redis`, `docs`, `audit`. CI runs formatting, lint, import-linter contracts, strict MyPy, pytest with 95% coverage, tests against the lowest allowed direct dependencies, PostgreSQL and Redis integration tests, package/docs/container builds, dependency audit, and an image vulnerability scan.

## Dependencies

- Put runtime imports in project dependencies, optional backend drivers in the matching extra, development tools in `dev`, and documentation tools in `docs`.
- Change dependencies through uv and update `pyproject.toml` and `uv.lock` together. Verify the lock with `uv sync --locked --all-extras --all-groups`.
- Raise a direct dependency's lower bound when code needs a newer API. Verify new or upgraded dependencies against their declared lower bounds and the lowest-direct-dependencies CI job; the locked environment alone does not check them.
- Use the project environment for tools. Do not install packages manually into `.venv` or treat local installations as declared dependencies.

## Application structure

- `src/app/main.py` defines `create_app()` and owns the bot, dispatcher, aiohttp server, and startup and shutdown. `uv run poe serve` starts polling by default. Polling concurrency is bounded and shutdown waits briefly for active updates before closing dependencies. A valid `APP_BOT_TOKEN` is required. `APP_UPDATE_MODE=webhook` also requires a public HTTPS `APP_WEBHOOK_URL` and `APP_WEBHOOK_SECRET`.
- `src/app/bot/` contains Aiogram routers, middleware, FSM states, and handler composition. Build a fresh Router for every dispatcher; Aiogram routers cannot be attached twice. Configure event isolation for FSM updates, using process locks with memory and Redis locks with Redis. Keep handlers thin and use Aiogram context for application-scoped dependencies.
- `src/app/services/` contains use cases, transport-independent types, errors, and ports; it never imports Aiogram, settings, or database drivers. The greeting example is here.
- `src/app/config/` contains Pydantic Settings, `APP_*` environment loading, and defaults in code. Storage settings are nested models (`APP_REDIS__DSN`) with `SecretStr` secrets. Every setting must appear in `.env.example`; a test enforces it, and the docs configuration page is generated from `Settings`.
- `src/app/core/` contains logging, metrics, and optional tracing. `/live`, `/ready`, and `/metrics` are provided by aiohttp in both update modes. `/ready` checks Telegram, update registration, and configured storage; `/live` only checks the local process.
- `src/app/infra/storage/` contains optional async clients and readiness checks. Backends are registered as `BackendSpec` entries in `base.py`; features access them through application-scoped `StorageManager`. No storage service is required by default. A configured backend requires its matching project extra. A configured Redis also gives Aiogram persistent FSM storage with a configurable TTL; otherwise FSM uses process memory.
- `tests/` mirrors the layers (`bot/`, `infra/`, `core/`, `config/`). Shared fakes live in `tests/fakes.py` and shared fixtures in `tests/conftest.py`. Use `fake_backends` to stub storage clients. Test routing and FSM behavior with `Dispatcher.feed_raw_update()` and mocked Telegram API calls. PostgreSQL and Redis integration suites skip without their DSNs and fail when selected explicitly.

Follow the import direction in `docs/architecture.md`: Telegram interface → services ← infrastructure, with infrastructure implementing ports defined in services. import-linter contracts in `pyproject.toml` enforce it. Use absolute `app.` imports and complete type annotations. Storage clients are initialized during the application lifecycle and closed at shutdown. An external outage should affect `/ready`, not `/live` or process startup. Keep the default bot usable with only a token, without credentials for storage services.

## Change workflow

- Inspect `git status` before editing. Preserve existing uncommitted changes and limit edits to the requested task.
- Do not create Git commits. After completing and checking a meaningful, independently committable part of the work, pause and give the user a one-line Conventional Commit message in chat. Resume only after the user responds.
- Run `uv run poe check` after application code changes. After documentation source or public docstring changes, also run `uv run --all-extras --group docs properdocs build --strict`.
- Do not lower coverage thresholds, disable checks, or add lint and type suppressions solely to pass CI. Explain necessary suppressions at the affected line.
- Use non-rewriting checks for verification; run formatters or `--fix` only when intentionally editing files. Pre-commit's Ruff hooks rewrite files.
- Report which checks ran, which were skipped, and why. When no PostgreSQL DSN is configured, report integration tests as skipped rather than as full integration verification; `test-fast` is not the full CI suite.
- For webhook changes, test accepted and rejected secret headers, registration behavior, and error outcomes. For commands, test responses, FSM state transitions, cancellation, and behavior with and without Redis.
- Keep mutable settings and storage state scoped to the application or update. Tests must pass in random order without depending on process-wide state.
- Edit `Settings` field descriptions and source docstrings, then rebuild the docs with ProperDocs; do not edit generated configuration or reference pages.

## Deployment and releases

The production image runs one bot process and logs to stdout. `compose.yml` binds the operational aiohttp port to localhost on the VPS and rotates container logs. An external TLS reverse proxy should forward only the configured webhook path and must block public access to `/metrics`, `/ready`, and `/live`. `compose.dev.yml` adds source reload and optional database profiles. Version tags run CI, then publish an amd64/arm64 image to GHCR and the ProperDocs site to GitHub Pages. The VPS update is manual.

The user's `.env` and tokens stay untracked. Update README, `.env.example`, and the docs when changing public settings, commands, storage extras, or deployment instructions.

## Documentation and comments

- Write documentation, docstrings, and comments in English. Keep them brief and factual; describe each entity's purpose and relevant behavior without lecturing or editorial commentary.
- Do not write module docstrings. Package docstrings in `__init__.py` are allowed. Describe package behavior and any module-level nuance in README, AGENTS.md, or the docs when it needs explanation.
- Give every public class, function, and method a docstring, preferably one line. Describe its overall purpose without repeating its name, signature, types, or obvious implementation. Test functions are identified by their names and do not need docstrings.
- Add docstrings to protected and private objects only when they explain important behavior that the code does not make clear.
- Keep inline comments only for non-obvious behavior, constraints, or decisions. Put a short comment on the relevant line when it fits; otherwise put it immediately above. Keep required tool directives such as `noqa`.
- Prefer clearer names and more precise types over comments that explain the code.
