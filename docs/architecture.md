# Architecture and layer boundaries

| Layer | Location | Responsibility |
| --- | --- | --- |
| Services | `app/services/` | Transport-independent use cases, types, errors, and ports |
| Telegram interface | `app/bot/` | Update handlers, FSM states, middleware, and dispatcher composition |
| Infrastructure | `app/infra/` | Optional clients, readiness, and concrete service adapters |
| Composition | `app/main.py`, `app/container.py` | Per-application ownership, Telegram mode selection, aiohttp, and cleanup |
| Configuration | `app/config/` | Typed settings, environment loading, and defaults |
| Operations | `app/core/` | Logs, metrics, and optional traces |

Dependencies follow **Telegram interface → services ← infrastructure**. Services do not import Aiogram, settings, or drivers. Infrastructure implements service ports without importing handlers. Import-linter checks these boundaries with `uv run poe lint-imports`.

`create_app()` creates one bot and dispatcher with a fresh Router. Startup opens configured storage clients, starts the operational aiohttp server, and launches Telegram setup in a background task. Polling removes an existing webhook, then consumes updates. Webhook mode registers a public HTTPS URL and requires a matching secret header. Setup failures are logged and retried; `/ready` stays unavailable until setup succeeds. Shutdown cancels update processing and closes the dispatcher, bot session, HTTP server, storage clients, and tracer provider.

The example handlers use Aiogram's FSM for two text answers and clear state after the result or `/cancel`. MemoryStorage is used when Redis is absent; configured Redis gets a separate FSM connection so its lifecycle does not interfere with the generic Redis client. Do not assume memory state survives restarts or multiple processes.

For new features, keep Telegram parsing and responses in handlers, put rules in services, and build adapters in infrastructure. Pass application-scoped settings and storage through Aiogram handler context or middleware; do not store mutable application state in module globals. A handler may report expected service errors to the user while unexpected failures are logged with update context.
