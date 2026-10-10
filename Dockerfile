# syntax=docker/dockerfile:1
# Dependabot updates the pinned digest.
ARG PYTHON_IMAGE=python:3.14-alpine3.24@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72

FROM ${PYTHON_IMAGE} AS base
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /usr/local/bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0 PYTHONUNBUFFERED=1

# Keep dependency installation cached across source-only changes.
FROM base AS builder
ARG UV_SYNC_EXTRAS=""
RUN apk add --no-cache build-base
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev $UV_SYNC_EXTRAS
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable $UV_SYNC_EXTRAS

FROM base AS development
RUN apk add --no-cache build-base
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --all-extras
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --all-extras
CMD ["/app/.venv/bin/watchfiles", "--filter", "python", "python -m app.main", "/app/src"]

FROM ${PYTHON_IMAGE} AS production
LABEL org.opencontainers.image.description="Aiogram Telegram bot" \
      org.opencontainers.image.licenses="MIT"
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Only the builder needs pip; its global vendored packages are absent from production.
RUN rm -rf /usr/local/lib/python3.14/site-packages/pip \
    /usr/local/lib/python3.14/site-packages/pip-*.dist-info \
    && adduser -S -D -u 10001 appuser
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('APP_HTTP_PORT', '8000') + '/live', timeout=2)"]
CMD ["python", "-m", "app.main"]
