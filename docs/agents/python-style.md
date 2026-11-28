# Python Style

## Code

- Use absolute `app.` imports. Services, infrastructure, and the Telegram interface follow the import direction in [docs/architecture.md](../architecture.md).
- MyPy runs with `strict = true` over the project. All new code must have complete type annotations. Prefer `X | Y` over `Optional[X]`.

## Python Formatting

- Keep function signatures, calls, and collection literals on one line when they fit. When they need wrapping, put one parameter, argument, or item on each line. Add a trailing comma after the last entry when there are two or more entries so Ruff preserves the layout. Do not enable `COM812`.
- Omit optional trailing commas in single-entry forms. Keep the required comma in a single-element tuple and any comma Ruff inserts in a wrapped signature with one parameter.

## Documentation and Comments

- Keep documentation, docstrings, and comments in English, short and factual. Describe each entity's purpose without editorial commentary or tutorials.
- Do not add module docstrings. Package docstrings in `__init__.py` are allowed. Put package behavior and module details in README, `AGENTS.md`, or `docs/`.
- Give public classes, functions, and methods a docstring. Prefer one line describing their overall purpose; do not repeat names, signatures, or type annotations. Test functions are identified by their names and need no docstrings.
- Add docstrings to protected or private objects only when they explain behavior that is not clear from code.
- Keep inline comments only for non-obvious behavior or decisions. Put a short comment on the relevant line when it fits; otherwise place it immediately above. Retain necessary tool directives such as `# noqa` and `# type: ignore`.
- A comment placed above a line or group of lines applies only to it. Separate that line or group from the code before and after it with a blank line, unless it starts or ends a block, so the comment's scope is clear. At module and class level, give each commented constant or attribute its own block, and keep uncommented related definitions together in one block.
- In long functions, methods, and tests, separate logical steps (input validation, setup, execution, result handling; arrange, act, assert) with a single blank line. Do not add comments to label the steps. Keep short functions compact.
- At module level, keep `UPPER_CASE` constants and lowercase objects (loggers, imported modules, routers, apps) in separate blocks divided by a blank line.
- Prefer clearer names and more precise types over comments that restate code.
- Edit `Settings` field descriptions and source docstrings, then rebuild the docs with ProperDocs; do not edit generated configuration or reference pages.
