# Infrastructure

- `src/app/infra/` implements service ports and holds optional storage clients. It never imports handlers.
- Backends are `BackendSpec` entries in `src/app/infra/storage/base.py`. Features reach them through the application-scoped `StorageManager`; clients are opened at startup and closed at shutdown.
- No storage service is required by default. A configured backend needs its matching project extra (`redis`, `postgres-raw`, `postgres-orm`, `clickhouse`, `mongodb`), and drivers are imported only in that backend's module.
- Each backend provides a readiness check used by `/ready`; an unreachable backend must not stop the process from starting.
- A configured Redis also gives Aiogram persistent FSM storage with a configurable TTL on a separate connection, plus Redis event isolation; otherwise FSM uses process memory.
- Stub storage clients in tests with `fake_backends`; real-service tests live in `tests/integration/` (see the [test guide](../../tests.md)). See [storage](../../../storage.md) for the user-facing description.
