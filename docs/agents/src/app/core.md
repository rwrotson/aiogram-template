# Core

- `src/app/core/` holds logging (`logging.py`), Prometheus metrics (`metrics.py`), and optional OpenTelemetry tracing (`telemetry.py`). It imports no other application layer except configuration.
- Logs go to stdout; the production image runs one process.
- aiohttp provides `/live`, `/ready`, and `/metrics` in both update modes. `/live` checks only the local process. `/ready` checks Telegram, update registration, and configured storage. An external outage must affect `/ready`, never `/live` or startup.
- Keep metric registries and tracer providers scoped to the application so tests can run in any order.
- See [observability](../../../observability.md) for the user-facing description.
- Ruff `banned-api` allows `logging.basicConfig`, `structlog.configure` and `logging.getLogger` only in `logging.py`; elsewhere use `structlog.get_logger()`.
- Start lifecycle tasks with `context=contextvars.Context()` so the update-bound `update_id` does not leak into their logs (see the architecture guide).
