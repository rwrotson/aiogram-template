# Services

- `src/app/services/` holds use cases, transport-independent types, errors, and ports. It never imports Aiogram, settings, or database drivers.
- A port is a `Protocol` defined next to the service that needs it (`FaqRepository` in `faq.py`); infrastructure implements it.
- Expected failures raise a subclass of `ServiceError` in `errors.py`, such as `NotFoundError`; give each feature its own subclass, such as `FaqTopicNotFoundError`, so replies stay specific. Add new errors to the [error table](../../../architecture.md#errors).
- To add a feature:
    1. Put the rules in a service, with ports for anything it reads or writes.
    2. Implement the ports in `src/app/infra/`.
    3. Add a thin handler in `src/app/bot/` that calls the service and maps its errors to replies.
    4. Wire the pieces in `src/app/container.py`.
    5. Test the service without Aiogram in `tests/services/` and the handler in `tests/bot/`.
- `greeting.py` and `faq.py` show the pattern; `/faq` goes from the handler through `FaqService` to an in-memory adapter in `infra/faq.py`.
