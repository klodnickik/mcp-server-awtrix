# Contributing to MCP Server Awtrix

Welcome! Thank you for considering contributing to `mcp-server-awtrix`. This guide will help you set up your development environment, understand our standards, and successfully submit a pull request.

## Prerequisites

- **Python 3.10+** (tested against 3.10, 3.11, 3.12)
- [**uv**](https://github.com/astral-sh/uv) (recommended package & environment manager) or standard `pip`/`venv`
- **Docker & Docker Compose** (optional, for containerized smoke testing)

## Development Environment Setup

```bash
# Clone repository
git clone https://github.com/klodnickik/mcp-server-awtrix.git
cd mcp-server-awtrix

# Install dependencies and development tools
uv sync --group dev
```

## Running Tests & Quality Gates

We use a suite of tools to maintain code quality. Ensure these pass before opening a PR:

```bash
# Run unit and integration test suite
uv run pytest

# Run tests with code coverage enforcement (>=85% required in CI)
uv run pytest --cov --cov-report=term-missing --cov-fail-under=85

# Run linter checks
uv run ruff check .

# Run code formatter checks
uv run ruff format --check .

# Run type checking
uv run mypy awtrix_mcp docker
```

## Running & Testing the Services Locally

```bash
# Start the MCP Server on STDIO
uv run mcp-server-awtrix

# Validate app manifests
uv run awtrix-daemon validate apps/

# Run daemon locally
uv run awtrix-daemon apps/
```

## Pull Request & Commit Standards

- **Conventional Commits**: We use Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
- **Atomic Commits**: Keep commits atomic with clear descriptions.
- **Changelog**: Document user-facing changes in `CHANGELOG.md` under the `[Unreleased]` section.
- **CI Checks**: Ensure all 5 CI jobs pass (lint, typecheck, test, docker-smoke, package).
