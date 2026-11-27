# Dependencies

- Put runtime imports in `[project].dependencies`, optional backend drivers in the matching extra, development tools in the `dev` group, and documentation tools in the `docs` group.
- Change dependencies through uv (`uv add`, `uv remove`) so `pyproject.toml` and `uv.lock` change together. Verify the lock with `uv sync --locked --all-extras --all-groups`.
- Raise a direct dependency's lower bound when code needs a newer API. The locked environment does not check lower bounds; the CI lowest-direct-dependencies job does.
- Security floors for transitive dependencies go in `[tool.uv] constraint-dependencies`.
- Import-linter contracts in `[tool.importlinter]` enforce the layer boundaries; update them when adding a module, a package, or a third-party dependency.
- Add every new module to its package's exhaustive `layers` contract; derive the order from real imports and `lint-imports` feedback, not by loosening a contract.
- Update the "Transitive dependencies are not imported directly" list from `uv.lock` when dependencies change: list the importable top-level names of packages that are not direct dependencies (skip namespace packages such as `opentelemetry` and `google`). A package promoted to a direct dependency leaves the list.
- Use the project environment for tools. Do not install packages manually into `.venv`.
- `[tool.mypy] files` lists only existing directories (mypy fails on a missing path).
