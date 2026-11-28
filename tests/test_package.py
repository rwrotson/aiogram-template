import json
import subprocess
import sys
from pathlib import Path

import pytest

OPTIONAL_DRIVERS = ("sqlalchemy", "psycopg", "redis", "pymongo", "clickhouse_connect")

PROBE = """
import json, logging, sys
import pydantic_settings
import structlog

reads = []
original_init = pydantic_settings.BaseSettings.__init__


def spy_init(self, *args, **kwargs):
    reads.append("Settings()")
    original_init(self, *args, **kwargs)


def audit(event, args):
    if event == "open" and str(args[0]).endswith(".env"):
        reads.append(str(args[0]))


pydantic_settings.BaseSettings.__init__ = spy_init
sys.addaudithook(audit)
before = len(logging.getLogger().handlers)
{imports}
print(json.dumps({{
    "reads": reads,
    "new_handlers": len(logging.getLogger().handlers) - before,
    "structlog_configured": structlog.is_configured(),
    "drivers": [name for name in {drivers!r} if name in sys.modules],
}}))
"""


IMPORT_MODULE = "import {module}"

IMPORT_ALL = """
import importlib, pkgutil
import app

for info in pkgutil.walk_packages(app.__path__, "app."):
    importlib.import_module(info.name)
"""


def probe(imports: str, tmp_path: Path) -> dict[str, object]:
    """Run import statements in a fresh interpreter and report global side effects."""
    (tmp_path / ".env").write_text(
        "APP_BOT_TOKEN=42:DOTENV\nAPP_NAME=From dotenv\nAPP_LOG_LEVEL=DEBUG\n"
    )
    code = PROBE.format(imports=imports, drivers=OPTIONAL_DRIVERS)
    env = {
        "PATH": "",
        "APP_BOT_TOKEN": "42:TEST",
        "APP_NAME": "From environment",
        "APP_REDIS__DSN": "redis://localhost",
    }

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
        env=env,
    )

    report: dict[str, object] = json.loads(result.stdout)

    return report


@pytest.mark.parametrize("module", ["app", "app.main"])
def test_import_leaves_global_state_untouched(module: str, tmp_path: Path) -> None:
    report = probe(IMPORT_MODULE.format(module=module), tmp_path)

    assert report["reads"] == []
    assert report["new_handlers"] == 0
    assert report["structlog_configured"] is False
    assert report["drivers"] == []


def test_importing_every_module_leaves_global_state_untouched(tmp_path: Path) -> None:
    # Storage modules import optional drivers by design, so only the driver check is skipped.
    report = probe(IMPORT_ALL, tmp_path)

    assert report["reads"] == []
    assert report["new_handlers"] == 0
    assert report["structlog_configured"] is False
