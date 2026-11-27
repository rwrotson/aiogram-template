# GitHub

- `.github/workflows/ci.yml` runs formatting, lint, import-linter contracts, strict MyPy, pytest with 95% coverage, tests against the lowest allowed direct dependencies, PostgreSQL and Redis integration tests, package, docs, and container builds, the dependency audit, and an image vulnerability scan (trivy). Actions are pinned to commit SHAs and workflow permissions are read-only.
- `.github/workflows/release.yml` runs CI on version tags (`v*`), then publishes an amd64/arm64 image to GHCR and the ProperDocs site to GitHub Pages. Pages Source must be set to "GitHub Actions" (Settings → Pages).
- Dependabot opens weekly PRs for uv dependencies, Docker and Docker Compose files, GitHub Actions, and pre-commit hooks (`.github/dependabot.yml`).
- When tests need an external program, install it in the CI test and lowest-dependency jobs.
- `uv run pre-commit install` installs the hooks; `uv run pre-commit run --all-files` runs them on all files and rewrites files.
