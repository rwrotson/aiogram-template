# Docker and VPS deployment

## Local development

Set a real `APP_BOT_TOKEN` in `.env`, then run:

```bash
docker compose -f compose.yml -f compose.dev.yml up --build
```

The development stage installs all extras and reloads the bot when Python source changes. Add `--profile postgres`, `--profile redis`, `--profile mongodb`, or `--profile clickhouse` to start local backing services. Inside the bot container use the Compose service name instead of `localhost` in storage DSNs.

## Release and VPS

A `v*` tag runs CI, scans a release candidate, publishes an amd64/arm64 image to GHCR, and deploys the ProperDocs site to GitHub Pages. Set repository variable `UV_SYNC_EXTRAS` to flags such as `--extra redis` before tagging when production needs optional clients. The default image has core dependencies only. The VPS update is manual.

On the VPS, place `compose.yml` beside a private `.env` file. Set `IMAGE_REF` to the released GHCR image, `APP_ENVIRONMENT=production`, `APP_BOT_TOKEN`, and any storage settings. Then run:

```bash
docker compose pull
docker compose up -d
docker compose ps
curl http://127.0.0.1:8000/ready
```

The operational port is published only on `127.0.0.1:${APP_PORT:-8000}` of the host. The container healthcheck uses `/live`; use `/ready` to inspect Telegram and storage availability. Logs go to stdout with rotation. The container runs as a non-root user with a read-only root filesystem and a `/tmp` tmpfs.

Polling handles at most `APP_POLLING_MAX_CONCURRENT_UPDATES` updates at once (100 by default). On shutdown, the bot gives active handlers `APP_SHUTDOWN_GRACE_SECONDS` (15 seconds by default) to finish, then cancels them before closing their dependencies. Keep this interval below Compose's 30-second `stop_grace_period`.

For polling, no public HTTP route is required. For webhook mode, set `APP_UPDATE_MODE=webhook`, a public `APP_WEBHOOK_URL` with HTTPS and a dedicated path, and `APP_WEBHOOK_SECRET`. Configure a TLS reverse proxy to forward only that path to the localhost port. For example:

```caddyfile
bot.example.com {
    @telegram path /telegram/hook
    reverse_proxy @telegram 127.0.0.1:8000
    respond 404
}
```

The Telegram secret header is validated by the bot's webhook handler. Keep `/live`, `/ready`, and `/metrics` off the public route; scrape metrics through a private path or locally. Polling and webhook must not run simultaneously for the same token. To roll back, set `IMAGE_REF` to an earlier tag and repeat the pull/up commands.
