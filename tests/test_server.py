"""Integration tests for the AWTRIX MCP tools, via the in-process MCP Client."""

from unittest.mock import MagicMock

import httpx
import pytest
import respx
from mcp import Client

from awtrix_mcp.config import AwtrixSettings
from awtrix_mcp.server import build_server, main

BASE_URL = "http://awtrix.local"


@pytest.fixture
def server():
    return build_server(AwtrixSettings(base_url=BASE_URL))


@pytest.mark.asyncio
async def test_awtrix_notify_posts_expected_payload(server):
    async with respx.mock:
        route = respx.post(f"{BASE_URL}/api/notify").mock(return_value=httpx.Response(200))
        async with Client(server, raise_exceptions=True) as client:
            result = await client.call_tool("awtrix_notify", {"text": "Build Failed", "color": "FF0000"})
        assert not result.is_error
        assert route.called
        assert result.structured_content["status"] == "sent"
        assert result.structured_content["payload"]["color"] == "FF0000"


@pytest.mark.asyncio
async def test_awtrix_notify_accepts_text_segments():
    server_local = build_server(AwtrixSettings(base_url=BASE_URL))
    async with respx.mock:
        respx.post(f"{BASE_URL}/api/notify").mock(return_value=httpx.Response(200))
        async with Client(server_local, raise_exceptions=True) as client:
            result = await client.call_tool(
                "awtrix_notify",
                {"text": [{"t": "FAIL", "c": "FF0000"}, {"t": " (2/10)", "c": "FFFFFF"}]},
            )
        assert result.structured_content["payload"]["text"] == [
            {"t": "FAIL", "c": "FF0000"},
            {"t": " (2/10)", "c": "FFFFFF"},
        ]


@pytest.mark.asyncio
async def test_awtrix_notify_surfaces_connection_error(server):
    async with respx.mock:
        respx.post(f"{BASE_URL}/api/notify").mock(side_effect=httpx.ConnectError("refused"))
        async with Client(server) as client:
            result = await client.call_tool("awtrix_notify", {"text": "hi"})
        assert result.is_error
        assert "awtrix_notify" in result.content[0].text
        assert "refused" in result.content[0].text


@pytest.mark.asyncio
async def test_awtrix_upsert_app_posts_to_named_route(server):
    async with respx.mock:
        route = respx.post(f"{BASE_URL}/api/custom", params={"name": "app_users"}).mock(
            return_value=httpx.Response(200)
        )
        async with Client(server, raise_exceptions=True) as client:
            result = await client.call_tool(
                "awtrix_upsert_app", {"name": "app_users", "text": "1,420", "lifetime": 300}
            )
        assert route.called
        assert result.structured_content["status"] == "upserted"
        assert result.structured_content["payload"]["lifetime"] == 300


@pytest.mark.asyncio
async def test_awtrix_upsert_app_surfaces_connection_error(server):
    async with respx.mock:
        respx.post(f"{BASE_URL}/api/custom", params={"name": "clock"}).mock(side_effect=httpx.ConnectError("refused"))
        async with Client(server) as client:
            result = await client.call_tool("awtrix_upsert_app", {"name": "clock", "text": "hi"})
        assert result.is_error
        assert "refused" in result.content[0].text


@pytest.mark.asyncio
async def test_awtrix_delete_app_sends_empty_body(server):
    async with respx.mock:
        route = respx.post(f"{BASE_URL}/api/custom", params={"name": "app_users"}).mock(
            return_value=httpx.Response(200)
        )
        async with Client(server, raise_exceptions=True) as client:
            result = await client.call_tool("awtrix_delete_app", {"name": "app_users"})
        assert route.called
        assert route.calls.last.request.content == b"{}"
        assert result.structured_content == {"status": "deleted", "name": "app_users"}


@pytest.mark.asyncio
async def test_awtrix_delete_app_surfaces_connection_error(server):
    async with respx.mock:
        respx.post(f"{BASE_URL}/api/custom", params={"name": "app_users"}).mock(
            side_effect=httpx.ConnectError("refused")
        )
        async with Client(server) as client:
            result = await client.call_tool("awtrix_delete_app", {"name": "app_users"})
        assert result.is_error
        assert "refused" in result.content[0].text


@pytest.mark.asyncio
async def test_awtrix_get_device_state_returns_parsed_stats(server):
    async with respx.mock:
        respx.get(f"{BASE_URL}/api/stats").mock(
            return_value=httpx.Response(200, json={"bat": 97, "lux": "8", "temp": "25", "ram": 152948})
        )
        async with Client(server, raise_exceptions=True) as client:
            result = await client.call_tool("awtrix_get_device_state", {})
        assert result.structured_content["battery"] == 97
        assert result.structured_content["ram_free"] == 152948


@pytest.mark.asyncio
async def test_awtrix_get_device_state_surfaces_malformed_response(server):
    async with respx.mock:
        respx.get(f"{BASE_URL}/api/stats").mock(return_value=httpx.Response(200, json={"unexpected": "shape"}))
        async with Client(server) as client:
            result = await client.call_tool("awtrix_get_device_state", {})
        assert result.is_error


@pytest.mark.asyncio
async def test_awtrix_set_settings_routes_brightness_and_power_separately(server):
    async with respx.mock:
        settings_route = respx.post(f"{BASE_URL}/api/settings").mock(return_value=httpx.Response(200))
        power_route = respx.post(f"{BASE_URL}/api/power").mock(return_value=httpx.Response(200))
        async with Client(server, raise_exceptions=True) as client:
            result = await client.call_tool("awtrix_set_settings", {"brightness": 80, "power": True})
        assert settings_route.called
        assert settings_route.calls.last.request.content == b'{"BRI":80}'
        assert power_route.called
        assert power_route.calls.last.request.content == b'{"power":true}'
        assert result.structured_content["settings"] == {"BRI": 80, "power": True}


@pytest.mark.asyncio
async def test_awtrix_set_settings_no_args_makes_no_http_calls(server):
    async with respx.mock:
        settings_route = respx.post(f"{BASE_URL}/api/settings").mock(return_value=httpx.Response(200))
        power_route = respx.post(f"{BASE_URL}/api/power").mock(return_value=httpx.Response(200))
        async with Client(server, raise_exceptions=True) as client:
            result = await client.call_tool("awtrix_set_settings", {})
        assert not settings_route.called
        assert not power_route.called
        assert result.structured_content == {"status": "updated", "settings": {}}


@pytest.mark.asyncio
async def test_awtrix_set_settings_transitions_only(server):
    async with respx.mock:
        route = respx.post(f"{BASE_URL}/api/settings").mock(return_value=httpx.Response(200))
        async with Client(server, raise_exceptions=True) as client:
            result = await client.call_tool("awtrix_set_settings", {"transitions": False})
        assert route.calls.last.request.content == b'{"ATRANS":false}'
        assert result.structured_content["settings"] == {"ATRANS": False}


@pytest.mark.asyncio
async def test_awtrix_set_settings_surfaces_connection_error(server):
    async with respx.mock:
        respx.post(f"{BASE_URL}/api/settings").mock(side_effect=httpx.ConnectError("refused"))
        async with Client(server) as client:
            result = await client.call_tool("awtrix_set_settings", {"brightness": 50})
        assert result.is_error
        assert "refused" in result.content[0].text


@pytest.mark.asyncio
async def test_awtrix_test_render_valid_payload_makes_no_http_calls(server):
    async with respx.mock:
        notify_route = respx.post(f"{BASE_URL}/api/notify")
        custom_route = respx.post(f"{BASE_URL}/api/custom")
        async with Client(server, raise_exceptions=True) as client:
            result = await client.call_tool(
                "awtrix_test_render", {"text": "hi", "kind": "notification", "color": "FF0000"}
            )
        assert result.structured_content["valid"] is True
        assert result.structured_content["payload"]["color"] == "FF0000"
        assert not notify_route.called
        assert not custom_route.called


@pytest.mark.asyncio
async def test_awtrix_test_render_invalid_color_returns_errors(server):
    # A dict for `color` mismatches ColorValue (str | list[int] | None), so the
    # SDK's own argument schema (built from the same type annotation) rejects it
    # before the tool body runs. This still exercises the "no unhandled crash"
    # contract: the Client call returns a controlled error result, not an exception.
    async with Client(server, raise_exceptions=True) as client:
        result = await client.call_tool("awtrix_test_render", {"text": "hi", "color": {"bad": "shape"}})
    assert result.is_error
    assert "color" in result.content[0].text


@pytest.mark.asyncio
async def test_awtrix_test_render_defaults_to_app_kind(server):
    async with Client(server, raise_exceptions=True) as client:
        result = await client.call_tool("awtrix_test_render", {"text": "hi", "rainbow": True})
    assert result.structured_content["valid"] is True
    assert result.structured_content["kind"] == "app"
    assert result.structured_content["payload"]["rainbow"] is True


def test_main_defaults_to_stdio_transport(monkeypatch):
    mock_server = MagicMock()
    monkeypatch.setattr("awtrix_mcp.server.build_server", lambda: mock_server)
    monkeypatch.setattr("sys.argv", ["mcp-server-awtrix"])
    main()
    mock_server.run.assert_called_once_with("stdio")


def test_main_sse_transport_passes_host_and_port(monkeypatch):
    mock_server = MagicMock()
    monkeypatch.setattr("awtrix_mcp.server.build_server", lambda: mock_server)
    monkeypatch.setattr(
        "sys.argv",
        ["mcp-server-awtrix", "--transport", "sse", "--host", "0.0.0.0", "--port", "9000"],
    )
    main()
    mock_server.run.assert_called_once_with("sse", host="0.0.0.0", port=9000)


def test_main_rejects_invalid_transport_from_env(monkeypatch, capsys):
    monkeypatch.setattr("awtrix_mcp.server.build_server", MagicMock())
    monkeypatch.setattr("sys.argv", ["mcp-server-awtrix"])
    monkeypatch.setenv("MCP_TRANSPORT", "bogus")
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
    assert "invalid choice: 'bogus'" in capsys.readouterr().err


@pytest.mark.asyncio
async def test_health_route_returns_ok():
    server_local = build_server(AwtrixSettings(base_url=BASE_URL))
    transport = httpx.ASGITransport(app=server_local.sse_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        response = await http_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
