# Docs

- The site is built with ProperDocs from `docs/` and `properdocs.yml`. Check changes with `uv run --all-extras --group docs properdocs build --strict`. See the [toolchain notes](../notes.md#documentation-toolchain).
- `docs/gen_ref_pages.py` generates API pages from source modules. `docs/gen_config_page.py` builds the configuration page from `Settings`.
- Do not edit generated pages (configuration, API reference); edit `Settings` field descriptions and source docstrings instead.
- The generator scripts are type-checked with the rest of the project.
- Update README, `.env.example`, and the docs when changing public settings, commands, storage extras, or deployment instructions.
- When renaming or removing a module, setting, or task, search `AGENTS.md` and `docs/agents/` for it and update the references.
