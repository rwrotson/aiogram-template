# AGENTS.md

A template for an Aiogram Telegram bot that runs with only a token, serves operational endpoints through aiohttp, and adds optional PostgreSQL and Redis backends through extras.

Distribution name: `aiogram-app` | Python package: `app` | Environment prefix: `APP_`

## Load instructions by path

For each area of the task, mirror its repo-relative path under [docs/agents](docs/agents/) and read the matching guide before editing: for `src/app/bot/handlers.py`, read the [bot guide](docs/agents/src/app/bot.md). For any code change, also read [docs/architecture.md](docs/architecture.md). The [Read when](#read-when) table lists every guide.

## Commands

This project uses [uv](https://docs.astral.sh/uv/) for package management; the full task list is in `[tool.poe.tasks]` in `pyproject.toml`.

```bash
uv sync --all-extras --all-groups
uv run poe serve        # start the bot (polling by default); needs APP_BOT_TOKEN
uv run poe check        # fmt-check, lint, lint-imports, typecheck, test (95% coverage)
uv run poe quick        # lint, lint-imports, typecheck (no formatting check or tests)
uv run poe test-fast    # pytest without coverage
uv run poe test-live    # tests/integration against real services; needs --live and DSNs
uv run poe fmt          # ruff format . (rewrites files)
uv run poe audit        # pip-audit over locked dependencies
uv run --all-extras --group docs properdocs build --strict
```

## Change Workflow

- Inspect `git status` before editing. Preserve existing uncommitted changes and limit edits to the requested task.
- When working from an active staged plan in `docs/plans/`, read it before work, implement only the first incomplete stage, append dated evidence, and stop at the stage boundary.
- Run `uv run poe check` after application code changes. After documentation source, `properdocs.yml`, or public docstring changes, also run `uv run --all-extras --group docs properdocs build --strict`.
- The Claude Code hooks in `.claude/` run `ruff format` and `ruff check --fix` on the Python file just edited (an intentional edit) and, at Stop, run `poe quick` when Python files changed during the turn; they do not replace `poe check`.
- Use non-rewriting checks (`poe fmt-check`, `poe lint`) for verification; run formatters or `--fix` only when intentionally editing files. Pre-commit's Ruff hooks rewrite files.
- Report which checks ran, which were skipped, and why. Report integration tests as skipped when no DSN is configured; `poe test-fast` is not the full CI suite: it skips coverage, and CI also runs the lowest-dependency job, PostgreSQL and Redis integration tests, package, docs, and container builds, and security scans.
- When changing public settings, commands, storage extras, or deployment instructions, update README, `.env.example`, and the docs.

## Commit Handoff

- Do not create or amend commits on the user's behalf, except where an active staged plan in `docs/plans/` authorizes it.
- After completing and verifying a meaningful, self-contained part of the work, pause before starting the next part.
- At each pause, send the user a one-line English Conventional Commit message for the completed work. Resume when the user asks you to continue.

## Layers

```
main      src/app/main.py        create_app(): bot, dispatcher, aiohttp server, startup and shutdown
container src/app/container.py   per-application ownership of services, storage, and cleanup
bot       src/app/bot/           Aiogram routers, middleware, FSM states, dispatcher composition
infra     src/app/infra/         adapters for service ports; optional storage backends (extras)
services  src/app/services/      use cases, transport-independent types, errors, ports
config    src/app/config/        Pydantic Settings, APP_* loading, defaults
core      src/app/core/          logging, metrics, optional tracing
```

Dependencies follow Telegram interface → services ← infrastructure; services import no Aiogram, settings, or drivers. The rules are in [docs/architecture.md](docs/architecture.md); `uv run poe lint-imports` enforces them.

## Invariants

- Do not lower coverage thresholds, disable checks, relax import-linter contracts, or add lint and type suppressions solely to pass CI. Explain necessary suppressions at the affected line.
- The default bot must work with only `APP_BOT_TOKEN`, without credentials for storage services. A configured backend requires its matching extra.
- An external outage affects `/ready`, not `/live` or process startup.
- Build a fresh Router for every dispatcher, and keep mutable settings and storage state scoped to the application or update, never in module globals. Tests must pass in random order.
- Expected failures raise a service error; handlers turn them into user replies.
- Tests never use the network; Telegram API calls are mocked.
- Code, docs, comments, and commit messages are in English.
- Keep the user's `.env`, tokens, and secrets untracked.

## Code Style

- Use absolute `app.` imports. Services, infrastructure, and the Telegram interface follow the import direction above.
- MyPy runs with `strict = true` over the project. All new code must have complete type annotations. Prefer `X | Y` over `Optional[X]`.

## Python Formatting

- Keep function signatures, calls, and collection literals on one line when they fit. When they need wrapping, put one parameter, argument, or item on each line. Add a trailing comma after the last entry when there are two or more entries so Ruff preserves the layout. Do not enable `COM812`.
- Omit optional trailing commas in single-entry forms. Keep the required comma in a single-element tuple and any comma Ruff inserts in a wrapped signature with one parameter.

## Documentation and Comments

- Keep documentation, docstrings, and comments in English, short and factual. Describe each entity's purpose without editorial commentary or tutorials.
- Do not add module docstrings. Package docstrings in `__init__.py` are allowed. Put package behavior and module details in README, this file, or `docs/`.
- Give public classes, functions, and methods a docstring. Prefer one line describing their overall purpose; do not repeat names, signatures, or type annotations. Test functions are identified by their names and need no docstrings.
- Add docstrings to protected or private objects only when they explain behavior that is not clear from code.
- Keep inline comments only for non-obvious behavior or decisions. Put a short comment on the relevant line when it fits; otherwise place it immediately above. Retain necessary tool directives such as `# noqa` and `# type: ignore`.
- A comment placed above a line or group of lines applies only to it. Separate that line or group from the code before and after it with a blank line, unless it starts or ends a block, so the comment's scope is clear. At module and class level, give each commented constant or attribute its own block, and keep uncommented related definitions together in one block.
- In long functions, methods, and tests, separate logical steps (input validation, setup, execution, result handling; arrange, act, assert) with a single blank line. Do not add comments to label the steps. Keep short functions compact.
- At module level, keep `UPPER_CASE` constants and lowercase objects (loggers, imported modules, routers, apps) in separate blocks divided by a blank line.
- Prefer clearer names and more precise types over comments that restate code.
- Edit `Settings` field descriptions and source docstrings, then rebuild the docs with ProperDocs; do not edit generated configuration or reference pages.

## Read when

| Task | Read |
| --- | --- |
| Any code change | [docs/architecture.md](docs/architecture.md) (layers, rules, errors, adding functionality) |
| Working in `src/app/bot/` or `src/app/main.py`, handlers, FSM, webhook | [Bot guide](docs/agents/src/app/bot.md) |
| Working in `src/app/services/` or adding a feature | [Services guide](docs/agents/src/app/services.md) |
| Working in `src/app/config/`, settings, `.env.example` | [Config guide](docs/agents/src/app/config.md) |
| Working in `src/app/core/`, logs, metrics, tracing, probes | [Core guide](docs/agents/src/app/core.md) |
| Working in `src/app/infra/`, storage backends, Redis FSM | [Infrastructure guide](docs/agents/src/app/infra.md) |
| Working in `tests/` | [Test guide](docs/agents/tests.md) |
| Working in `docs/`, `properdocs.yml`, or public docstrings | [Docs guide](docs/agents/docs.md) |
| Dependencies, extras, `pyproject.toml`, `uv.lock` | [Dependency guide](docs/agents/pyproject.md) |
| CI, releases, container images, Dependabot | [GitHub guide](docs/agents/github.md) |
| `Dockerfile`, `compose*.yml`, reverse proxy, VPS updates | [Deployment guide](docs/agents/deploy.md) |
| Renaming the template | [Renaming checklist](docs/notes.md#renaming-the-template) |
