# Notes

## Documentation Toolchain

The site is built with [ProperDocs](https://properdocs.org/), a maintained continuation of MkDocs 1.x that reads the same configuration (`properdocs.yml`) and runs MkDocs themes and plugins unchanged. MkDocs 2.0 drops the plugin and theme system, and Material for MkDocs requires `mkdocs<2`, so the `mkdocs` package stays on 1.x as a library dependency of the plugins. Running `properdocs` instead of `mkdocs` also avoids the MkDocs 2.0 warnings printed by Material and the plugins.

[Zensical](https://zensical.org/), the successor to Material for MkDocs, does not support `mkdocs-gen-files` yet; the API reference and configuration pages depend on it.

## Commitizen & Versioning

[Commitizen](https://commitizen-tools.github.io/commitizen/) reads Conventional Commit messages to select the next version and update `CHANGELOG.md`. Its settings are in `pyproject.toml`; the `commit-msg` hook checks Conventional Commit format.

## Renaming the Template

Choose three names before editing: a distribution name (for example, `my-bot`), an import package (`my_bot`), and an environment prefix (`MY_BOT_`). The template ships as `aiogram-app`, `app`, and `APP_`.

1. In `pyproject.toml`, set `[project].name`, the description, authors, keywords, and `[project.urls]`.
2. Change `DISTRIBUTION` in `src/app/main.py` the `APP_NAME` default, and the default image tag in `compose.yml`. Keep the `app` import package unless you rename `src/app/` and `docs/agents/src/app/` and update every `app.` import, `[tool.importlinter]`, coverage, MyPy, Ruff `known-first-party`, `docs/gen_ref_pages.py`, and `docs/gen_config_page.py` together.
3. To change the environment prefix, update `env_prefix` in `src/app/config/settings.py`, `.env.example`, README examples, tests, compose files, and `docs/`.
4. Update `properdocs.yml` (`site_name`, repository links, `edit_uri` if the default branch is not `main`), README, docs, `AGENTS.md`, `docs/agents/`, the copyright holder in `LICENSE`, and the image name in `compose.yml` (the release workflow derives it from the repository).
5. Configure GitHub Pages (Source: "GitHub Actions") and GHCR package access.
6. Replace the demonstration handlers, survey, and `/faq` example with your own features.
7. Regenerate the lockfile with `uv lock`, then run `uv sync --locked --all-extras --all-groups`, `uv run poe check`, and `uv run --all-extras --group docs properdocs build --strict`.
