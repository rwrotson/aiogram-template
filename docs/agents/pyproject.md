# Dependencies

- Put runtime imports in `[project].dependencies`, optional backend drivers in the matching extra, development tools in the `dev` group, and documentation tools in the `docs` group.
- Change dependencies through uv (`uv add`, `uv remove`) so `pyproject.toml` and `uv.lock` change together. Verify the lock with `uv sync --locked --all-extras --all-groups`.
- Raise a direct dependency's lower bound when code needs a newer API. The locked environment does not check lower bounds; the CI lowest-direct-dependencies job does.
- Security floors for transitive dependencies go in `[tool.uv] constraint-dependencies`.
- Import-linter contracts in `[tool.importlinter]` enforce the layer boundaries; update them when adding a package or a third-party dependency to a layer.
- Use the project environment for tools. Do not install packages manually into `.venv`.
- `[tool.mypy] files` lists only existing directories (mypy fails on a missing path).
