"""Metric Poller Daemon Entrypoint.

Discovers `apps/*.yaml` manifests, schedules one polling job per enabled
manifest (fetch -> transform -> evaluate display rules / sub-apps -> push to
the AWTRIX device), and hot-reloads manifests on file changes without a
process restart.
"""

import argparse
import asyncio
import hashlib
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import dotenv
import httpx
import watchfiles
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .client import AwtrixClient, AwtrixError
from .config import AwtrixSettings, ManifestConfig, ManifestError, SourceConfig, load_manifest
from .evaluator import AttrDict, ExpressionError, evaluate_condition, evaluate_expression, render_template
from .models import AppPayload, NotificationPayload, TextSegment

logger = logging.getLogger(__name__)


class SourceFetchError(Exception):
    """Raised when a manifest's HTTP source cannot be fetched or parsed."""


def _wrap_json(data: Any) -> Any:
    if isinstance(data, dict):
        return AttrDict(data)
    if isinstance(data, list):
        return [_wrap_json(item) for item in data]
    return data


async def fetch_source(http: httpx.AsyncClient, source: SourceConfig) -> Any:
    auth = None
    if source.auth is not None:
        auth = (source.auth.username, source.auth.password)
    try:
        response = await http.request(
            source.method, source.url, headers=source.headers, json=source.body, auth=auth
        )
        response.raise_for_status()
        return _wrap_json(response.json())
    except httpx.HTTPError as exc:
        raise SourceFetchError(str(exc)) from exc


def _build_context(manifest: ManifestConfig, data: Any) -> dict:
    context: dict[str, Any] = {"data": data}
    for name, expr in manifest.transform.items():
        try:
            context[name] = evaluate_expression(expr, context)
        except ExpressionError as exc:
            logger.warning(
                "transform '%s' failed for manifest %s: %s", name, manifest.app_id, exc
            )
            raise
    return context


def _render_segments(segments: list, context: dict) -> list[TextSegment]:
    return [TextSegment(text=render_template(s.text, context), color=s.color) for s in segments]


async def _run_display_rules(client: AwtrixClient, manifest: ManifestConfig, context: dict) -> None:
    for rule in manifest.display:
        if evaluate_condition(rule.condition, context):
            segments = _render_segments(rule.text, context)
            payload = AppPayload(text=segments, icon=rule.icon)
            await client.send_app(manifest.name, payload)
            if rule.notify:
                await client.send_notification(NotificationPayload(text=segments, icon=rule.icon))
            return
    logger.warning("no display rule matched for manifest %s", manifest.app_id)


async def _run_sub_apps(client: AwtrixClient, manifest: ManifestConfig, context: dict) -> None:
    for sub in manifest.sub_apps:
        if sub.show_if is None or evaluate_condition(sub.show_if, context):
            segments = _render_segments(sub.text, context)
            await client.send_app(sub.name, AppPayload(text=segments, icon=sub.icon))
        else:
            await client.delete_app(sub.name)


async def poll_once(
    http: httpx.AsyncClient, client: AwtrixClient, manifest: ManifestConfig
) -> None:
    try:
        data = await fetch_source(http, manifest.source)
        context = _build_context(manifest, data)
        if manifest.display:
            await _run_display_rules(client, manifest, context)
        if manifest.sub_apps:
            await _run_sub_apps(client, manifest, context)
    except (SourceFetchError, ExpressionError, AwtrixError) as exc:
        logger.warning("poll cycle failed for %s: %s", manifest.app_id, exc)


class DaemonState:
    def __init__(self, scheduler: AsyncIOScheduler, http: httpx.AsyncClient, client: AwtrixClient) -> None:
        self.scheduler = scheduler
        self.http = http
        self.client = client
        self.manifests: dict[Path, tuple[ManifestConfig, str]] = {}


def _schedule(state: DaemonState, manifest: ManifestConfig) -> None:
    if not manifest.enabled:
        try:
            state.scheduler.remove_job(manifest.app_id)
        except JobLookupError:
            pass
        return
    state.scheduler.add_job(
        poll_once,
        "interval",
        seconds=manifest.interval_seconds,
        id=manifest.app_id,
        replace_existing=True,
        next_run_time=datetime.now(),
        args=[state.http, state.client, manifest],
    )


async def _reload_apps_dir(state: DaemonState, apps_dir: Path, env: dict) -> None:
    current_paths = sorted(list(apps_dir.glob("*.yaml")) + list(apps_dir.glob("*.yml")))

    for path in current_paths:
        raw_bytes = path.read_bytes()
        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        previous = state.manifests.get(path)
        if previous is not None and previous[1] == content_hash:
            continue
        try:
            manifest = load_manifest(path, env)
        except ManifestError as exc:
            logger.warning("skipping manifest %s: %s", path, exc)
            continue
        state.manifests[path] = (manifest, content_hash)
        _schedule(state, manifest)

    removed_paths = set(state.manifests) - set(current_paths)
    for path in removed_paths:
        manifest, _hash = state.manifests.pop(path)
        try:
            state.scheduler.remove_job(manifest.app_id)
        except JobLookupError:
            pass
        app_names = [manifest.name] if manifest.display else []
        app_names += [sub.name for sub in manifest.sub_apps]
        for name in app_names:
            await state.client.delete_app(name)


async def watch_apps_dir(
    state: DaemonState, apps_dir: Path, env: dict, stop_event: asyncio.Event
) -> None:
    async for _changes in watchfiles.awatch(apps_dir, stop_event=stop_event):
        await _reload_apps_dir(state, apps_dir, env)


async def run_daemon(apps_dir: Path, settings: AwtrixSettings) -> None:
    dotenv.load_dotenv(override=False)

    scheduler = AsyncIOScheduler()
    http = httpx.AsyncClient()
    client = AwtrixClient(base_url=settings.base_url)
    state = DaemonState(scheduler, http, client)

    try:
        await _reload_apps_dir(state, apps_dir, os.environ)
        scheduler.start()

        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        await watch_apps_dir(state, apps_dir, os.environ, stop_event)
    finally:
        scheduler.shutdown(wait=False)
        await http.aclose()
        await client.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="awtrix-daemon")
    parser.add_argument(
        "--apps-dir", type=Path, default=Path(os.environ.get("APPS_DIR", "apps"))
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    print("awtrix-daemon: Metric Daemon starting...", file=sys.stderr)

    asyncio.run(run_daemon(args.apps_dir, AwtrixSettings()))


if __name__ == "__main__":
    main()
