# Feature: Fix Docker Compose and Dockerfile Wiring with Health Check Verification

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Fix and verify Docker Compose and Dockerfile configuration wiring for both `mcp-server` and `metric-daemon` container roles. Specifically:
1. Align the default `Dockerfile` `CMD` and `CONTAINER_ROLE` to run the MCP server over SSE with documented inline rationale, while `docker-compose.yml` configures each service explicitly (`mcp-server` and `metric-daemon`).
2. Verify `--apps-dir` CLI argument parsing in `awtrix_mcp/daemon.py` for background metric daemon operations and manifest validation.
3. Validate and ensure full test coverage for the mode-aware health check (`docker/healthcheck.py`) probing HTTP `/health` for `mcp-server` and heartbeat file freshness for `metric-daemon`, ensuring no exit masking (`|| exit 0`).

## User Story

```markdown
As a developer deploying mcp-server-awtrix via Docker or Docker Compose
I want the Dockerfile default CMD and health checks for both mcp-server and metric-daemon services to reflect real service status without masking errors
So that docker compose ps accurately reports service health and neither service gets trapped in a silent failure or restart loop
```

## Problem Statement

Earlier Docker and Compose configurations had wiring bugs and assumptions:
1. `Dockerfile` defaulted its `CMD` and `CONTAINER_ROLE` to `metric-daemon`, which was counter-intuitive for users running the MCP server container directly via `docker run`.
2. Health check probing in `docker-compose.yml` previously masked failures using `|| exit 0` and probed endpoints without a verified SSE `/health` route on the MCP server.
3. `daemon.py` needed CLI argument parsing for `--apps-dir` so background runs and manifest validation commands can configure the apps directory cleanly.

## Solution Statement

1. **Dockerfile Default Alignment**: Update `Dockerfile` to default `CONTAINER_ROLE=mcp-server` and `CMD ["python", "-m", "awtrix_mcp.server", "--transport", "sse", "--host", "0.0.0.0", "--port", "8000"]` with clear explanatory comments describing that `docker-compose.yml` overrides command/role for the `metric-daemon` service.
2. **Compose Configuration Verification**: Ensure `docker-compose.yml` defines `mcp-server` and `metric-daemon` with explicit roles, volume mounts (`./apps:/app/apps:ro`), environment variables, and health checks referencing `docker/healthcheck.py` without exit code masking.
3. **CLI Arguments & Endpoint Tests**: Verify and add targeted unit tests in `tests/test_server.py` for the `/health` endpoint and in `tests/test_daemon.py` for `--apps-dir` argument parsing.
4. **Health Check Verification**: Verify `tests/test_healthcheck.py` covers role dispatching (`mcp-server` HTTP check and `metric-daemon` heartbeat check), timeout handling, missing files, and stale heartbeat detection.

## Out of Scope / Non-Goals

- Implementing new metric poller engine features (completed in #12).
- Implementing new MCP tools or display features.
- Dynamic multi-host Docker Swarm or Kubernetes helm charts.

## Feature Metadata

- **Feature Type**: Bug Fix / Configuration Hardening
- **Estimated Complexity**: Low
- **Primary Systems Affected**: `Dockerfile`, `docker-compose.yml`, `awtrix_mcp/daemon.py`, `awtrix_mcp/server.py`, `docker/healthcheck.py`, `tests/`
- **Dependencies**: `starlette`, `pydantic`, `httpx`

## Related Work

- **Implements**: GitHub Issue [#13](https://github.com/klodnickik/mcp-server-awtrix/issues/13)
- **Back-references**:
  - [PR #12](https://github.com/klodnickik/mcp-server-awtrix/issues/12) / [PR #15](https://github.com/klodnickik/mcp-server-awtrix/pull/15) - Declarative YAML metric poller daemon core engine
- **Forward-references**: None

---

## CONTEXT REFERENCES

### Relevant Codebase Files IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- `Dockerfile` (lines 35-55) - Base runtime image configuration, environment defaults, health check, and default CMD.
- `docker-compose.yml` (lines 1-57) - Service definitions for `mcp-server` and `metric-daemon`.
- `docker/healthcheck.py` (lines 1-46) - Mode-aware container healthcheck for `mcp-server` and `metric-daemon`.
- `awtrix_mcp/server.py` (lines 160-194) - MCP server definition, `/health` route, and CLI entrypoint.
- `awtrix_mcp/daemon.py` (lines 270-299) - Metric poller daemon CLI entrypoint and `--apps-dir` parser.
- `tests/test_healthcheck.py` (lines 1-74) - Health check unit tests.
- `tests/test_server.py` (lines 1-200) - Server unit tests and route testing.
- `tests/test_daemon.py` (lines 1-400) - Daemon unit tests and CLI parser testing.

### New Files to Create

None (existing files will be refined and tested).

### Patterns to Follow

**Argparse CLI Pattern:**
In `awtrix_mcp/daemon.py`:
```python
parser = argparse.ArgumentParser(prog="awtrix-daemon")
parser.add_argument("--apps-dir", type=Path, default=Path(os.environ.get("APPS_DIR", "apps")))
```

**Custom Route in MCPServer:**
In `awtrix_mcp/server.py`:
```python
@server.custom_route("/health", methods=["GET"])
async def health_check(_request: Request) -> Response:
    return JSONResponse({"status": "ok"})
```

**Container Healthcheck Dispatching:**
In `docker/healthcheck.py`:
```python
def main() -> int:
    role = os.environ.get("CONTAINER_ROLE", "mcp-server")
    healthy = _check_mcp_server() if role == "mcp-server" else _check_metric_daemon()
    return 0 if healthy else 1
```

---

## IMPLEMENTATION PLAN

### Phase 1: Dockerfile and Compose Alignment

Align `Dockerfile` default runtime parameters (`CONTAINER_ROLE`, `CMD`) to MCP server over SSE, with inline explanatory comments. Ensure `docker-compose.yml` service configurations are explicit and unmasked.

### Phase 2: Server and Daemon CLI Test Verification

Verify and add explicit test coverage for:
1. `GET /health` endpoint on `MCPServer` in `tests/test_server.py`.
2. Daemon CLI `--apps-dir` argument parsing and fallback in `tests/test_daemon.py`.
3. Health check script role dispatching and error conditions in `tests/test_healthcheck.py`.

### Phase 3: Validation and Documentation

Run all linters (`ruff`, `mypy`) and full pytest test suite, and ensure `README.md` Docker documentation accurately reflects the container defaults.

---

## STEP-BY-STEP TASKS

### UPDATE Dockerfile

- **IMPLEMENT**:
  1. Set default `CONTAINER_ROLE=mcp-server`.
  2. Set default `CMD ["python", "-m", "awtrix_mcp.server", "--transport", "sse", "--host", "0.0.0.0", "--port", "8000"]`.
  3. Add clear comments explaining that the image defaults to the MCP server over SSE and that `docker-compose.yml` overrides `CMD` and `CONTAINER_ROLE` for `metric-daemon`.
- **PATTERN**: `Dockerfile:40-55`
- **VALIDATE**: `.venv/bin/ruff check .`
- **SATISFIES**: AC #2, AC #3

### UPDATE awtrix_mcp/daemon.py (if needed) & tests/test_daemon.py

- **IMPLEMENT**: Add explicit unit tests verifying `awtrix-daemon` CLI parses `--apps-dir` (custom path, env var fallback, default `apps`) and dispatches correctly.
- **PATTERN**: `tests/test_daemon.py:30-60`
- **VALIDATE**: `.venv/bin/pytest tests/test_daemon.py -k cli`
- **SATISFIES**: AC #1

### UPDATE tests/test_server.py

- **IMPLEMENT**: Add test for `GET /health` endpoint verifying that starlette route returns HTTP 200 `{"status": "ok"}`.
- **PATTERN**: `tests/test_server.py:1-50`
- **VALIDATE**: `.venv/bin/pytest tests/test_server.py -k health`
- **SATISFIES**: AC #2

### UPDATE tests/test_healthcheck.py

- **IMPLEMENT**: Ensure tests cover both `CONTAINER_ROLE=mcp-server` (default) and `CONTAINER_ROLE=metric-daemon`, checking connection errors, 200 OK, missing heartbeat file, and stale heartbeat file.
- **PATTERN**: `tests/test_healthcheck.py:1-74`
- **VALIDATE**: `.venv/bin/pytest tests/test_healthcheck.py`
- **SATISFIES**: AC #2

---

## TESTING STRATEGY

### Unit Tests
- `tests/test_healthcheck.py`: Verify HTTP check against mock server / error raising, heartbeat file existence and timestamp freshness.
- `tests/test_server.py`: Verify `/health` route status 200 response and JSON payload.
- `tests/test_daemon.py`: Verify CLI argument parser correctly parses `--apps-dir`.

### Integration Tests
- Full test suite execution (`.venv/bin/pytest`) ensuring zero regressions across all components.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```bash
.venv/bin/ruff check .
.venv/bin/mypy awtrix_mcp docker tests
```

### Level 2: Unit Tests
```bash
.venv/bin/pytest tests/test_healthcheck.py tests/test_server.py tests/test_daemon.py
```

### Level 3: Full Test Suite
```bash
.venv/bin/pytest
```

---

## ACCEPTANCE CRITERIA

- [ ] `docker-compose.yml` does not restart-loop either service.
- [ ] `docker/healthcheck.py` reflects real MCP server health (HTTP 200 on `/health`) and metric daemon health (fresh heartbeat file), not a hardcoded pass.
- [ ] `Dockerfile`'s default `CMD` and `CONTAINER_ROLE` default to the MCP server with clear documentation comments, matching what `docker-compose.yml` expects.
- [ ] Daemon CLI `--apps-dir` argument parsing is covered by unit tests.
- [ ] All unit tests pass and linters (`ruff`, `mypy`) report zero errors.

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order
- [ ] Each task validation passed immediately
- [ ] All validation commands executed successfully
- [ ] Full test suite passes (116+ tests)
- [ ] No linting or type checking errors
- [ ] Acceptance criteria all met

---

## OPEN QUESTIONS / ASSUMPTIONS

- **Assumption 1**: Docker binary is not available in the CI/container sandbox environment; therefore end-to-end smoke testing is verified via unit tests, docker-compose configuration validation, and python healthcheck simulation.
