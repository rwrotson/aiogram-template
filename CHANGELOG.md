# Changelog

All notable changes to the Aiogram template will be documented here.

## v0.1.1 (2026-10-10)

- Use an Alpine 3.24 Python image for production and remove unused global pip packages to clear HIGH and CRITICAL image scan findings.
- Install build tools in build stages so optional storage dependencies remain available.

## v0.1.0 (2026-10-08)

- Initial Aiogram bot template with optional storage clients, telemetry, Docker, CI, and documentation.
