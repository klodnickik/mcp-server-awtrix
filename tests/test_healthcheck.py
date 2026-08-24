import os
import time
import urllib.error
from unittest.mock import MagicMock

from awtrix_mcp.daemon import DAEMON_HEARTBEAT_INTERVAL_SECONDS
from docker.healthcheck import (
    HEARTBEAT_STALE_AFTER_SECONDS,
    _check_mcp_server,
    _check_metric_daemon,
    main,
)


def test_stale_threshold_keeps_margin_over_heartbeat_interval():
    assert HEARTBEAT_STALE_AFTER_SECONDS >= 3 * DAEMON_HEARTBEAT_INTERVAL_SECONDS


def test_check_metric_daemon_missing_file_is_unhealthy(tmp_path, monkeypatch):
    monkeypatch.setenv("DAEMON_HEARTBEAT_FILE", str(tmp_path / "missing"))
    assert _check_metric_daemon() is False


def test_check_metric_daemon_fresh_heartbeat_is_healthy(tmp_path, monkeypatch):
    heartbeat = tmp_path / "heartbeat"
    heartbeat.touch()
    monkeypatch.setenv("DAEMON_HEARTBEAT_FILE", str(heartbeat))
    assert _check_metric_daemon() is True


def test_check_metric_daemon_stale_heartbeat_is_unhealthy(tmp_path, monkeypatch):
    heartbeat = tmp_path / "heartbeat"
    heartbeat.touch()
    stale_time = time.time() - HEARTBEAT_STALE_AFTER_SECONDS - 1
    os.utime(heartbeat, (stale_time, stale_time))
    monkeypatch.setenv("DAEMON_HEARTBEAT_FILE", str(heartbeat))
    assert _check_metric_daemon() is False


def test_check_mcp_server_success(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    monkeypatch.setattr("docker.healthcheck.urllib.request.urlopen", lambda *a, **k: response)
    assert _check_mcp_server() is True


def test_check_mcp_server_connection_refused_is_unhealthy(monkeypatch):
    def raise_oserror(*args, **kwargs):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("docker.healthcheck.urllib.request.urlopen", raise_oserror)
    assert _check_mcp_server() is False


def test_main_dispatches_to_mcp_server_check(monkeypatch):
    monkeypatch.setenv("CONTAINER_ROLE", "mcp-server")
    monkeypatch.setattr("docker.healthcheck._check_mcp_server", lambda: True)
    monkeypatch.setattr("docker.healthcheck._check_metric_daemon", lambda: False)
    assert main() == 0


def test_main_dispatches_to_metric_daemon_check_by_default(monkeypatch):
    monkeypatch.delenv("CONTAINER_ROLE", raising=False)
    monkeypatch.setattr("docker.healthcheck._check_mcp_server", lambda: False)
    monkeypatch.setattr("docker.healthcheck._check_metric_daemon", lambda: True)
    assert main() == 0


def test_main_returns_1_when_unhealthy(monkeypatch):
    monkeypatch.setenv("CONTAINER_ROLE", "metric-daemon")
    monkeypatch.setattr("docker.healthcheck._check_metric_daemon", lambda: False)
    assert main() == 1
