# Tests

- `tests/` mirrors the layers (`bot/`, `services/`, `infra/`, `core/`, `config/`). Shared fakes live in `tests/fakes.py` and shared fixtures in `tests/conftest.py`.
- Tests run in random order (pytest-randomly) and must not depend on process-wide state. `poe test` enforces 95% coverage. Reproduce an order-dependent failure with `uv run pytest -p randomly --randomly-seed=<seed>`.
- Test routing and FSM behavior with `Dispatcher.feed_raw_update()` and mocked Telegram API calls. For webhooks, cover accepted and rejected secret headers, registration, and errors. For commands, cover responses, FSM transitions, cancellation, and behavior with and without Redis.
- Use `fake_backends` to stub storage clients.
- PostgreSQL and Redis suites in `tests/integration/` are collected only with `--live` (`poe test-live`); `poe test` and `test-fast` skip the directory. Under `--live` a missing DSN fails the test with a clear error, and `-m postgres_integration` or `-m redis_integration` selects one backend. Report them as skipped, not verified, when no DSN is set. Tests run in parallel (`-n auto`) with sockets blocked except Unix sockets and loopback; integration modules carry `enable_socket`.
- Test functions and fixtures need type annotations but no docstrings.
- Run a focused file or `-k` selection before the full suite.
