# Bot and application lifecycle

- `src/app/bot/` holds the Aiogram routers, middleware, FSM states, and dispatcher composition. Keep handlers thin: parse the update, call a service, send the reply. Rules live in `services/`.
- Build a fresh Router for every dispatcher (`create_router()`); Aiogram routers cannot be attached twice.
- Pass application-scoped dependencies (services, settings, storage) through Aiogram handler context or middleware. Do not use module globals.
- Handlers turn expected service errors into user replies through `reply_for_error()` and the `ERROR_REPLY` table in `bot/replies.py`; add a table entry for each new error kind; unexpected failures are logged with update context by `UpdateMiddleware`.
- Configure event isolation for FSM updates: process locks with memory storage and Redis locks with Redis. Cover cancellation and behavior with and without Redis.
- `src/app/main.py` defines `create_app()`, which owns the bot, dispatcher, aiohttp server, startup, and shutdown. Polling concurrency is bounded and shutdown waits briefly for active updates before closing dependencies. Setup failures are retried; `/ready` stays unavailable until setup succeeds.
- Webhook mode requires a public HTTPS `APP_WEBHOOK_URL` and `APP_WEBHOOK_SECRET`. Test accepted and rejected secret headers, registration behavior, and error outcomes.
- Test routing and FSM transitions with `Dispatcher.feed_raw_update()` and mocked Telegram API calls; see the [test guide](../../tests.md).
- Start lifecycle tasks in `main.py` with `context=contextvars.Context()`; per-update tasks keep their context.
