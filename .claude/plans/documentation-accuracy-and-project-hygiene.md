# Feature: Documentation Accuracy and Project Hygiene (CONTRIBUTING, CHANGELOG, CI & README)

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

This feature addresses documentation accuracy, developer ergonomics, and project hygiene gaps across the `mcp-server-awtrix` repository. Specifically, it introduces standard project documentation (`CONTRIBUTING.md` and `CHANGELOG.md`), corrects hardware caveats and roadmap milestone statuses in `README.md`, and confirms that the automated GitHub Actions CI test suite enforces code quality and unit test execution across all supported Python versions.

## User Story

```markdown
As a contributor or developer integrating mcp-server-awtrix
I want accurate API/telemetry documentation, explicit contribution guidelines, a transparent changelog, and automated CI test enforcement
So that I understand real-world hardware responses, can set up a local development environment quickly, and can contribute high-quality changes with confidence
```

## Problem Statement

1. **Unconfirmed Hardware Telemetry in Documentation**: `README.md`'s `awtrix_get_device_state` and `awtrix_set_settings` tool examples present fields such as `charging`, `active_app`, and `transitions` without caveats, despite them being flagged in `awtrix_mcp/models.py` (`DeviceStats` and `DeviceSettings`) as `# unconfirmed on real hardware`. Users debugging `null` or omitted responses on physical devices could be misled.
2. **Roadmap Discrepancies**: The roadmap in `README.md` previously tracked declarative engine items loosely without reflecting actual completed implementation milestones (such as `awtrix-daemon` background polling, AST expression sandboxing, sub-app fault isolation, and Docker packaging).
3. **Missing Developer Onboarding Guide**: The repository invites contributions in `README.md` but lacks a root `CONTRIBUTING.md` defining development environment setup (`uv sync --group dev`), linting (`ruff`), type-checking (`mypy`), testing (`pytest`), and PR expectations.
4. **Missing Changelog**: No `CHANGELOG.md` exists to track changes across versions (currently `0.1.0` per `pyproject.toml`) following standard formatting conventions.
5. **CI Quality Verification**: Automated CI verification must guarantee that PRs run the full test suite (`pytest`) with coverage thresholds alongside linting and type-checking, preventing regressions.

## Solution Statement

1. **Update `README.md` Hardware Notes**: Add explicit notes/callouts to `awtrix_get_device_state` and `awtrix_set_settings` in `README.md` (§3) clarifying that `charging`, `active_app`, and `transitions` are unconfirmed across some physical hardware revisions and are omitted when `null` or unsupported by firmware.
2. **Update `README.md` Roadmap & Contribution Links**: Update §6 (Roadmap & Contributing) to accurately mark completed features (`mcp-server-awtrix` server, `awtrix-daemon` poller with hot-reload, Docker/Compose setup) and link directly to `CONTRIBUTING.md` and `CHANGELOG.md`.
3. **Create `CONTRIBUTING.md`**: Author a comprehensive developer guide detailing prerequisites (Python 3.10+, `uv`), local environment setup (`uv sync --group dev`), testing commands (`uv run pytest --cov`), linting & formatting (`uv run ruff check .`, `uv run ruff format --check .`), type checking (`uv run mypy awtrix_mcp docker`), daemon testing (`uv run awtrix-daemon validate apps/`), commit standards, and PR workflows.
4. **Create `CHANGELOG.md`**: Seed a `CHANGELOG.md` conforming to Keep a Changelog (v1.1.0) and Semantic Versioning (v2.0.0), including an `[Unreleased]` section and a `[0.1.0] - 2026-08-24` initial release section documenting all core capabilities.
5. **Verify `.github/workflows/ci.yml` Alignment**: Ensure the existing CI workflow (.github/workflows/ci.yml) enforces linting, type-checking, multi-version test execution (Python 3.10, 3.11, 3.12 with `>=85%` coverage), Docker smoke testing, and package builds matching the documented developer workflow.

## Out of Scope / Non-Goals

- Implementing new MCP tools or altering the MCP server wire protocol.
- Changing `DeviceStats` or `DeviceSettings` model field aliases in `awtrix_mcp/models.py`.
- Modifying daemon scheduling, AST evaluation, or YAML parsing logic.
- Adding MQTT transport or Web UI matrix preview (retained as future roadmap items).

## Feature Metadata

- **Feature Type**: Documentation / Project Hygiene
- **Estimated Complexity**: Low
- **Primary Systems Affected**: `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `.github/workflows/ci.yml`
- **Dependencies**: None (Markdown files and repository workflow documentation)

## Related Work

- **Implements**: GitHub Issue [#14](https://github.com/klodnickik/mcp-server-awtrix/issues/14)
- **Back-references**:
  - [PR #15](https://github.com/klodnickik/mcp-server-awtrix/pull/15) - Declarative YAML metric poller daemon completion (#12)
  - [PR #11](https://github.com/klodnickik/mcp-server-awtrix/pull/11) - CI pipeline and CLI validate subcommand (#5)
  - [PR #10](https://github.com/klodnickik/mcp-server-awtrix/pull/10) - Production-grade Docker containerization (#6)
- **Forward-references**: (none yet)

---

## CONTEXT REFERENCES

### Relevant Codebase Files IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- [README.md](file:///home/klodnicki_k/mcp-server-awtrix/README.md#L197-L227) (lines 197–227, 467–477) - Device state tool documentation, settings tool documentation, and Roadmap section.
- [pyproject.toml](file:///home/klodnicki_k/mcp-server-awtrix/pyproject.toml#L1-L115) (lines 1–115) - Project metadata, version `0.1.0`, dependencies, dev tool configuration (`ruff`, `mypy`, `pytest`, `coverage`).
- [awtrix_mcp/models.py](file:///home/klodnicki_k/mcp-server-awtrix/awtrix_mcp/models.py#L43-L67) (lines 43–67) - `DeviceStats` and `DeviceSettings` models with `# unconfirmed on real hardware` annotations.
- [awtrix_mcp/server.py](file:///home/klodnicki_k/mcp-server-awtrix/awtrix_mcp/server.py#L104-L128) (lines 104–128) - `awtrix_get_device_state` and `awtrix_set_settings` tool definitions and response structures.
- [.github/workflows/ci.yml](file:///home/klodnicki_k/mcp-server-awtrix/.github/workflows/ci.yml#L1-L80) (lines 1–80) - CI workflow definition across lint, typecheck, test (matrix 3.10/3.11/3.12), docker-smoke, and package jobs.

### New Files to Create

- `CONTRIBUTING.md` - Developer onboarding, local environment setup, validation commands, and PR guidelines.
- `CHANGELOG.md` - Project version changelog formatted according to Keep a Changelog 1.1.0.

### Relevant Documentation YOU SHOULD READ THESE BEFORE IMPLEMENTING!

- [Keep a Changelog 1.1.0 Specification](https://keepachangelog.com/en/1.1.0/)
  - Section: Principles & Changelog Format
  - Why: Defines section conventions (`Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`) and ISO 8601 release dates.
- [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html)
  - Section: Summary & SemVer specification
  - Why: Governs version increments across project releases.
- [Astral uv Documentation: Dependency Groups & Environments](https://docs.astral.sh/uv/concepts/projects/dependencies/#dependency-groups)
  - Section: Managing development dependency groups (`uv sync --group dev`)
  - Why: Official standard for local development setup documented in `CONTRIBUTING.md`.

### Patterns to Follow

**Markdown Callout Alerts:**
```markdown
> [!NOTE]
> Explanatory note or caveat
```

**Keep a Changelog Format:**
```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

## [0.1.0] - 2026-08-24

### Added
```

---

## IMPLEMENTATION PLAN

Phases run **top to bottom by default** — each assumes the phase above it is done.

### Phase 1: Documentation Accuracy (`README.md`)

Update existing documentation in `README.md` to reflect hardware support realities and accurate roadmap status.

**Tasks:**
- Add hardware-unconfirmed caveats to `awtrix_get_device_state` and `awtrix_set_settings` in `README.md` §3.
- Update `README.md` §6 Roadmap checkboxes to reflect implemented features and link to `CONTRIBUTING.md` and `CHANGELOG.md`.

### Phase 2: Project Hygiene Files (`CONTRIBUTING.md` & `CHANGELOG.md`)

Author root-level developer guide and project changelog.

**Tasks:**
- Create `CONTRIBUTING.md` with complete setup, development, testing, linting, type-checking, and PR instructions.
- Create `CHANGELOG.md` following Keep a Changelog v1.1.0 format with `[Unreleased]` and `[0.1.0]` release notes.

### Phase 3: CI Pipeline Verification & Cross-Document Consistency

Validate that all commands in `CONTRIBUTING.md` match `pyproject.toml` and `.github/workflows/ci.yml`, and verify formatting and links.

**Tasks:**
- Verify `.github/workflows/ci.yml` jobs against `CONTRIBUTING.md` commands.
- Verify Markdown formatting, code blocks, and internal cross-references.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

### 1. UPDATE `README.md`

- **IMPLEMENT**:
  1. In §3 `awtrix_get_device_state`, add a `> [!NOTE]` callout directly under the example response stating:
     "`charging` and `active_app` are unconfirmed on certain physical hardware revisions and are omitted by the server when `null` or unsupported by the device firmware."
  2. In §3 `awtrix_set_settings`, add a `> [!NOTE]` callout stating:
     "`transitions` (`ATRANS`) is unconfirmed on certain hardware versions and defaults to `None`."
  3. In §6 `Roadmap & Contributing`, update the task list to:
     ```markdown
     - [x] Core MCP Tools specification and design
     - [x] MCPServer (mcp v2) implementation with async HTTP client
     - [x] Declarative YAML metric poller daemon (`awtrix-daemon`) with hot-reload
     - [x] Production-grade multi-arch Docker and Compose deployment
     - [ ] Live visual web preview for matrix pixel art
     - [ ] MQTT Transport layer support (optional alternative to REST)
     - [ ] Home Assistant service discovery export

     Contributions are welcome! Please review our [Contributing Guide](CONTRIBUTING.md) and [Changelog](CHANGELOG.md) before submitting a pull request.
     ```
  4. Ensure Table of Contents links remain accurate and valid.
- **PATTERN**: [README.md:197-227](file:///home/klodnicki_k/mcp-server-awtrix/README.md#L197-L227), [README.md:467-477](file:///home/klodnicki_k/mcp-server-awtrix/README.md#L467-L477)
- **GOTCHA**: Do not insert inline JavaScript comments `// ...` into JSON example blocks as that breaks standard JSON syntax. Use standard GitHub Flavored Markdown blockquote callouts (`> [!NOTE]`).
- **VALIDATE**: `grep -n "unconfirmed" README.md && grep -n "CONTRIBUTING.md" README.md`
- **SATISFIES**: Issue #14 Scope items 1 & 2; Acceptance Criteria #3.

### 2. CREATE `CONTRIBUTING.md`

- **IMPLEMENT**: Create `/home/klodnicki_k/mcp-server-awtrix/CONTRIBUTING.md` containing:
  1. **Introduction & Code of Conduct**: Welcoming contributors and establishing community standards.
  2. **Prerequisites**:
     - Python 3.10+ (tested against 3.10, 3.11, 3.12)
     - `uv` (recommended package & environment manager) or standard `pip`/`venv`
     - Docker & Docker Compose (optional, for containerized smoke testing)
  3. **Development Environment Setup**:
     ```bash
     # Clone repository
     git clone https://github.com/klodnickik/mcp-server-awtrix.git
     cd mcp-server-awtrix

     # Install dependencies and development tools
     uv sync --group dev
     ```
  4. **Running Tests & Quality Gates**:
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
  5. **Running & Testing the Services Locally**:
     ```bash
     # Start the MCP Server on STDIO
     uv run mcp-server-awtrix

     # Validate app manifests
     uv run awtrix-daemon validate apps/

     # Run daemon locally
     uv run awtrix-daemon apps/
     ```
  6. **Pull Request & Commit Standards**:
     - Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)
     - Atomic commits with clear descriptions
     - Documenting changes in `CHANGELOG.md` under `[Unreleased]`
     - Ensuring all 5 CI jobs pass (lint, typecheck, test, docker-smoke, package)
- **PATTERN**: Follow standard open-source contribution guidelines aligned with `pyproject.toml` tool configuration.
- **GOTCHA**: Do not reference `pylint` since the project uses `ruff` and `mypy`. Ensure commands use `uv sync --group dev` matching `[dependency-groups] dev` in `pyproject.toml`.
- **VALIDATE**: `test -f CONTRIBUTING.md && grep "uv sync --group dev" CONTRIBUTING.md`
- **SATISFIES**: Issue #14 Scope item 3; Acceptance Criteria #2.

### 3. CREATE `CHANGELOG.md`

- **IMPLEMENT**: Create `/home/klodnicki_k/mcp-server-awtrix/CHANGELOG.md` containing:
  1. Header with references to Keep a Changelog 1.1.0 and Semantic Versioning 2.0.0.
  2. `## [Unreleased]` section with categories (`Added`, `Changed`, `Fixed`).
  3. `## [0.1.0] - 2026-08-24` section documenting:
     - `### Added`:
       - Core Model Context Protocol (MCP) server implementation (`awtrix_mcp.server`) exposing 5 tools: `awtrix_push_app`, `awtrix_notify`, `awtrix_delete_app`, `awtrix_get_device_state`, `awtrix_set_settings`, and `awtrix_test_render`.
       - Declarative YAML metric poller daemon (`awtrix-daemon` / `awtrix_mcp.daemon`) with AST-sandboxed expression evaluator, Jinja2 template rendering, sub-app error isolation, and `watchfiles` zero-downtime hot-reload.
       - Asynchronous HTTP client (`awtrix_mcp.client.AwtrixClient`) supporting AWTRIX Light 3.x wire protocol with connection timeouts and response validation.
       - Multi-architecture Docker packaging (`Dockerfile`, `docker-compose.yml`) with automated `/healthz` check script and non-root execution.
       - Comprehensive GitHub Actions CI pipeline in `.github/workflows/ci.yml` running Ruff linting, Mypy type-checking, Pytest across Python 3.10/3.11/3.12 with >=85% coverage enforcement, Docker smoke test, and package build checks.
       - Comprehensive developer documentation in `README.md` and `CONTRIBUTING.md`.
- **PATTERN**: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
- **GOTCHA**: Ensure valid Markdown formatting with proper section headers and ISO 8601 dates (`YYYY-MM-DD`).
- **VALIDATE**: `test -f CHANGELOG.md && grep "\[0.1.0\]" CHANGELOG.md`
- **SATISFIES**: Issue #14 Scope item 4; Acceptance Criteria #2.

### 4. VERIFY CI WORKFLOW ALIGNMENT (`.github/workflows/ci.yml`)

- **IMPLEMENT**: Inspect `.github/workflows/ci.yml` to confirm:
  1. `test` job executes `uv run pytest --cov --cov-report=xml --cov-report=term-missing --cov-fail-under=85` under a matrix of `["3.10", "3.11", "3.12"]`.
  2. `lint` job runs `uv run ruff check .`.
  3. `typecheck` job runs `uv run mypy awtrix_mcp docker`.
  4. CI fails whenever tests, linting, type-checking, or coverage drop below expectations.
- **PATTERN**: [.github/workflows/ci.yml:1-80](file:///home/klodnicki_k/mcp-server-awtrix/.github/workflows/ci.yml#L1-L80)
- **GOTCHA**: Confirm there are no stale references to `pylint.yml` or deleted workflow files.
- **VALIDATE**: `.venv/bin/ruff check .`
- **SATISFIES**: Issue #14 Scope item 5; Acceptance Criteria #1.

---

## TESTING STRATEGY

### Unit Tests
- Run existing unit test suite to verify zero regressions:
  - `tests/test_models.py` (model serialization and field aliases)
  - `tests/test_server.py` (MCP tools and device state responses)
  - `tests/test_client.py` (HTTP client requests and error handling)
  - `tests/test_daemon.py` (polling, AST evaluation, sub-app fault isolation)
  - `tests/test_config.py` (manifest parsing and secret resolution)
  - `tests/test_evaluator.py` (AST sandbox safety)
  - `tests/test_healthcheck.py` (healthcheck probe)

### Integration Tests
- Verify that documentation code snippets, example JSON structures, and CLI commands in `CONTRIBUTING.md` and `README.md` accurately correspond to the actual CLI entrypoints in `pyproject.toml`:
  - `mcp-server-awtrix` -> `awtrix_mcp.server:main`
  - `awtrix-daemon` -> `awtrix_mcp.daemon:main`

### Edge Cases
- Markdown syntax rendering: Validate that alert blockquotes (`> [!NOTE]`) render properly in GitHub Flavored Markdown.
- Relative file links: Ensure links between `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, and `LICENSE` resolve correctly.

---

## VALIDATION COMMANDS

Execute every command to ensure zero regressions and 100% feature correctness.

### Level 1: Syntax & Style
```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

### Level 2: Unit Tests & Type Checking
```bash
.venv/bin/mypy awtrix_mcp docker
.venv/bin/pytest -v
```

### Level 3: Code Coverage Enforcement
```bash
.venv/bin/pytest --cov=awtrix_mcp --cov=docker --cov-report=term-missing --cov-fail-under=85
```

### Level 4: Documentation & Link Verification
```bash
test -f CONTRIBUTING.md && test -f CHANGELOG.md && echo "Files exist"
grep -q "CONTRIBUTING.md" README.md && grep -q "CHANGELOG.md" README.md && echo "README links verified"
grep -q "unconfirmed" README.md && echo "Hardware caveat verified"
```

---

## ACCEPTANCE CRITERIA

- [ ] CI fails a PR that breaks `pytest`, not just one that breaks `pylint` (verified in `.github/workflows/ci.yml`).
- [ ] `CONTRIBUTING.md` and `CHANGELOG.md` exist at the repo root.
- [ ] `CONTRIBUTING.md` accurately details development environment setup (`uv sync --group dev`), testing (`pytest`), linting (`ruff`), and type checking (`mypy`).
- [ ] `CHANGELOG.md` adheres to Keep a Changelog format with `[Unreleased]` and `[0.1.0]` release notes.
- [ ] `README.md` clarifies which device-state and settings fields (`charging`, `active_app`, `transitions`) are unconfirmed on physical hardware.
- [ ] `README.md` roadmap accurately reflects shipped components vs. future planned items.
- [ ] All linters, type checks, and unit tests pass with zero regressions.

---

## COMPLETION CHECKLIST

- [ ] `README.md` updated with hardware caveats and updated roadmap.
- [ ] `CONTRIBUTING.md` created with comprehensive development guidelines.
- [ ] `CHANGELOG.md` created with Keep a Changelog 1.1.0 structure.
- [ ] CI workflow alignment verified against `.github/workflows/ci.yml`.
- [ ] All validation commands executed and passing.
- [ ] Acceptance criteria all met.

---

## OPEN QUESTIONS / ASSUMPTIONS

- **Assumption 1 (CI Workflow)**: `.github/workflows/ci.yml` (added in PR #11) already contains multi-version matrix testing for Python 3.10, 3.11, and 3.12 with >=85% test coverage enforcement, Ruff linting, Mypy type-checking, Docker smoke testing, and package validation. No separate or redundant workflow file is required.
- **Assumption 2 (Toolchain)**: Development toolchain references in `CONTRIBUTING.md` use Ruff (`uv run ruff check .`) and Mypy (`uv run mypy awtrix_mcp docker`) matching `pyproject.toml`, rather than `pylint`.

---

## NOTES (open canvas)

### Architecture Decision Rationale
1. **GitHub Markdown Callouts vs Inline Comments**: JSON examples in `README.md` should remain valid JSON representations without invalid inline `//` comments. Using GitHub alert callouts (`> [!NOTE]`) provides clear visual hierarchy and avoids breaking copy-pasted payload snippets.
2. **Keep a Changelog 1.1.0**: Standardizing on Keep a Changelog provides a clear, machine-readable and human-readable format for downstream users and package consumers tracking version updates.

---

## AMENDMENTS

*(None - created on 2026-08-24)*
