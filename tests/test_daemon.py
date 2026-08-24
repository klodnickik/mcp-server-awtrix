import asyncio
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx

from awtrix_mcp.client import AwtrixClient
from awtrix_mcp.config import AwtrixSettings, BasicAuthConfig, SourceConfig, load_manifest
from awtrix_mcp.daemon import (
    DaemonState,
    _reload_apps_dir,
    fetch_source,
    main,
    poll_once,
    run_daemon,
    watch_apps_dir,
)

BASE_URL = "http://awtrix.local"
SOURCE_URL = "https://api.checklyhq.com/v1/checks"


def _write_checkly_manifest(path: Path, *, interval_seconds: int = 60, enabled: bool = True) -> None:
    path.write_text(
        textwrap.dedent(
            f"""
            app_id: "checkly"
            name: "checkly_status"
            enabled: {str(enabled).lower()}
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


@pytest.mark.asyncio
async def test_reload_apps_dir_unschedules_disabled_manifest(tmp_path):
    manifest_path = tmp_path / "checkly.yaml"
    _write_checkly_manifest(manifest_path, enabled=True)

    scheduler = MagicMock()
    client = AsyncMock()
    state = DaemonState(scheduler=scheduler, http=MagicMock(), client=client)

    await _reload_apps_dir(state, tmp_path, {})
    scheduler.add_job.reset_mock()

    _write_checkly_manifest(manifest_path, enabled=False)
    await _reload_apps_dir(state, tmp_path, {})

    assert scheduler.remove_job.called
    assert scheduler.remove_job.call_args[0][0] == "checkly"
    assert not scheduler.add_job.called


@pytest.mark.asyncio
async def test_reload_apps_dir_skips_invalid_manifest_and_logs(tmp_path, caplog):
    valid = tmp_path / "checkly.yaml"
    _write_checkly_manifest(valid)
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(
        textwrap.dedent(
            """
            app_id: "bad"
            interval_seconds: 1
            unexpected_key: true
            source: { type: "http", url: "http://x" }
            display: [{ condition: "default", text: [{ text: "hi" }] }]
            """
        )
    )

    scheduler = MagicMock()
    client = AsyncMock()
    state = DaemonState(scheduler=scheduler, http=MagicMock(), client=client)

    with caplog.at_level("WARNING"):
        await _reload_apps_dir(state, tmp_path, {})

    assert "invalid.yaml" in caplog.text
    assert state.manifests[valid][0].app_id == "checkly"
    assert len(state.manifests) == 1


@pytest.mark.asyncio
async def test_reload_apps_dir_skips_manifest_with_duplicate_app_id(tmp_path, caplog):
    first = tmp_path / "checkly.yaml"
    _write_checkly_manifest(first)
    duplicate = tmp_path / "checkly_copy.yaml"
    _write_checkly_manifest(duplicate)

    scheduler = MagicMock()
    client = AsyncMock()
    state = DaemonState(scheduler=scheduler, http=MagicMock(), client=client)

    with caplog.at_level("WARNING"):
        await _reload_apps_dir(state, tmp_path, {})

    assert "app_id 'checkly' already used by" in caplog.text
    assert scheduler.add_job.call_count == 1
    assert list(state.manifests.keys()) == [first]


@pytest.mark.asyncio
async def test_reload_apps_dir_keeps_skipping_duplicate_app_id_across_reload_cycles(tmp_path, caplog):
    first = tmp_path / "checkly.yaml"
    _write_checkly_manifest(first)
    duplicate = tmp_path / "checkly_copy.yaml"
    _write_checkly_manifest(duplicate)

    scheduler = MagicMock()
    client = AsyncMock()
    state = DaemonState(scheduler=scheduler, http=MagicMock(), client=client)

    await _reload_apps_dir(state, tmp_path, {})
    scheduler.add_job.reset_mock()

    # Unrelated filesystem event (e.g. an editor touching the duplicate file)
    # re-triggers a reload; the duplicate must still be rejected, not silently
    # allowed to steal the job/app now that a cycle has passed.
    with caplog.at_level("WARNING"):
        await _reload_apps_dir(state, tmp_path, {})

    assert "app_id 'checkly' already used by" in caplog.text
    assert not scheduler.add_job.called
    assert list(state.manifests.keys()) == [first]


@pytest.mark.asyncio
async def test_watch_apps_dir_triggers_reload_on_change(tmp_path, monkeypatch):
    async def fake_awatch(_path, stop_event):  # pylint: disable=unused-argument
        yield {("added", str(tmp_path / "x.yaml"))}

    monkeypatch.setattr("awtrix_mcp.daemon.watchfiles.awatch", fake_awatch)

    reload_calls = []

    async def fake_reload(state, apps_dir, env):
        reload_calls.append((state, apps_dir, env))

    monkeypatch.setattr("awtrix_mcp.daemon._reload_apps_dir", fake_reload)

    state = DaemonState(scheduler=MagicMock(), http=MagicMock(), client=AsyncMock())
    await watch_apps_dir(state, tmp_path, {}, asyncio.Event())

    assert len(reload_calls) == 1


@pytest.mark.asyncio
async def test_fetch_source_sends_basic_auth_header():
    source = SourceConfig(url="https://api.example.com/data", auth=BasicAuthConfig(username="u", password="p"))

    async with respx.mock:
        route = respx.get("https://api.example.com/data").mock(return_value=httpx.Response(200, json={}))
        async with httpx.AsyncClient() as http:
            await fetch_source(http, source)

        assert route.called
        assert route.calls.last.request.headers["authorization"] == "Basic dTpw"


@pytest.mark.asyncio
async def test_fetch_source_omits_auth_header_when_unset():
    source = SourceConfig(url="https://api.example.com/data")

    async with respx.mock:
        route = respx.get("https://api.example.com/data").mock(return_value=httpx.Response(200, json={}))
        async with httpx.AsyncClient() as http:
            await fetch_source(http, source)

        assert "authorization" not in route.calls.last.request.headers


@pytest.mark.asyncio
async def test_poll_once_sub_app_shows_when_show_if_true(tmp_path):
    manifest_path = tmp_path / "saas_metrics.yaml"
    _write_saas_metrics_manifest(manifest_path)
    manifest = load_manifest(manifest_path, env={})

    async with respx.mock:
        respx.get("https://api.example.com/v1/admin/metrics").mock(
            return_value=httpx.Response(200, json={"tickets_open": 3})
        )
        show_route = respx.post(f"{BASE_URL}/api/custom", params={"name": "app_support"}).mock(
            return_value=httpx.Response(200)
        )

        async with httpx.AsyncClient() as http, AwtrixClient(base_url=BASE_URL) as client:
            await poll_once(http, client, manifest)

        assert show_route.called
        assert b"3" in show_route.calls.last.request.content


@pytest.mark.asyncio
async def test_poll_once_invalid_json_response_does_not_raise(tmp_path):
    manifest_path = tmp_path / "checkly.yaml"
    _write_checkly_manifest(manifest_path)
    manifest = load_manifest(manifest_path, env={})

    async with respx.mock:
        respx.get(SOURCE_URL).mock(return_value=httpx.Response(200, text="<html>not json</html>"))
        async with httpx.AsyncClient() as http, AwtrixClient(base_url=BASE_URL) as client:
            await poll_once(http, client, manifest)  # must not raise


@pytest.mark.asyncio
async def test_poll_once_device_error_during_display_push_does_not_raise(tmp_path):
    manifest_path = tmp_path / "checkly.yaml"
    _write_checkly_manifest(manifest_path)
    manifest = load_manifest(manifest_path, env={})

    async with respx.mock:
        respx.get(SOURCE_URL).mock(
            return_value=httpx.Response(200, json=[{"hasFailures": True}, {"hasFailures": False}])
        )
        respx.post(f"{BASE_URL}/api/custom", params={"name": "checkly_status"}).mock(
            return_value=httpx.Response(500)
        )

        async with httpx.AsyncClient() as http, AwtrixClient(base_url=BASE_URL) as client:
            await poll_once(http, client, manifest)  # must not raise despite AwtrixResponseError


@pytest.mark.asyncio
async def test_poll_once_template_error_during_display_push_does_not_raise(tmp_path):
    manifest_path = tmp_path / "checkly.yaml"
    manifest_path.write_text(
        textwrap.dedent(
            f"""
            app_id: "checkly"
            interval_seconds: 60
            source:
              type: "http"
              url: "{SOURCE_URL}"
            display:
              - condition: "default"
                text:
                  - {{ text: "{{{{data.nonexistent_field}}}}", color: "FFFFFF" }}
            """
        )
    )
    manifest = load_manifest(manifest_path, env={})

    async with respx.mock:
        respx.get(SOURCE_URL).mock(return_value=httpx.Response(200, json={"total": 1}))
        async with httpx.AsyncClient() as http, AwtrixClient(base_url=BASE_URL) as client:
            await poll_once(http, client, manifest)  # must not raise despite StrictUndefined ExpressionError


@pytest.mark.asyncio
async def test_poll_once_transform_failure_does_not_raise_and_skips_push(tmp_path):
    manifest_path = tmp_path / "checkly.yaml"
    manifest_path.write_text(
        textwrap.dedent(
            f"""
            app_id: "checkly"
            interval_seconds: 60
            source:
              type: "http"
              url: "{SOURCE_URL}"
            transform:
              failures: "data.nonexistent_field"
            display:
              - condition: "default"
                text:
                  - {{ text: "UP", color: "00FF00" }}
            """
        )
    )
    manifest = load_manifest(manifest_path, env={})

    async with respx.mock:
        respx.get(SOURCE_URL).mock(return_value=httpx.Response(200, json={"total": 1}))
        app_route = respx.post(f"{BASE_URL}/api/custom", params={"name": "checkly"}).mock(
            return_value=httpx.Response(200)
        )
        async with httpx.AsyncClient() as http, AwtrixClient(base_url=BASE_URL) as client:
            await poll_once(http, client, manifest)  # must not raise

        assert not app_route.called  # push must be skipped, not attempted with a broken context


@pytest.mark.asyncio
async def test_run_daemon_touches_heartbeat_file(tmp_path, monkeypatch):
    heartbeat_path = tmp_path / "heartbeat"
    monkeypatch.setenv("DAEMON_HEARTBEAT_FILE", str(heartbeat_path))
    apps_dir = tmp_path / "apps"
    apps_dir.mkdir()

    task = asyncio.create_task(run_daemon(apps_dir, AwtrixSettings(base_url=BASE_URL)))
    try:
        for _ in range(50):
            if heartbeat_path.exists():
                break
            await asyncio.sleep(0.1)
        assert heartbeat_path.exists()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


def test_validate_single_valid_file_exits_zero(tmp_path, monkeypatch, capsys):
    manifest_path = tmp_path / "checkly.yaml"
    _write_checkly_manifest(manifest_path)
    monkeypatch.setattr("sys.argv", ["awtrix-daemon", "validate", str(manifest_path)])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    assert "OK" in capsys.readouterr().out


def test_validate_invalid_manifest_exits_one(tmp_path, monkeypatch, capsys):
    manifest_path = tmp_path / "bad.yaml"
    manifest_path.write_text("app_id: t\ninterval_seconds: 1\nsource: {type: http, url: 'http://x'}\n")
    monkeypatch.setattr("sys.argv", ["awtrix-daemon", "validate", str(manifest_path)])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    assert "INVALID" in capsys.readouterr().err


def test_validate_no_files_found_exits_one(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["awtrix-daemon", "--apps-dir", str(tmp_path), "validate"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_validate_dir_wide_validates_all_manifests(tmp_path, monkeypatch, capsys):
    _write_checkly_manifest(tmp_path / "checkly.yaml")
    _write_saas_metrics_manifest(tmp_path / "saas_metrics.yaml")
    monkeypatch.setattr("sys.argv", ["awtrix-daemon", "--apps-dir", str(tmp_path), "validate"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    assert capsys.readouterr().out.count("OK") == 2


def test_validate_missing_file_exits_one(tmp_path, monkeypatch, capsys):
    missing_path = tmp_path / "does-not-exist.yaml"
    monkeypatch.setattr("sys.argv", ["awtrix-daemon", "validate", str(missing_path)])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    assert "INVALID" in capsys.readouterr().err


def test_validate_dir_wide_mixed_valid_and_invalid(tmp_path, monkeypatch, capsys):
    _write_checkly_manifest(tmp_path / "good.yaml")
    (tmp_path / "bad.yaml").write_text("app_id: t\ninterval_seconds: 1\nsource: {type: http, url: 'http://x'}\n")
    monkeypatch.setattr("sys.argv", ["awtrix-daemon", "--apps-dir", str(tmp_path), "validate"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "OK" in captured.out
    assert "INVALID" in captured.err


def test_validate_duplicate_app_id_exits_one(tmp_path, monkeypatch, capsys):
    _write_checkly_manifest(tmp_path / "checkly.yaml")
    _write_checkly_manifest(tmp_path / "checkly_copy.yaml")
    monkeypatch.setattr("sys.argv", ["awtrix-daemon", "--apps-dir", str(tmp_path), "validate"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "OK" in captured.out
    assert "app_id 'checkly' already used by" in captured.err
