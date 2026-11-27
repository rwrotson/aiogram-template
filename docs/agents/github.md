# GitHub

- `.github/workflows/ci.yml` runs formatting, lint, import-linter contracts, strict MyPy, pytest with 95% coverage, tests against the lowest allowed direct dependencies, PostgreSQL and Redis integration tests, package, docs, and container builds, the dependency audit, and a trivy filesystem scan in the build job, and a trivy image scan. Actions are pinned to commit SHAs and workflow permissions are read-only.
- `.github/workflows/release.yml` runs CI on version tags (`v*`) and on manual `workflow_dispatch`, then:
    - **`image`** — on tags, checks that the tag matches `uv version --short`; builds and trivy-scans a release candidate; on tags only, logs in to GHCR and publishes the amd64/arm64 image. Manual runs build and scan without pushing.
    - **`docs`** — version tags only (the `github-pages` environment accepts only `v*` tags); builds the ProperDocs site and deploys it to GitHub Pages. The Pages artifact is named `github-pages-<run_attempt>` because reruns keep earlier attempts' artifacts and `deploy-pages` rejects duplicate names.
    - Pages Source must be set to "GitHub Actions" (Settings → Pages), and the `github-pages` environment must allow the `v*` tag.
- Dependabot opens weekly PRs for uv dependencies, Docker and Docker Compose files, GitHub Actions, and pre-commit hooks (`.github/dependabot.yml`).
- When tests need an external program, install it in the CI test and lowest-dependency jobs.
- `uv run pre-commit install` installs the hooks; `uv run pre-commit run --all-files` runs them on all files and rewrites files.
