# Deployment

- The production image (`Dockerfile`) runs one bot process and logs to stdout. Keep the base image and its vulnerability scan clean.
- `compose.yml` binds the operational aiohttp port to localhost on the VPS and rotates container logs. `compose.dev.yml` adds source reload and optional database profiles.
- An external TLS reverse proxy forwards only the configured webhook path and blocks public access to `/metrics`, `/ready`, and `/live`.
- The VPS update is manual: pull the tagged image and restart the container.
- Keep `.env` and tokens untracked. Update `docs/deployment.md` and README when deployment instructions change.
