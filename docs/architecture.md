# Architecture

The Telegram interface parses updates and replies, services hold the rules, and infrastructure supplies adapters and optional storage. The default bot needs only a token; storage backends are optional extras.

## Layers

The Telegram interface and infrastructure may import services and never each other.

| Layer | Location | Responsibility |
| --- | --- | --- |
| Services | `app/services/` | Transport-independent use cases, types, errors, and ports |
| Telegram interface | `app/bot/` | Update handlers, FSM states, middleware, and dispatcher composition |
| Infrastructure | `app/infra/` | Optional clients, readiness, and concrete service adapters |
| Composition | `app/main.py`, `app/container.py` | Per-application ownership, Telegram mode selection, aiohttp, and cleanup |
| Configuration | `app/config/` | Typed settings, environment loading, and defaults |
| Operations | `app/core/` | Logs, metrics, and optional traces |

### Rules

- Dependencies follow **Telegram interface → services ← infrastructure**.
- Services do not import Aiogram, settings, or drivers.
- Infrastructure implements service ports without importing handlers.
- Use absolute `app.` imports.
- Package order is `main` → `bot` → `container` → `infra` → `services | core | config`; the last three are independent of each other.
- Every package with more than one module has an exhaustive `layers` contract: a new module must be added to it.
- A new third-party dependency belongs to the lowest layer that needs it, and to that layer's extra.
- Packages installed only as transitive dependencies are not imported directly. `psycopg_pool` is the exception: it comes from the `psycopg[pool]` feature the `postgres-raw` extra declares.
- Storage clients are opened during the application lifecycle and closed at shutdown.
- An external outage affects `/ready`, not `/live` or process startup.
- The default bot works with only a token; a configured backend requires its extra.

Import-linter checks the package layers, exhaustive per-package layers, the service, infrastructure, configuration, and operations boundaries, and direct imports of transitive dependencies with `uv run poe lint-imports`; the contracts are in `pyproject.toml`. Rules that the contracts do not cover are checked in review.

## Lifecycle


`create_app()` creates one bot and dispatcher with a fresh Router. Startup opens configured storage clients, starts the operational aiohttp server, and launches Telegram setup in a background task. Polling removes an existing webhook, then consumes updates with bounded concurrency. Webhook mode registers a public HTTPS URL and requires a matching secret header. Setup failures are logged and retried; `/ready` stays unavailable until setup succeeds. Shutdown stops new updates, waits up to the configured grace period for active handlers, then closes the dispatcher, bot session, HTTP server, storage clients, and tracer provider.

## Background tasks

Tasks created while handling an update inherit its context, including the structlog `update_id`. Start lifecycle tasks (the update supervisor, polling stop, shutdown wait) with `context=contextvars.Context()` so update IDs do not leak into their logs; per-update tasks keep their context:

```python
task = asyncio.create_task(worker(), context=contextvars.Context())
```

## Examples

The `/faq` example passes a topic from the Telegram handler to a service, which reads through a port implemented by an in-memory infrastructure adapter. Unknown topics raise a service error that the handler turns into a user reply. The survey handlers use Aiogram's FSM for two text answers and clear state after the result or `/cancel`. MemoryStorage and per-user event isolation are used when Redis is absent; configured Redis gets a separate FSM connection and Redis-backed event isolation, so concurrent updates for one user do not race. The FSM connection's lifecycle does not interfere with the generic Redis client. Redis FSM records have a configurable TTL; memory state does not survive restarts or multiple processes.

## Errors

| Error | Base classes | Raised when | Reply |
| --- | --- | --- | --- |
| `ServiceError` | `Exception` | Base for every expected use-case failure | Generic retry message |
| `NotFoundError` | `ServiceError` | A requested item does not exist | Generic "Not found." |
| `FaqTopicNotFoundError` | `NotFoundError` | The FAQ topic does not exist | Unknown topic with the available ones |
| `ConflictError` | `ServiceError` | The request conflicts with existing state | Conflict message |

Handlers catch `ServiceError` and reply with `reply_for_error()` from `app/bot/replies.py`, which resolves the nearest base class in the `ERROR_REPLY` table; the `ServiceError` entry is the final fallback. Unexpected exceptions get no reply; they are logged with update context. Add a subclass and an `ERROR_REPLY` entry for each new kind of expected failure.

## Adding functionality

For new features, keep Telegram parsing and responses in handlers, put rules in services, and build adapters in infrastructure. Pass application-scoped settings and storage through Aiogram handler context or middleware; do not store mutable application state in module globals. A handler may report expected service errors to the user while unexpected failures are logged with update context.
