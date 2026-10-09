import json
from collections.abc import Iterator

import mkdocs_gen_files
from pydantic import BaseModel, SecretStr
from pydantic.fields import FieldInfo

from app.config.settings import Settings, env_fields, nested_model

DOCKER_VARIABLES = [
    ("IMAGE_REF", "aiogram-app:dev", "Image that `compose.yml` runs; use a released GHCR tag"),
    ("APP_PORT", "8000", "Host port bound on 127.0.0.1"),
]


def type_name(field: FieldInfo) -> str:
    """Format a field type for a Markdown table cell."""
    name = str(field.annotation).replace("typing.", "").replace("pydantic.types.", "")
    return name.replace("<class '", "").replace("'>", "").replace("|", "\\|")


def default_value(field: FieldInfo) -> str:
    """Format a field default for a Markdown table cell."""
    if field.is_required():
        return "required"
    value = field.get_default(call_default_factory=True)
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    return "—" if value is None else f"`{json.dumps(value)}`"


def table(rows: Iterator[tuple[str, FieldInfo]]) -> list[str]:
    """Build a configuration table from setting fields."""
    lines = ["| Variable | Type | Default | Description |", "| --- | --- | --- | --- |"]
    for variable, field in rows:
        description = field.description or ""
        lines.append(
            f"| `{variable}` | `{type_name(field)}` | {default_value(field)} | {description} |"
        )
    return lines


lines = [
    "# Configuration",
    "",
    "This page is generated from `app.config.Settings`. Values are read from `APP_*` "
    "environment variables and `.env`; the process environment wins. Lists use JSON. "
    "Nested storage settings use `__`, for example `APP_REDIS__DSN`.",
    "",
    "## Application",
    "",
]
top_level = {name for name, field in Settings.model_fields.items() if nested_model(field) is None}
lines += table(
    (variable, field)
    for variable, field in env_fields()
    if variable.removeprefix("APP_").lower() in top_level
)
for name, field in Settings.model_fields.items():
    section: type[BaseModel] | None = nested_model(field)
    if section is None:
        continue
    lines += ["", f"## {name}", "", (section.__doc__ or "").strip(), ""]
    lines += [
        "Enabled when its required value is set. Install the matching extra first.",
        "",
    ]
    lines += table(env_fields(section, f"APP_{name.upper()}__"))

lines += [
    "",
    "## Docker Compose",
    "",
    "Read by Compose, not by `Settings`.",
    "",
    "| Variable | Default | Description |",
    "| --- | --- | --- |",
]
lines += [f"| `{name}` | `{default}` | {text} |" for name, default, text in DOCKER_VARIABLES]

with mkdocs_gen_files.open("configuration.md", "w") as fd:
    fd.write("\n".join(lines) + "\n")

mkdocs_gen_files.set_edit_path("configuration.md", "../src/app/config/settings.py")
