import httpx
import pytest
import respx

from awtrix_mcp.client import (
    AwtrixClient,
    AwtrixConnectionError,
    AwtrixResponseError,
    AwtrixTimeoutError,
)
from awtrix_mcp.models import AppPayload, DeviceSettings, NotificationPayload

BASE_URL = "http://awtrix.local"


@pytest.mark.asyncio
async def test_send_app_posts_expected_payload():
    async with respx.mock:
        route = respx.post(f"{BASE_URL}/api/custom", params={"name": "clock"}).mock(return_value=httpx.Response(200))
        async with AwtrixClient(base_url=BASE_URL) as client:
            await client.send_app("clock", AppPayload(text="hi"))
        assert route.called
        assert route.calls.last.request.content == (
            b'{"text":"hi","duration":5,"repeat":-1,"rainbow":false,"save":false}'
        )


@pytest.mark.asyncio
async def test_delete_app_sends_empty_json_body():
    async with respx.mock:
        route = respx.post(f"{BASE_URL}/api/custom", params={"name": "clock"}).mock(return_value=httpx.Response(200))
        async with AwtrixClient(base_url=BASE_URL) as client:
            await client.delete_app("clock")
        assert route.called
        assert route.calls.last.request.content == b"{}"


@pytest.mark.asyncio
async def test_send_notification_posts_expected_payload():
    async with respx.mock:
        route = respx.post(f"{BASE_URL}/api/notify").mock(return_value=httpx.Response(200))
        async with AwtrixClient(base_url=BASE_URL) as client:
            await client.send_notification(NotificationPayload(text="Build Failed", color="FF0000"))
        assert route.called
        assert route.calls.last.request.content == (
            b'{"text":"Build Failed","color":"FF0000","hold":false,"duration":5,"wakeup":false,"stack":true}'
        )


@pytest.mark.asyncio
async def test_get_stats_parses_response():
    async with respx.mock:
        respx.get(f"{BASE_URL}/api/stats").mock(
            return_value=httpx.Response(200, json={"bat": 97, "lux": "8", "temp": "25", "ram": 152948})
        )
        async with AwtrixClient(base_url=BASE_URL) as client:
            stats = await client.get_stats()
        assert stats.battery == 97
        assert stats.ram_free == 152948


@pytest.mark.asyncio
async def test_set_settings_posts_expected_payload():
    async with respx.mock:
        route = respx.post(f"{BASE_URL}/api/settings").mock(return_value=httpx.Response(200))
        async with AwtrixClient(base_url=BASE_URL) as client:
            await client.set_settings(DeviceSettings(brightness=120, power=True, transitions=False))
        assert route.called
        assert route.calls.last.request.content == b'{"BRI":120,"MATP":true,"ATRANS":false}'


@pytest.mark.asyncio
async def test_set_power_posts_expected_payload():
    async with respx.mock:
        route = respx.post(f"{BASE_URL}/api/power").mock(return_value=httpx.Response(200))
        async with AwtrixClient(base_url=BASE_URL) as client:
            await client.set_power(True)
        assert route.called
        assert route.calls.last.request.content == b'{"power":true}'


@pytest.mark.asyncio
async def test_send_rtttl_sends_raw_text_body():
    async with respx.mock:
        route = respx.post(f"{BASE_URL}/api/rtttl").mock(return_value=httpx.Response(200))
        async with AwtrixClient(base_url=BASE_URL) as client:
            await client.send_rtttl("d=4,o=5,b=200:c")
        assert route.called
        assert route.calls.last.request.content == b"d=4,o=5,b=200:c"


@pytest.mark.asyncio
async def test_timeout_raises_awtrix_timeout_error():
    async with respx.mock:
        respx.get(f"{BASE_URL}/api/stats").mock(side_effect=httpx.TimeoutException("timed out"))
        async with AwtrixClient(base_url=BASE_URL, max_retries=1, backoff_factor=0.01) as client:
            with pytest.raises(AwtrixTimeoutError):
                await client.get_stats()


@pytest.mark.asyncio
async def test_http_status_error_raises_awtrix_response_error():
    async with respx.mock:
        respx.get(f"{BASE_URL}/api/stats").mock(return_value=httpx.Response(500))
        async with AwtrixClient(base_url=BASE_URL, max_retries=1, backoff_factor=0.01) as client:
            with pytest.raises(AwtrixResponseError):
                await client.get_stats()


@pytest.mark.asyncio
async def test_http_status_error_does_not_retry():
    async with respx.mock:
        route = respx.get(f"{BASE_URL}/api/stats").mock(return_value=httpx.Response(500))
        async with AwtrixClient(base_url=BASE_URL, max_retries=3, backoff_factor=0.01) as client:
            with pytest.raises(AwtrixResponseError):
                await client.get_stats()
        assert route.call_count == 1


@pytest.mark.asyncio
async def test_connect_error_raises_awtrix_connection_error():
    async with respx.mock:
        respx.get(f"{BASE_URL}/api/stats").mock(side_effect=httpx.ConnectError("refused"))
        async with AwtrixClient(base_url=BASE_URL, max_retries=1, backoff_factor=0.01) as client:
            with pytest.raises(AwtrixConnectionError):
                await client.get_stats()


@pytest.mark.asyncio
async def test_retry_succeeds_after_transient_timeouts():
    async with respx.mock:
        route = respx.get(f"{BASE_URL}/api/stats")
        route.side_effect = [
            httpx.TimeoutException("timed out"),
            httpx.Response(200, json={"bat": 97, "lux": "8", "temp": "25", "ram": 152948}),
        ]
        async with AwtrixClient(base_url=BASE_URL, max_retries=2, backoff_factor=0.01) as client:
            stats = await client.get_stats()
        assert stats.battery == 97
        assert route.call_count == 2


@pytest.mark.asyncio
async def test_retry_exhausted_raises_awtrix_timeout_error():
    async with respx.mock:
        route = respx.get(f"{BASE_URL}/api/stats").mock(side_effect=httpx.TimeoutException("timed out"))
        async with AwtrixClient(base_url=BASE_URL, max_retries=2, backoff_factor=0.01) as client:
            with pytest.raises(AwtrixTimeoutError):
                await client.get_stats()
        assert route.call_count == 2


@pytest.mark.asyncio
async def test_get_stats_malformed_json_raises_awtrix_response_error():
    async with respx.mock:
        respx.get(f"{BASE_URL}/api/stats").mock(
            return_value=httpx.Response(200, content="not json", headers={"Content-Type": "text/plain"})
        )
        async with AwtrixClient(base_url=BASE_URL) as client:
            with pytest.raises(AwtrixResponseError):
                await client.get_stats()


@pytest.mark.asyncio
async def test_get_stats_missing_required_field_raises_awtrix_response_error():
    async with respx.mock:
        respx.get(f"{BASE_URL}/api/stats").mock(
            return_value=httpx.Response(200, json={"lux": "8", "temp": "25", "ram": 152948})
        )
        async with AwtrixClient(base_url=BASE_URL) as client:
            with pytest.raises(AwtrixResponseError):
                await client.get_stats()
