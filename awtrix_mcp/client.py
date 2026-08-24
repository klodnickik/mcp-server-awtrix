"""Async HTTP client for the AWTRIX 3 device REST API."""

import asyncio
import logging
from typing import Any

import httpx
from pydantic import ValidationError

from .models import AppPayload, DeviceSettings, DeviceStats, NotificationPayload

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(5.0, connect=3.0)


class AwtrixError(Exception):
    """Base exception for all AwtrixClient errors."""


class AwtrixConnectionError(AwtrixError):
    """Raised when the device cannot be reached (transport-level failure). Retried."""


class AwtrixTimeoutError(AwtrixError):
    """Raised when a request to the device times out. Retried."""


class AwtrixResponseError(AwtrixError):
    """Raised when the device returns a non-2xx HTTP response, or an unparseable
    body from a 2xx response. Not retried."""


class AwtrixClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: httpx.Timeout | float = _DEFAULT_TIMEOUT,
        limits: httpx.Limits | None = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        """
        max_retries is the total number of attempts (including the first),
        not the number of retries after the first. max_retries=1 means no retries.
        """
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

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        attempt = 0
        while True:
            try:
                response = await self._http.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.TimeoutException as exc:
                if attempt >= self._max_retries - 1:
                    logger.warning("%s %s timed out after %d attempt(s): %s", method, url, attempt + 1, exc)
                    raise AwtrixTimeoutError(str(exc)) from exc
                logger.debug("%s %s timed out (attempt %d), retrying: %s", method, url, attempt + 1, exc)
            except httpx.HTTPStatusError as exc:
                raise AwtrixResponseError(
                    f"{exc.response.status_code} from {exc.request.url}: {exc.response.text}"
                ) from exc
            except httpx.RequestError as exc:
                if attempt >= self._max_retries - 1:
                    logger.warning("%s %s failed after %d attempt(s): %s", method, url, attempt + 1, exc)
                    raise AwtrixConnectionError(str(exc)) from exc
                logger.debug("%s %s failed (attempt %d), retrying: %s", method, url, attempt + 1, exc)

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
        await self._request("POST", "/api/notify", json=payload.model_dump(by_alias=True, exclude_none=True))

    async def get_stats(self) -> DeviceStats:
        response = await self._request("GET", "/api/stats")
        try:
            return DeviceStats.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            # response.json() raises json.JSONDecodeError, a ValueError subclass
            raise AwtrixResponseError(f"Malformed response from /api/stats: {exc}") from exc

    async def set_settings(self, settings: DeviceSettings) -> None:
        await self._request("POST", "/api/settings", json=settings.model_dump(by_alias=True, exclude_none=True))

    async def set_power(self, state: bool) -> None:
        await self._request("POST", "/api/power", json={"power": state})

    async def send_rtttl(self, rtttl: str) -> None:
        await self._request("POST", "/api/rtttl", content=rtttl, headers={"Content-Type": "text/plain"})
