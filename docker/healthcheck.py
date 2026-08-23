"""Mode-aware container healthcheck. HTTP liveness for the SSE MCP server;
heartbeat-file freshness for the metric daemon, which has no HTTP surface.
Mode is selected via CONTAINER_ROLE (set per-service in docker-compose.yml
and defaulted in the Dockerfile)."""

import os
import pathlib
import sys
import time
import urllib.request

HEARTBEAT_STALE_AFTER_SECONDS = 90


def _check_mcp_server() -> bool:
    port = os.environ.get("MCP_PORT", "8000")
    try:
        urllib.request.urlopen(f"http://localhost:{port}/health", timeout=3)
        return True
    except OSError:
        return False


def _check_metric_daemon() -> bool:
    heartbeat = pathlib.Path(
        os.environ.get("DAEMON_HEARTBEAT_FILE", "/tmp/awtrix-daemon-heartbeat")
    )
    if not heartbeat.exists():
        return False
    return (time.time() - heartbeat.stat().st_mtime) < HEARTBEAT_STALE_AFTER_SECONDS


def main() -> int:
    role = os.environ.get("CONTAINER_ROLE", "metric-daemon")
    healthy = _check_mcp_server() if role == "mcp-server" else _check_metric_daemon()
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
