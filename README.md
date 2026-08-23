# MCP Server Awtrix: AI Agent Display Orchestrator for Ulanzi & Pixel Clocks

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Protocol](https://img.shields.io/badge/Protocol-MCP-blue.svg)](https://modelcontextprotocol.io/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Awtrix Light](https://img.shields.io/badge/Firmware-Awtrix_Light_3.x-orange.svg)](https://blueforcer.github.io/awtrix-light/)

**MCP Server Awtrix** (`mcp-server-awtrix`) is an open-source [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server and declarative metric orchestrator designed to give AI agents (Antigravity, Claude Desktop, Cursor, Cline, AutoGPT, etc.) full control over **Ulanzi TC001** and compatible pixel matrix smart clocks running **Awtrix Light**.

It bridges conversational and autonomous AI agents with physical desktop displays, enabling:
- **Instant Agent Alerts**: Push ad-hoc status alerts, build failure notifications, and task completions to the pixel screen.
- **Dynamic Carousel Apps**: Register, update, and cycle through custom live telemetry apps (server health, SaaS metrics, revenue counters, build status).
- **Declarative Metric Poller**: Automate background API fetching and threshold formatting via YAML specifications without writing bespoke Python scripts.
- **Hardware Telemetry & Control**: Inspect battery levels, adjust matrix brightness, manage power states, and trigger custom sound cues.

---

## Table of Contents

1. [Product Requirements Document (PRD)](#1-product-requirements-document-prd)
   - [Problem Statement](#problem-statement)
   - [Goals & Non-Goals](#goals--non-goals)
   - [Target Personas & Use Cases](#target-personas--use-cases)
   - [Functional Requirements](#functional-requirements)
   - [Non-Functional Requirements](#non-functional-requirements)
2. [System Architecture & Design](#2-system-architecture--design)
   - [High-Level Architecture](#high-level-architecture)
   - [Component Breakdown](#component-breakdown)
   - [Data Flow](#data-flow)
3. [MCP Tools Specification](#3-mcp-tools-specification)
4. [Declarative App Engine (YAML Schema)](#4-declarative-app-engine-yaml-schema)
   - [Example 1: CI/CD & Service Health (Checkly)](#example-1-service-health-checkly)
   - [Example 2: Multi-Metric SaaS Dashboard](#example-2-saas-metrics-dashboard)
5. [Quickstart & Installation](#5-quickstart--installation)
   - [Prerequisites](#prerequisites)
   - [Local Setup with uv / pip](#local-setup-with-uv--pip)
   - [MCP Client Configuration](#mcp-client-configuration)
6. [Roadmap & Contributing](#6-roadmap--contributing)
7. [License](#7-license)

---

## 1. Product Requirements Document (PRD)

### Problem Statement
Developers and power users running smart pixel clocks (like the Ulanzi TC001 with Awtrix Light) currently write fragmented, hardcoded Python or Bash cron scripts to query external APIs and update matrix apps. 

When working with AI coding agents:
- Agents must generate and maintain raw imperative code for every metric.
- There is no standardized toolset for an AI agent to send real-time notifications or manage the display lifecycle.
- Secret management is error-prone, risking API key leaks in AI prompts and logs.
- There is no native fallback or validation for multi-segment text formatting and pixel icons.

### Goals & Non-Goals

#### Goals
- **Native MCP Interface**: Provide a standard Model Context Protocol server exposing robust tools for notifications, custom apps, device management, and previews.
- **Declarative Telemetry**: Enable agents and humans to define metric polling rules in simple YAML files with built-in templating (Jinja2) and threshold styling.
- **Secure Secret Isolation**: Decouple sensitive credentials from prompt context using `.env` environment variable substitution.
- **Zero-Downtime Hot-Reload**: Automatically reflect changes made to YAML configuration files without service restarts.
- **Reliable Fallbacks**: Gracefully handle network outages, API rate limits, and offline display states.

#### Non-Goals
- Replacing the Awtrix Light firmware (this tool interacts exclusively with the official Awtrix Light REST/MQTT API).
- Complex multi-monitor tile synchronization (focus is on single or multi-instance standalone pixel clocks).

### Target Personas & Use Cases

| Persona | Scenario | How MCP Server Awtrix Helps |
|---|---|---|
| **AI Coding Agent** (e.g., Antigravity / Cursor) | Agent finishes a 10-minute test suite or autonomous task in the background. | Calls `awtrix_notify` tool to flash green with a checkmark icon and chime on the developer's desk. |
| **DevOps / SRE Engineer** | Wants to monitor production uptime, error budgets, or Checkly synthetic tests. | Drops a `checkly.yaml` declarative spec; orchestrator polls every 60s and turns red on failures. |
| **SaaS Founder / Builder** | Wants real-time MRR, new user signups, and support ticket counters cycling on desk. | Defines a declarative multi-metric app querying backend admin endpoints. |

### Functional Requirements

1. **FR-1: Instant Notifications (`/api/notify`)**:
   - Support custom text, multi-segment colored text, icon ID, sound/RTTTL ringtones, priority hold, and duration.
2. **FR-2: Custom Carousel Apps (`/api/custom`)**:
   - Ability to register, update, and remove named apps from the display loop.
   - Support rich text segment formatting (`[{"t": "FAIL", "c": "FF0000"}, {"t": " (2/10)", "c": "FFFFFF"}]`).
3. **FR-3: Declarative Background Engine**:
   - Built-in scheduler (`asyncio` / `apscheduler`) executing polling jobs defined in `apps/*.yaml`.
   - Templating engine supporting computed variables, arithmetic, and conditional expressions.
4. **FR-4: Device State & Telemetry**:
   - Query battery percentage, Wi-Fi RSSI, lux sensor, matrix state, and active apps.
   - Adjust brightness, sleep/wake status, and transitions.
5. **FR-5: Dry-Run & Simulation**:
   - Preview tool returning exact rendered JSON payloads and color validations prior to hardware submission.

### Non-Functional Requirements

- **Latency**: Direct MCP tool executions must dispatch to Awtrix within $< 150\text{ms}$ on local networks.
- **Resilience**: A failed source fetch is logged and skipped for that cycle; the next scheduled poll (per `interval_seconds`) retries automatically. No exponential backoff or explicit "degraded" state is applied to source fetches.
- **Portability**: Packaged as standard Python package with `uv`/`pipx` support, Docker container, and standalone CLI.

---

## 2. System Architecture & Design

### High-Level Architecture

```
                                  ┌──────────────────────────┐
                                  │      AI Client/Host      │
                                  │ (Claude / Antigravity /  │
                                  │     Cursor / Cline)      │
                                  └────────────┬─────────────┘
                                               │
                                               │ stdio / SSE (MCP Protocol)
                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                  mcp-server-awtrix                                     │
│                                                                                        │
│  ┌───────────────────────┐   ┌──────────────────────────────┐   ┌───────────────────┐  │
│  │     MCP Interface     │   │      App Orchestrator        │   │   Config Watcher  │  │
│  │ (Tools / Resources)   │   │     (Async Scheduler)        │   │   (Hot-Reload)    │  │
│  └───────────┬───────────┘   └──────────────┬───────────────┘   └─────────┬─────────┘  │
│              │                              │                             │            │
│              ▼                              ▼                             ▼            │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                               Core Engine & Driver                               │  │
│  │  - Schema Validator (Pydantic)                                                   │  │
│  │  - Template & Expression Engine (Jinja2 / restricted Python evaluator)           │  │
│  │  - Secret Resolver (.env)                                                        │  │
│  │  - Awtrix REST / WebSocket Client                                                │  │
│  └──────────────────────────────────────────┬───────────────────────────────────────┘  │
└─────────────────────────────────────────────┼──────────────────────────────────────────┘
                                              │
                                              │ HTTP REST (JSON)
                                              ▼
                                ┌──────────────────────────┐
                                │     Ulanzi TC001 Clock   │
                                │   (Awtrix Light Firmware)│
                                └──────────────────────────┘
```

### Component Breakdown

1. **MCP Interface Layer**:
   - Implements Model Context Protocol server endpoints over `stdio` and `SSE`.
   - Exposes tools with strict JSON schemas and human-readable documentation for AI models.
2. **Declarative Polling Engine**:
   - Asynchronous worker managing task lifecycles for file-based app manifests.
   - Evaluates HTTP requests, extracts fields using a sandboxed expression evaluator (see §4), and resolves display rules.
3. **Awtrix Driver**:
   - Encapsulates device communication, request deduplication, connection pooling, and error recovery.
4. **Configuration & Security Layer**:
   - Isolates sensitive tokens into `.env`. Config files reference variables via `${VAR_NAME}` syntax.

---

## 3. MCP Tools Specification

AI Agents can execute the following MCP tools:

### `awtrix_notify`
Pushes an immediate, high-priority notification to the screen (interrupts the current carousel).

```json
{
  "text": "Build Failed: Backend API",
  "icon": "10558",
  "color": "FF0000",
  "duration": 8,
  "sound": "alarm",
  "rtttl": "beep:d=4,o=5,b=100:16e6,16e6",
  "wakeup": true
}
```

### `awtrix_upsert_app`
Registers or updates a persistent custom app in the carousel loop.

```json
{
  "name": "app_users",
  "text": [
    {"t": "1,420", "c": "FFFFFF"},
    {"t": " (+42)", "c": "00FF00"}
  ],
  "icon": "2058",
  "duration": 5,
  "lifetime": 300
}
```

### `awtrix_delete_app`
Removes a custom app from the device cycle.

```json
{
  "name": "app_users"
}
```

### `awtrix_get_device_state`
Returns hardware statistics and current operational metrics.

*Response:*
```json
{
  "online": true,
  "battery": 88,
  "charging": true,
  "lux": 140,
  "temp": 24,
  "ram_free": 128440,
  "active_app": "app_users",
  "brightness": 120
}
```

### `awtrix_set_settings`
Configures device parameters such as brightness, matrix toggle, and transition speeds.

```json
{
  "brightness": 80,
  "power": true
}
```

### `awtrix_test_render`
Dry-run helper that parses expressions and returns the rendered payload without pushing to hardware.

---

## 4. Declarative App Engine (YAML Schema)

Rather than maintaining custom Python scripts, place `.yaml` manifests in the `apps/` directory.

### Example 1: Service Health (Checkly)
`apps/checkly.yaml`

```yaml
app_id: "checkly"
name: "checkly_status"
enabled: true
interval_seconds: 60

source:
  type: "http"
  url: "https://api.checklyhq.com/v1/checks"
  headers:
    Authorization: "Bearer ${CHECKLY_API_KEY}"
    X-Checkly-Account: "${CHECKLY_ACCOUNT_ID}"

transform:
  total: "len(data)"
  failures: "sum(1 for c in data if c.get('hasFailures'))"
  degraded: "sum(1 for c in data if c.get('isDegraded') and not c.get('hasFailures'))"

display:
  - condition: "failures > 0"
    icon: "10558"
    notify: true
    text:
      - { text: "FAIL ", color: "FF0000" }
      - { text: "({{failures}}/{{total}})", color: "FFFFFF" }

  - condition: "degraded > 0"
    icon: "10558"
    text:
      - { text: "WARN ", color: "FFA500" }
      - { text: "({{degraded}}/{{total}})", color: "FFFFFF" }

  - condition: "default"
    icon: "483"
    text:
      - { text: "UP ", color: "00FF00" }
      - { text: "({{total}})", color: "FFFFFF" }
```

`source` also supports HTTP Basic Auth as an alternative to header-based credentials:

```yaml
source:
  type: "http"
  url: "https://api.example.com/v1/private"
  auth:
    username: "${API_USERNAME}"
    password: "${API_PASSWORD}"
```

### Example 2: Multi-Metric SaaS Dashboard
`apps/saas_metrics.yaml`

```yaml
app_id: "saas_metrics"
interval_seconds: 120

source:
  type: "http"
  url: "https://api.example.com/v1/admin/metrics"
  headers:
    X-API-Secret: "${SAAS_METRICS_API_SECRET}"

sub_apps:
  - name: "app_users"
    icon: "2058"
    text:
      - { text: "{{data.users_total}}", color: "FFFFFF" }
      - { text: " (+{{data.new_users_last_week}})", color: "00FF00" }

  - name: "app_premium"
    icon: "5336"
    text:
      - { text: "{{data.users_premium}}", color: "FFFFFF" }
      - { text: " (+{{data.new_users_premium_last_week}})", color: "FFD700" }

  - name: "app_orders"
    icon: "21072"
    text:
      - { text: "{{data.orders_total}}", color: "FFFFFF" }
      - { text: " (+{{data.new_orders_last_week}})", color: "00FF00" }

  - name: "app_support"
    icon: "10558"
    show_if: "data.tickets_open > 0"
    text:
      - { text: "{{data.tickets_open}}", color: "FF0000" }
```

---

## 5. Quickstart & Installation

### Prerequisites
- Python 3.10 or higher
- Ulanzi TC001 (or compatible device) flashed with [Awtrix Light Firmware](https://blueforcer.github.io/awtrix-light/) connected to your Wi-Fi network.

### Local Setup with `uv` / `pip`

```bash
# Clone the repository
git clone https://github.com/klodnickik/mcp-server-awtrix.git
cd mcp-server-awtrix

# Copy example environment configuration
cp .env.example .env

# Edit device address and API keys in .env
# AWTRIX_BASE_URL=http://awtrix3.local
```

Run the MCP server locally over stdio:
```bash
# Using uv (recommended)
uv run mcp-server-awtrix

# Or standard pip
pip install -e .
python -m awtrix_mcp
```

Or over SSE (HTTP), for clients that connect remotely:
```bash
uv run mcp-server-awtrix --transport sse --host 0.0.0.0 --port 8000
```

Run the metric poller daemon locally (polls `apps/*.yaml` in the background):
```bash
uv run awtrix-daemon --apps-dir apps
```

### Running Tests

```bash
uv sync --group dev
uv run pytest
```

### Docker & Docker Compose Setup

Run using Docker Compose:

```bash
# 1. Clone & prepare environment
git clone https://github.com/klodnickik/mcp-server-awtrix.git
cd mcp-server-awtrix
cp .env.example .env

# 2. Start the MCP Server (SSE on port 8000) and Metric Daemon
docker compose up -d

# Or start only the metric poller daemon:
docker compose up -d metric-daemon

# View live logs:
docker compose logs -f
```

**Multi-arch builds (Raspberry Pi / arm64):**

```bash
# One-time setup for a buildx builder that supports multiple platforms
docker buildx create --use

docker buildx build --platform linux/amd64,linux/arm64 -t <you>/mcp-server-awtrix:local .
```

Prebuilt multi-arch images (`linux/amd64` + `linux/arm64`) are also published to
`ghcr.io/klodnickik/mcp-server-awtrix` by CI on every push to `main` and on version
tags, so NAS/Pi/cloud users can `docker pull` instead of building locally.

**Health check:** the `mcp-server` container exposes `GET http://localhost:8000/health`,
which returns `{"status": "ok"}` when the server is up. `CONTAINER_ROLE` and
`DAEMON_HEARTBEAT_FILE` are internal compose-wiring environment variables used to pick
the right healthcheck per service — they don't need to be set in `.env`.

### MCP Client Configuration

#### 1. Google Antigravity
Add to your `mcp_servers.json`:
```json
{
  "mcpServers": {
    "awtrix": {
      "command": "uv",
      "args": ["--directory", "/path/to/mcp-server-awtrix", "run", "mcp-server-awtrix"],
      "env": {
        "AWTRIX_BASE_URL": "http://awtrix3.local"
      }
    }
  }
}
```

#### 2. Claude Desktop
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "awtrix": {
      "command": "python",
      "args": ["-m", "awtrix_mcp"],
      "env": {
        "AWTRIX_BASE_URL": "http://awtrix3.local"
      }
    }
  }
}
```

#### 3. Cursor
In Cursor Settings $\rightarrow$ Features $\rightarrow$ MCP Servers $\rightarrow$ Add Server:
- **Name**: `awtrix`
- **Type**: `command`
- **Command**: `uv --directory /path/to/mcp-server-awtrix run mcp-server-awtrix`

---

## 6. Roadmap & Contributing

- [x] Core MCP Tools specification and design
- [x] Declarative YAML orchestration schema
- [x] MCPServer (mcp v2) implementation with async HTTP client
- [ ] Live visual web preview for matrix pixel art
- [ ] MQTT Transport layer support (optional alternative to REST)
- [ ] Home Assistant service discovery export

Contributions are welcome! Please submit a PR or open an issue for feature discussions.

---

## 7. License

Distributed under the **MIT License**. See `LICENSE` for more information.
