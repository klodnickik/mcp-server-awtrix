import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx

from awtrix_mcp.client import AwtrixClient
from awtrix_mcp.config import load_manifest
from awtrix_mcp.daemon import DaemonState, _reload_apps_dir, poll_once

BASE_URL = "http://awtrix.local"
SOURCE_URL = "https://api.checklyhq.com/v1/checks"


def _write_checkly_manifest(path: Path, *, interval_seconds: int = 60) -> None:
    path.write_text(
        textwrap.dedent(
            f"""
            app_id: "checkly"
            name: "checkly_status"
            interval_seconds: {interval_seconds}

            source:
              type: "http"
              url: "{SOURCE_URL}"

            transform:
              total: "len(data)"
              failures: "sum(1 for c in data if c.get('hasFailures'))"
              degraded: "sum(1 for c in data if c.get('isDegraded') and not c.get('hasFailures'))"

            display:
              - condition: "failures > 0"
                icon: "10558"
                notify: true
                text:
                  - {{ text: "FAIL ", color: "FF0000" }}
                  - {{ text: "({{{{failures}}}}/{{{{total}}}})", color: "FFFFFF" }}
              - condition: "default"
                icon: "483"
                text:
                  - {{ text: "UP ", color: "00FF00" }}
                  - {{ text: "({{{{total}}}})", color: "FFFFFF" }}
            """
        )
    )


def _write_saas_metrics_manifest(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """
            app_id: "saas_metrics"
            interval_seconds: 120

            source:
              type: "http"
              url: "https://api.example.com/v1/admin/metrics"

            sub_apps:
              - name: "app_support"
                icon: "10558"
                show_if: "data.tickets_open > 0"
                text:
                  - { text: "{{data.tickets_open}}", color: "FF0000" }
            """
        )
    )


@pytest.mark.asyncio
async def test_poll_once_sends_fail_payload_and_notification(tmp_path):
    manifest_path = tmp_path / "checkly.yaml"
    _write_checkly_manifest(manifest_path)
    manifest = load_manifest(manifest_path, env={})

    async with respx.mock:
        respx.get(SOURCE_URL).mock(
            return_value=httpx.Response(200, json=[{"hasFailures": True}, {"hasFailures": False}])
        )
        app_route = respx.post(f"{BASE_URL}/api/custom", params={"name": "checkly_status"}).mock(
            return_value=httpx.Response(200)
        )
        notify_route = respx.post(f"{BASE_URL}/api/notify").mock(return_value=httpx.Response(200))

        async with httpx.AsyncClient() as http, AwtrixClient(base_url=BASE_URL) as client:
            await poll_once(http, client, manifest)

        assert app_route.called
        assert b"FAIL" in app_route.calls.last.request.content
        assert notify_route.called


@pytest.mark.asyncio
async def test_poll_once_sends_default_payload_when_healthy(tmp_path):
    manifest_path = tmp_path / "checkly.yaml"
    _write_checkly_manifest(manifest_path)
    manifest = load_manifest(manifest_path, env={})

    async with respx.mock:
        respx.get(SOURCE_URL).mock(
            return_value=httpx.Response(200, json=[{"hasFailures": False}, {"hasFailures": False}])
        )
        app_route = respx.post(f"{BASE_URL}/api/custom", params={"name": "checkly_status"}).mock(
            return_value=httpx.Response(200)
        )
        notify_route = respx.post(f"{BASE_URL}/api/notify").mock(return_value=httpx.Response(200))

        async with httpx.AsyncClient() as http, AwtrixClient(base_url=BASE_URL) as client:
            await poll_once(http, client, manifest)

        assert app_route.called
        assert b"UP" in app_route.calls.last.request.content
        assert not notify_route.called


@pytest.mark.asyncio
async def test_poll_once_sub_app_deletes_when_show_if_false(tmp_path):
    manifest_path = tmp_path / "saas_metrics.yaml"
    _write_saas_metrics_manifest(manifest_path)
    manifest = load_manifest(manifest_path, env={})

    async with respx.mock:
        respx.get("https://api.example.com/v1/admin/metrics").mock(
            return_value=httpx.Response(200, json={"tickets_open": 0})
        )
        delete_route = respx.post(f"{BASE_URL}/api/custom", params={"name": "app_support"}).mock(
            return_value=httpx.Response(200)
        )

        async with httpx.AsyncClient() as http, AwtrixClient(base_url=BASE_URL) as client:
            await poll_once(http, client, manifest)

        assert delete_route.called
        assert delete_route.calls.last.request.content == b"{}"


@pytest.mark.asyncio
async def test_poll_once_source_fetch_failure_does_not_raise(tmp_path):
    manifest_path = tmp_path / "checkly.yaml"
    _write_checkly_manifest(manifest_path)
    manifest = load_manifest(manifest_path, env={})

    async with respx.mock:
        respx.get(SOURCE_URL).mock(side_effect=httpx.ConnectError("refused"))
        async with httpx.AsyncClient() as http, AwtrixClient(base_url=BASE_URL) as client:
            await poll_once(http, client, manifest)  # must not raise


@pytest.mark.asyncio
async def test_reload_apps_dir_schedules_new_manifest(tmp_path):
    manifest_path = tmp_path / "checkly.yaml"
    _write_checkly_manifest(manifest_path)

    scheduler = MagicMock()
    client = AsyncMock()
    state = DaemonState(scheduler=scheduler, http=MagicMock(), client=client)

    await _reload_apps_dir(state, tmp_path, {})

    assert scheduler.add_job.called
    _, kwargs = scheduler.add_job.call_args
    assert kwargs["id"] == "checkly"
    assert kwargs["seconds"] == 60


@pytest.mark.asyncio
async def test_reload_apps_dir_reschedules_on_interval_change(tmp_path):
    manifest_path = tmp_path / "checkly.yaml"
    _write_checkly_manifest(manifest_path, interval_seconds=60)

    scheduler = MagicMock()
    client = AsyncMock()
    state = DaemonState(scheduler=scheduler, http=MagicMock(), client=client)

    await _reload_apps_dir(state, tmp_path, {})
    scheduler.add_job.reset_mock()

    _write_checkly_manifest(manifest_path, interval_seconds=30)
    await _reload_apps_dir(state, tmp_path, {})

    assert scheduler.add_job.called
    _, kwargs = scheduler.add_job.call_args
    assert kwargs["seconds"] == 30
    assert kwargs["replace_existing"] is True


@pytest.mark.asyncio
async def test_reload_apps_dir_deletes_apps_when_manifest_removed(tmp_path):
    manifest_path = tmp_path / "checkly.yaml"
    _write_checkly_manifest(manifest_path)

    scheduler = MagicMock()
    client = AsyncMock()
    state = DaemonState(scheduler=scheduler, http=MagicMock(), client=client)

    await _reload_apps_dir(state, tmp_path, {})
    manifest_path.unlink()
    await _reload_apps_dir(state, tmp_path, {})

    assert scheduler.remove_job.called
    client.delete_app.assert_awaited_with("checkly_status")
