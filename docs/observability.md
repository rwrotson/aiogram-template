# Observability

Structlog emits JSON logs outside development and readable console logs in development. Update middleware binds the Telegram update ID, measures processing duration, counts outcomes, and creates a trace span when `APP_OTLP_ENDPOINT` is set. Logs include active trace and span IDs. No message text, chat ID, or user ID is used as a metric label.

The operational aiohttp server exposes `/live`, `/ready`, and `/metrics` in both update modes. `/live` reports process liveness. `/ready` checks Telegram API reachability, update-mode registration, and every configured storage backend; it returns 503 on failure. The storage checks have bounded timeouts and cached results. Telegram API reachability is bounded by the same timeout.

`/metrics` exposes `app_telegram_updates_total`, `app_telegram_update_duration_seconds`, `app_telegram_updates_in_progress`, `app_storage_available`, and generic database-operation metrics, together with Python and process metrics from Prometheus. Keep `/metrics` private. In Compose, the host port binds only to localhost; in webhook mode the reverse proxy must expose only the webhook path. The bot runs as one process, so Prometheus multiprocess setup is unnecessary.

`APP_OTLP_ENDPOINT` takes a full OTLP/HTTP traces endpoint, such as `http://collector:4318/v1/traces`. Tracing is disabled when unset. Each application owns its tracer provider and closes it after active updates finish; the template does not run a collector.
