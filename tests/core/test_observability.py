import json
import logging

import pytest
import structlog
from opentelemetry.sdk.trace import TracerProvider

from app.core.logging import configure_logging
from app.core.metrics import DATABASE_OPERATIONS, observe_database_operation
from app.core.telemetry import configure_tracing


def test_json_logs_include_trace_context(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", "json")
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("work") as span:
        structlog.get_logger("test").info("inside_span", answer=42)
    structlog.get_logger("test").info("outside_span")
    inside, outside = (json.loads(line) for line in capsys.readouterr().out.splitlines())
    assert inside["trace_id"] == format(span.get_span_context().trace_id, "032x")
    assert inside["answer"] == 42
    assert "trace_id" not in outside


def test_console_logs_are_readable(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("DEBUG", "console")
    logging.getLogger("stdlib").debug("from stdlib")
    assert "from stdlib" in capsys.readouterr().out


def test_tracing_is_optional() -> None:
    assert configure_tracing(None, "test") is None
    provider = configure_tracing("http://127.0.0.1:4318/v1/traces", "test")
    assert isinstance(provider, TracerProvider)
    assert provider.resource.attributes["service.name"] == "test"
    provider.shutdown()


async def test_database_operation_metrics_record_success_and_failure() -> None:
    success = DATABASE_OPERATIONS.labels(backend="test", operation="read", result="ok")
    failed = DATABASE_OPERATIONS.labels(backend="test", operation="read", result="error")
    before_success = success._value.get()
    before_failed = failed._value.get()
    async with observe_database_operation("test", "read"):
        pass
    with pytest.raises(ValueError, match="failure"):
        async with observe_database_operation("test", "read"):
            raise ValueError("failure")
    assert success._value.get() == before_success + 1
    assert failed._value.get() == before_failed + 1
