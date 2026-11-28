# Configuration

- `src/app/config/settings.py` defines Pydantic Settings loaded from `APP_*` environment variables and `.env`, with defaults in code.
- Storage settings are nested models, set with the `__` delimiter (`APP_REDIS__DSN`). Secrets use `SecretStr`.
- Every setting must appear in `.env.example`; a test enforces it. Update README and the docs when a public setting changes.
- A setting that holds a credential also gets a README "Credentials" section that says where to obtain it and how to set it.
- Models used as default argument values must be frozen; register them in `[tool.ruff.lint.flake8-bugbear] extend-immutable-calls` in `pyproject.toml`.
- The docs configuration page is generated from `Settings`; edit field descriptions, not the page.
- Settings are scoped to the application: pass the object into `create_app()` and never read the environment elsewhere.
- Ruff `banned-api` bans `os.environ`, `os.getenv` and `os.putenv` outside `src/app/config/` and `tests/`.
