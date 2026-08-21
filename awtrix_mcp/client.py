"""Async HTTP client for the AWTRIX 3 device REST API."""

import asyncio

import httpx

from .models import AppPayload, DeviceSettings, DeviceStats, NotificationPayload


class AwtrixError(Exception):
    """Base exception for all AwtrixClient errors."""


class AwtrixConnectionError(AwtrixError):
    """Raised when the device cannot be reached (transport-level failure)."""


class AwtrixTimeoutError(AwtrixError):
    """Raised when a request to the device times out."""


class AwtrixResponseError(AwtrixError):
    """Raised when the device returns a non-2xx HTTP response."""


class AwtrixClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: httpx.Timeout | float = httpx.Timeout(5.0, connect=3.0),
        limits: httpx.Limits | None = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._http = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            limits=limits or httpx.Limits(max_connections=5, max_keepalive_connections=5),
        )

    async def __aenter__(self) -> "AwtrixClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        attempt = 0
        while True:
            try:
                response = await self._http.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.TimeoutException as exc:
                if attempt >= self._max_retries - 1:
                    raise AwtrixTimeoutError(str(exc)) from exc
            except httpx.HTTPStatusError as exc:
                raise AwtrixResponseError(
                    f"{exc.response.status_code} from {exc.request.url}: {exc.response.text}"
                ) from exc
            except httpx.RequestError as exc:
                if attempt >= self._max_retries - 1:
                    raise AwtrixConnectionError(str(exc)) from exc

            await asyncio.sleep(self._backoff_factor * 2**attempt)
            attempt += 1

    async def send_app(self, name: str, payload: AppPayload) -> None:
        await self._request(
            "POST",
            "/api/custom",
            params={"name": name},
            json=payload.model_dump(by_alias=True, exclude_none=True),
        )

    async def delete_app(self, name: str) -> None:
        await self._request("POST", "/api/custom", params={"name": name}, json={})

    async def send_notification(self, payload: NotificationPayload) -> None:
        await self._request(
            "POST", "/api/notify", json=payload.model_dump(by_alias=True, exclude_none=True)
        )

    async def get_stats(self) -> DeviceStats:
        response = await self._request("GET", "/api/stats")
        return DeviceStats.model_validate(response.json())

    async def set_settings(self, settings: DeviceSettings) -> None:
        await self._request(
            "POST", "/api/settings", json=settings.model_dump(by_alias=True, exclude_none=True)
        )

    async def set_power(self, state: bool) -> None:
        await self._request("POST", "/api/power", json={"power": state})

    async def send_rtttl(self, rtttl: str) -> None:
        await self._request(
            "POST", "/api/rtttl", content=rtttl, headers={"Content-Type": "text/plain"}
        )
