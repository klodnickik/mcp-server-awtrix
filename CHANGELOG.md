# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
### Changed
### Fixed

## [0.1.0] - 2026-08-24

### Added
- Core Model Context Protocol (MCP) server implementation (`awtrix_mcp.server`) exposing 5 tools: `awtrix_push_app`, `awtrix_notify`, `awtrix_delete_app`, `awtrix_get_device_state`, `awtrix_set_settings`, and `awtrix_test_render`.
- Declarative YAML metric poller daemon (`awtrix-daemon` / `awtrix_mcp.daemon`) with AST-sandboxed expression evaluator, Jinja2 template rendering, sub-app error isolation, and `watchfiles` zero-downtime hot-reload.
- Asynchronous HTTP client (`awtrix_mcp.client.AwtrixClient`) supporting AWTRIX Light 3.x wire protocol with connection timeouts and response validation.
- Multi-architecture Docker packaging (`Dockerfile`, `docker-compose.yml`) with automated `/healthz` check script and non-root execution.
- Comprehensive GitHub Actions CI pipeline in `.github/workflows/ci.yml` running Ruff linting, Mypy type-checking, Pytest across Python 3.10/3.11/3.12 with >=85% coverage enforcement, Docker smoke test, and package build checks.
- Comprehensive developer documentation in `README.md` and `CONTRIBUTING.md`.
