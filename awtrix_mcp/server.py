"""MCP Server Entrypoint — registers AWTRIX device tools over stdio/SSE."""

import argparse
import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations
from pydantic import ValidationError

from . import __version__
from .client import AwtrixClient
from .config import AwtrixSettings
from .models import AppPayload, ColorValue, DeviceSettings, NotificationPayload, TextSegment

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    client: AwtrixClient


def build_server(settings: AwtrixSettings | None = None) -> MCPServer:
    resolved_settings = settings or AwtrixSettings()

    @asynccontextmanager
    async def app_lifespan(_server: MCPServer) -> AsyncIterator[AppContext]:
        async with AwtrixClient(base_url=resolved_settings.base_url) as client:
            yield AppContext(client=client)

    server = MCPServer("awtrix", version=__version__, lifespan=app_lifespan)

    @server.tool(annotations=ToolAnnotations(destructive_hint=False, idempotent_hint=False, open_world_hint=True))
    async def awtrix_notify(
        text: str | list[TextSegment],
        ctx: Context,
        icon: str | None = None,
        color: ColorValue = None,
        sound: str | None = None,
        rtttl: str | None = None,
        hold: bool = False,
        duration: int = 5,
        wakeup: bool = False,
        stack: bool = True,
    ) -> dict[str, Any]:
        """Push an instant, high-priority notification to the AWTRIX display."""
        payload = NotificationPayload(
            text=text, icon=icon, color=color, sound=sound, rtttl=rtttl,
            hold=hold, duration=duration, wakeup=wakeup, stack=stack,
        )
        await ctx.request_context.lifespan_context.client.send_notification(payload)
        return {"status": "sent", "payload": payload.model_dump(by_alias=True, exclude_none=True)}

    @server.tool(annotations=ToolAnnotations(destructive_hint=False, idempotent_hint=True, open_world_hint=True))
    async def awtrix_upsert_app(
        name: str,
        text: str | list[TextSegment],
        ctx: Context,
        icon: str | None = None,
        duration: int = 5,
        repeat: int = -1,
        rainbow: bool = False,
        color: ColorValue = None,
        lifetime: int | None = None,
        lifetime_mode: int | None = None,
        save: bool = False,
    ) -> dict[str, Any]:
        """Create or update a persistent custom app in the display carousel."""
        payload = AppPayload(
            text=text, icon=icon, duration=duration, repeat=repeat, rainbow=rainbow,
            color=color, lifetime=lifetime, lifetime_mode=lifetime_mode, save=save,
        )
        await ctx.request_context.lifespan_context.client.send_app(name, payload)
        return {"status": "upserted", "name": name, "payload": payload.model_dump(by_alias=True, exclude_none=True)}

    @server.tool(annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=True, open_world_hint=True))
    async def awtrix_delete_app(name: str, ctx: Context) -> dict[str, Any]:
        """Remove a custom app from the display cycle by name."""
        await ctx.request_context.lifespan_context.client.delete_app(name)
        return {"status": "deleted", "name": name}

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=True))
    async def awtrix_get_device_state(ctx: Context) -> dict[str, Any]:
        """Return current AWTRIX hardware metrics: battery, lux, temperature, active app (if available)."""
        stats = await ctx.request_context.lifespan_context.client.get_stats()
        return stats.model_dump(exclude_none=True)

    @server.tool(annotations=ToolAnnotations(destructive_hint=False, idempotent_hint=True, open_world_hint=True))
    async def awtrix_set_settings(
        ctx: Context,
        brightness: int | None = None,
        power: bool | None = None,
        transitions: bool | None = None,
    ) -> dict[str, Any]:
        """Configure display brightness, transition animations, and screen power state."""
        client = ctx.request_context.lifespan_context.client
        applied: dict[str, Any] = {}
        if brightness is not None or transitions is not None:
            settings = DeviceSettings(brightness=brightness, transitions=transitions)
            await client.set_settings(settings)
            applied.update(settings.model_dump(by_alias=True, exclude_none=True))
        if power is not None:
            await client.set_power(power)
            applied["power"] = power
        return {"status": "updated", "settings": applied}

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False))
    async def awtrix_test_render(
        text: str | list[TextSegment],
        kind: Literal["notification", "app"] = "app",
        icon: str | None = None,
        color: ColorValue = None,
        duration: int = 5,
        rainbow: bool = False,
        sound: str | None = None,
        rtttl: str | None = None,
        hold: bool = False,
        wakeup: bool = False,
    ) -> dict[str, Any]:
        """Validate and preview a rendered notification/app payload with no hardware side-effects."""
        try:
            if kind == "notification":
                payload = NotificationPayload(
                    text=text, icon=icon, color=color, sound=sound, rtttl=rtttl,
                    hold=hold, duration=duration, wakeup=wakeup,
                )
            else:
                payload = AppPayload(text=text, icon=icon, duration=duration, rainbow=rainbow, color=color)
        except ValidationError as exc:
            return {"valid": False, "errors": exc.errors(include_url=False)}
        return {"valid": True, "kind": kind, "payload": payload.model_dump(by_alias=True, exclude_none=True)}

    return server


def _transport_type(value: str) -> str:
    if value not in ("stdio", "sse"):
        raise argparse.ArgumentTypeError(f"invalid choice: {value!r} (choose from 'stdio', 'sse')")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(prog="mcp-server-awtrix")
    parser.add_argument(
        "--transport", type=_transport_type, default=os.environ.get("MCP_TRANSPORT", "stdio")
    )
    parser.add_argument("--host", default=os.environ.get("MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=os.environ.get("MCP_PORT", "8000"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    print("mcp-server-awtrix: MCP Server starting...", file=sys.stderr)

    server = build_server()
    if args.transport == "stdio":
        server.run("stdio")
    else:
        server.run("sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
