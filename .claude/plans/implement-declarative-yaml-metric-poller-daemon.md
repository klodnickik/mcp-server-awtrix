# Feature: Declarative YAML Metric Poller Daemon (Core Engine Hardening & Completion)

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

The declarative YAML metric poller daemon (`awtrix-daemon`) provides automated, background metric polling and carousel app synchronization for Awtrix Light / Ulanzi TC001 pixel displays. It continuously watches an `apps/` directory for YAML manifests, fetches remote HTTP endpoints on configured intervals, evaluates data transformations using a restricted Python AST evaluator, renders Jinja2 multi-segment colored text payloads based on threshold display conditions or multi-metric sub-apps, pushes payloads to the device via `AwtrixClient`, and hot-reloads manifests without restarting the process.

This feature plan covers auditing, hardening, and verifying the core engine against all specifications and acceptance criteria in GitHub Issue [#12](https://github.com/klodnickik/mcp-server-awtrix/issues/12).

## User Story

```markdown
As a developer or home automation enthusiast with an Awtrix Light pixel clock
I want to define metric polling rules in declarative YAML files under apps/
So that the background daemon automatically fetches APIs, computes metrics, and updates my display without writing custom boilerplate code
```

## Problem Statement

Users of Awtrix Light clocks often have to write bespoke cron scripts and custom API wrappers to display live metrics (e.g. CI/CD test results, revenue, open support tickets). A background daemon must reliably parse YAML manifests, securely resolve environment secrets, evaluate expressions safely without arbitrary code execution vulnerabilities, schedule non-blocking polling jobs, isolate errors across individual apps and sub-apps, and hot-reload on file edits.

While the foundational daemon infrastructure was introduced in earlier PRs, the system requires end-to-end audit, per-item sub-app error isolation hardening, rigorous edge-case testing, and full verification against Issue #12's acceptance criteria.

## Solution Statement

1. **Per-Item Sub-App Error Isolation**: Update `_run_sub_apps` in [awtrix_mcp/daemon.py](file:///home/klodnicki_k/mcp-server-awtrix/awtrix_mcp/daemon.py) to wrap each individual sub-app render and push in its own exception handling block, ensuring that an error in one sub-app (e.g. invalid template syntax or missing field) does not halt the evaluation and push of subsequent sub-apps.
2. **Resilience & Cycle-Skip Polling**: Maintain the non-blocking cycle-skip model where failed HTTP fetches log a warning and retry on the next interval tick without crashing or stalling other scheduled jobs.
3. **AST Evaluator Security**: Maintain the safe, AST-whitelisted restricted evaluator in [awtrix_mcp/evaluator.py](file:///home/klodnicki_k/mcp-server-awtrix/awtrix_mcp/evaluator.py) protecting against dunder attribute access, reflective format attacks, and unconstrained comprehensions.
4. **Validation CLI & Hot-Reload**: Ensure `awtrix-daemon validate` and `watchfiles` directory monitoring accurately process single-app (`display`) and multi-metric (`sub_apps`) schemas.
5. **Comprehensive Test Suite**: Add tests specifically covering per-item sub-app failure isolation, manifest schema variations, and verify that the full test suite passes with 100% clean linting and typing.

## Out of Scope / Non-Goals

- **MQTT transport layer**: REST API is used; MQTT transport remains a separate roadmap item.
- **Live web matrix pixel preview**: Web UI preview is a separate roadmap item.
- **Changes to docker-compose.yml / Dockerfile**: Existing health check and compose configs remain unchanged.
- **In-process retry / exponential backoff loops on source fetch**: Polling tasks skip the failed cycle and retry at the next scheduled interval per the README NFR.

## Feature Metadata

- **Feature Type**: Enhancement / Hardening & Verification
- **Estimated Complexity**: Medium
- **Primary Systems Affected**: `awtrix_mcp/daemon.py`, `awtrix_mcp/config.py`, `awtrix_mcp/evaluator.py`, `tests/test_daemon.py`, `README.md`
- **Dependencies**: `apscheduler>=3.10.4`, `httpx>=0.27.0`, `jinja2>=3.1.4`, `pyyaml>=6.0.1`, `watchfiles>=0.21.0`, `pydantic>=2.7.0`, `pydantic-settings>=2.2.0`

## Related Work

- **Implements**: GitHub Issue [#12](https://github.com/klodnickik/mcp-server-awtrix/issues/12)
- **Back-references**:
  - [PR #9](https://github.com/klodnickik/mcp-server-awtrix/pull/9) - Phase 3 Declarative YAML Engine & Background Metric Poller
  - [PR #11](https://github.com/klodnickik/mcp-server-awtrix/pull/11) - CLI validate subcommand and CI pipeline
- **Forward-references**: None

---

## CONTEXT REFERENCES

### Relevant Codebase Files IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- [awtrix_mcp/daemon.py](file:///home/klodnicki_k/mcp-server-awtrix/awtrix_mcp/daemon.py#L58-L138) (lines 58–138, 167–216) - Poller execution, display rules, sub-apps execution, and hot-reload.
- [awtrix_mcp/config.py](file:///home/klodnicki_k/mcp-server-awtrix/awtrix_mcp/config.py#L34-L136) (lines 34–136) - Secret substitution (`resolve_secrets`), schema models (`ManifestConfig`, `SourceConfig`, `DisplayRule`, `SubAppConfig`), and `load_manifest`.
- [awtrix_mcp/evaluator.py](file:///home/klodnicki_k/mcp-server-awtrix/awtrix_mcp/evaluator.py#L89-L246) (lines 89–246) - Restricted AST evaluator (`evaluate_expression`, `evaluate_condition`) and sandboxed template renderer (`render_template`).
- [awtrix_mcp/client.py](file:///home/klodnicki_k/mcp-server-awtrix/awtrix_mcp/client.py#L40-L130) (lines 40–130) - `AwtrixClient` methods (`send_app`, `send_notification`, `delete_app`).
- [apps/checkly.yaml](file:///home/klodnicki_k/mcp-server-awtrix/apps/checkly.yaml) - Reference single-app manifest with transforms and display conditions.
- [apps/saas_metrics.yaml](file:///home/klodnicki_k/mcp-server-awtrix/apps/saas_metrics.yaml) - Reference multi-app manifest with `sub_apps` and `show_if` filters.
- [tests/test_daemon.py](file:///home/klodnicki_k/mcp-server-awtrix/tests/test_daemon.py) - Existing daemon unit & integration tests.
- [tests/test_evaluator.py](file:///home/klodnicki_k/mcp-server-awtrix/tests/test_evaluator.py) - Evaluator AST sandbox and security tests.
- [tests/test_config.py](file:///home/klodnicki_k/mcp-server-awtrix/tests/test_config.py) - Manifest parsing and secret resolution tests.

### New Files to Create

- None (all changes are modifications and extensions of existing modules and tests).

### Relevant Documentation YOU SHOULD READ THESE BEFORE IMPLEMENTING!

- [APScheduler 3.x AsyncIOScheduler Documentation](https://apscheduler.readthedocs.io/en/3.x/modules/schedulers/asyncio.html)
  - Section: `AsyncIOScheduler` job management (`add_job`, `remove_job`, `replace_existing`)
  - Why: Used for per-manifest asynchronous interval scheduling.
- [Watchfiles Documentation](https://watchfiles.helpmanual.io/)
  - Section: `awatch` asynchronous file system watcher
  - Why: Used for zero-downtime hot-reload of the `apps/` directory.
- [Jinja2 SandboxedEnvironment Documentation](https://jinja.palletsprojects.com/en/3.1.x/sandbox/)
  - Section: Safe string template rendering with `StrictUndefined`
  - Why: Prevents template injection vulnerabilities while rendering metric text.

### Patterns to Follow

**Error Handling & Logging Pattern:**
```python
# In awtrix_mcp/daemon.py
try:
    # Action
    ...
except (ExpressionError, AwtrixError) as exc:
    logger.warning("sub-app push failed for %s (%s): %s", sub.name, manifest.app_id, exc)
```

**Pydantic Model Extra Attributes Forbidden:**
```python
# In awtrix_mcp/config.py
class DisplayRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    condition: str
    icon: str | None = None
    notify: bool = False
    text: list[TemplateTextSegment]
```

**AST Node Evaluation Handler:**
```python
# In awtrix_mcp/evaluator.py
def _eval_Constant(self, node: ast.Constant, _scope: dict) -> Any:  # pylint: disable=invalid-name
    return node.value
```

---

## IMPLEMENTATION PLAN

### Phase 1: Sub-App Fault Isolation Hardening
**Depends on:** None (builds on existing daemon baseline)

Isolate errors within `_run_sub_apps` so that a failure in one sub-app does not stop or discard the execution of other sub-apps defined in the same manifest.

**Tasks:**
- Refactor `_run_sub_apps` in [awtrix_mcp/daemon.py](file:///home/klodnicki_k/mcp-server-awtrix/awtrix_mcp/daemon.py) to wrap each sub-app loop iteration in a `try...except (ExpressionError, AwtrixError)` block.
- Ensure error messages clearly log the sub-app name, manifest `app_id`, and exception details.
- Clean up `poll_once` handling so display rules and sub-apps errors are handled cleanly.

### Phase 2: Test Suite Hardening & Regression Verification
**Depends on:** Phase 1

Add regression tests in [tests/test_daemon.py](file:///home/klodnicki_k/mcp-server-awtrix/tests/test_daemon.py) verifying that a failure in one sub-app allows remaining sub-apps to proceed.

**Tasks:**
- Add `test_poll_once_sub_app_partial_failure_continues_remaining_sub_apps` in `tests/test_daemon.py`.
- Add test verifying that both `display` and `sub_apps` rules within the same cycle execute independently.
- Verify manifest validation CLI tests for all existing example manifests (`checkly.yaml` and `saas_metrics.yaml`).

### Phase 3: Acceptance Criteria & Documentation Verification
**Depends on:** Phase 2

Verify all acceptance criteria from Issue #12, check typing and linting, and confirm roadmap accuracy in [README.md](file:///home/klodnicki_k/mcp-server-awtrix/README.md).

**Tasks:**
- Validate `README.md` roadmap and PRD references.
- Run full test suite and code quality checks (`pytest`, `ruff`, `mypy`).

---

## STEP-BY-STEP TASKS

### UPDATE `awtrix_mcp/daemon.py`

- **IMPLEMENT**: Wrap each sub-app processing step in `_run_sub_apps` in a try-except block catching `(ExpressionError, AwtrixError)` and logging a warning with the sub-app name and `app_id`. In `poll_once`, update error handling so that display rules and sub-apps errors are logged independently.
- **PATTERN**: [awtrix_mcp/daemon.py:107-114](file:///home/klodnicki_k/mcp-server-awtrix/awtrix_mcp/daemon.py#L107-L114)
- **IMPORTS**: `from .evaluator import AttrDict, ExpressionError, evaluate_condition, evaluate_expression, render_template`, `from .client import AwtrixClient, AwtrixError`
- **GOTCHA**: Do not catch bare `Exception` — only catch `ExpressionError` (template/condition failure) and `AwtrixError` (device HTTP/network failure) so bugs or cancellation errors are not swallowed.
- **VALIDATE**: `pytest tests/test_daemon.py -k test_poll_once`
- **SATISFIES**: AC #3 (A malformed manifest or a failing source logs a clear error and does not crash the daemon or block other apps' polling).

### ADD `tests/test_daemon.py`

- **IMPLEMENT**: Add unit tests:
  1. `test_poll_once_sub_app_partial_failure_continues_remaining`: A multi-sub-app manifest where the first sub-app references a non-existent field in its template (raising `ExpressionError`) and the second sub-app renders valid text. Verify the second sub-app successfully calls `send_app`.
  2. `test_poll_once_sub_app_device_error_continues_remaining`: A multi-sub-app manifest where the first sub-app's POST request to `/api/custom` returns HTTP 500 (`AwtrixResponseError`) and the second sub-app's POST succeeds (HTTP 200). Verify the second sub-app is sent.
- **PATTERN**: [tests/test_daemon.py:356-374](file:///home/klodnicki_k/mcp-server-awtrix/tests/test_daemon.py#L356-L374)
- **IMPORTS**: `import respx`, `import httpx`, `import pytest`, `from awtrix_mcp.daemon import poll_once`
- **GOTCHA**: Ensure mock endpoints use distinct query parameters `params={"name": "app_users"}` vs `params={"name": "app_orders"}` so calls can be asserted independently.
- **VALIDATE**: `pytest tests/test_daemon.py -k sub_app`
- **SATISFIES**: AC #3, AC #4 (Unit tests verify error isolation across sub-apps).

### UPDATE `README.md`

- **IMPLEMENT**: Verify that the Roadmap section in `README.md` correctly has `[x] Declarative YAML orchestration schema` checked, and that the instructions for running `awtrix-daemon` and `awtrix-daemon validate` match the implementation.
- **PATTERN**: [README.md:362-375](file:///home/klodnicki_k/mcp-server-awtrix/README.md#L362-L375)
- **GOTCHA**: Ensure no broken links or outdated command-line flag examples.
- **VALIDATE**: Review markdown links and command syntax.
- **SATISFIES**: AC #5 (README roadmap accurately reflects what's shipped).

---

## TESTING STRATEGY

### Unit Tests
- **Manifest Loading & Secret Resolution**: Verify `${VAR}` substitution, missing secret errors, schema validation, and reject unknown top-level keys (`tests/test_config.py`).
- **Expression Evaluator & Sandbox**: Verify AST evaluation of arithmetic, comparisons, builtins (`len`, `sum`, `min`, `max`), generator expressions, `AttrDict` dot-access, `StrictUndefined` Jinja2 template errors, and dunder/reflective security boundaries (`tests/test_evaluator.py`).
- **Daemon Lifecycle & Scheduling**: Verify `AsyncIOScheduler` interval scheduling, manifest modification rescheduling, manifest removal app deletion, duplicate `app_id` rejection, disabled manifest unscheduling, and heartbeat touches (`tests/test_daemon.py`).
- **Sub-App Fault Isolation**: Verify single sub-app template or network failures do not block subsequent sub-apps (`tests/test_daemon.py`).
- **Validation CLI**: Verify `awtrix-daemon validate [file]` and `awtrix-daemon --apps-dir <dir> validate` with valid, invalid, duplicate, and missing files (`tests/test_daemon.py`).

### Integration Tests
- Verify end-to-end polling of `apps/checkly.yaml` and `apps/saas_metrics.yaml` with mock HTTP API responses and mock Awtrix device endpoints via `respx`.

### Edge Cases
- HTTP source returns invalid/non-JSON response (must log and skip).
- HTTP source returns 4xx/5xx status code (must log and skip).
- Jinja2 template references missing attribute under `StrictUndefined` (must catch `ExpressionError` and skip without crashing).
- Sub-app in multi-app manifest fails while sibling sub-apps succeed (sibling sub-apps must proceed).
- Duplicate `app_id` in newly added YAML file during hot-reload (must log warning and keep original).
- Manifest file unreadable / OS error during reload (must log warning and continue watching).

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```bash
ruff check .
ruff format --check .
```

### Level 2: Unit Tests
```bash
pytest tests/test_config.py tests/test_evaluator.py tests/test_daemon.py -v
```

### Level 3: Integration Tests
```bash
pytest tests/ -v --cov=awtrix_mcp --cov-report=term-missing
```

### Level 4: Manifest Validation CLI
```bash
python -m awtrix_mcp.daemon validate apps/checkly.yaml
python -m awtrix_mcp.daemon validate apps/saas_metrics.yaml
python -m awtrix_mcp.daemon --apps-dir apps validate
```

### Level 5: Type Checking
```bash
mypy awtrix_mcp tests
```

---

## ACCEPTANCE CRITERIA

- [ ] Running `awtrix-daemon --apps-dir apps/` polls `apps/checkly.yaml` and `apps/saas_metrics.yaml` and pushes updates to the device.
- [ ] Adding, editing, or removing a YAML file under a watched `apps/` directory is reflected without restarting the process.
- [ ] A malformed manifest or a failing HTTP source logs a clear error and does not crash the daemon or block other apps' polling.
- [ ] An error rendering or sending one sub-app in a multi-app manifest does not prevent sibling sub-apps from executing.
- [ ] All unit and integration tests pass under `pytest`.
- [ ] Linting (`ruff`) and type checking (`mypy`) pass with zero errors.
- [ ] `README.md` accurately documents the declarative daemon, validation CLI, and roadmap status.

---

## COMPLETION CHECKLIST

- [ ] Sub-app isolation implemented in `_run_sub_apps`
- [ ] Unit tests added for sub-app partial failure scenarios
- [ ] All existing test suites pass (`test_client`, `test_config`, `test_daemon`, `test_evaluator`, `test_server`, `test_models`)
- [ ] Manifest validation CLI tested against `apps/checkly.yaml` and `apps/saas_metrics.yaml`
- [ ] Zero lint/typecheck errors
- [ ] Acceptance criteria verified against Issue #12

---

## OPEN QUESTIONS / ASSUMPTIONS

- **Assumption 1**: Source fetch errors skip the current poll cycle and retry on the next scheduled interval tick as specified in the README NFR.
- **Assumption 2**: Manifest validation via CLI (`validate`) strictly checks referenced environment variables, requiring defined secrets in `.env` or the environment.

## NOTES (open canvas)

### Fault Isolation Architecture

```
                       poll_once(manifest)
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
       fetch_source() (HTTP)           _build_context() (AST Transform)
        - On error: log & abort         - On error: log & abort
               │                               │
               └───────────────┬───────────────┘
                               │ (Valid Context)
               ┌───────────────┴───────────────┐
               ▼                               ▼
     _run_display_rules()              _run_sub_apps()
      - Match rule                     - For each sub_app:
      - Render & push                   ┌────────────────────────────┐
      - On error: log & abort           │ try:                       │
                                        │   evaluate show_if         │
                                        │   render & send_app        │
                                        │ except:                    │
                                        │   log warning & continue   │
                                        └────────────────────────────┘
```

By isolating individual sub-apps inside `_run_sub_apps`, transient issues or misconfigured templates in one metric do not take down the entire multi-metric dashboard.

## AMENDMENTS

*(Leave empty at creation)*
