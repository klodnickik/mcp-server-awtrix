"""Metric Poller Daemon Entrypoint.

Discovers `apps/*.yaml` manifests, schedules one polling job per enabled
manifest (fetch -> transform -> evaluate display rules / sub-apps -> push to
the AWTRIX device), and hot-reloads manifests on file changes without a
process restart.
"""

import argparse
import asyncio
import contextlib
import hashlib
import logging
import os
import signal
import sys
from collections.abc import Mapping
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


DAEMON_HEARTBEAT_INTERVAL_SECONDS = 30


def _touch_heartbeat(path: Path) -> None:
    try:
        path.touch()
    except OSError as exc:
        logger.warning("failed to write heartbeat file %s: %s", path, exc)


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
    except httpx.HTTPStatusError as exc:
        raise SourceFetchError(
            f"{exc.response.status_code} from {exc.request.url}: {exc.response.text[:500]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise SourceFetchError(str(exc)) from exc
    except ValueError as exc:
        raise SourceFetchError(f"invalid JSON response: {exc}") from exc


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
            await client.send_app(manifest.name or manifest.app_id, payload)
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
    except SourceFetchError as exc:
        logger.warning("source fetch failed for %s: %s", manifest.app_id, exc)
        return

    try:
        context = _build_context(manifest, data)
    except ExpressionError:
        return  # _build_context already logs which transform failed

    try:
        if manifest.display:
            await _run_display_rules(client, manifest, context)
        if manifest.sub_apps:
            await _run_sub_apps(client, manifest, context)
    except (ExpressionError, AwtrixError) as exc:
        logger.warning("display/sub-app push failed for %s: %s", manifest.app_id, exc)


class DaemonState:
    def __init__(self, scheduler: AsyncIOScheduler, http: httpx.AsyncClient, client: AwtrixClient) -> None:
        self.scheduler = scheduler
        self.http = http
        self.client = client
        self.manifests: dict[Path, tuple[ManifestConfig, str]] = {}


def _schedule(state: DaemonState, manifest: ManifestConfig) -> None:
    if not manifest.enabled:
        with contextlib.suppress(JobLookupError):
            state.scheduler.remove_job(manifest.app_id)
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


async def _reload_apps_dir(state: DaemonState, apps_dir: Path, env: Mapping[str, str]) -> None:
    current_paths = sorted(list(apps_dir.glob("*.yaml")) + list(apps_dir.glob("*.yml")))

    seen_app_ids: dict[str, Path] = {}
    for path in current_paths:
        try:
            raw_bytes = path.read_bytes()
        except OSError as exc:
            logger.warning("skipping manifest %s: unreadable: %s", path, exc)
            continue
        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        previous = state.manifests.get(path)
        if previous is not None and previous[1] == content_hash:
            seen_app_ids[previous[0].app_id] = path
            continue
        try:
            manifest = load_manifest(path, env)
        except ManifestError as exc:
            logger.warning("skipping manifest %s: %s", path, exc)
            continue
        if manifest.app_id in seen_app_ids:
            logger.warning(
                "skipping manifest %s: app_id '%s' already used by %s",
                path, manifest.app_id, seen_app_ids[manifest.app_id],
            )
            continue
        seen_app_ids[manifest.app_id] = path
        state.manifests[path] = (manifest, content_hash)
        _schedule(state, manifest)

    removed_paths = set(state.manifests) - set(current_paths)
    for path in removed_paths:
        manifest, _hash = state.manifests.pop(path)
        with contextlib.suppress(JobLookupError):
            state.scheduler.remove_job(manifest.app_id)
        app_names = [manifest.name or manifest.app_id] if manifest.display else []
        app_names += [sub.name for sub in manifest.sub_apps]
        for name in app_names:
            try:
                await state.client.delete_app(name)
            except AwtrixError as exc:
                logger.warning("failed to delete app %s for removed manifest %s: %s", name, path, exc)


async def watch_apps_dir(
    state: DaemonState, apps_dir: Path, env: Mapping[str, str], stop_event: asyncio.Event
) -> None:
    async for _changes in watchfiles.awatch(apps_dir, stop_event=stop_event):
        await _reload_apps_dir(state, apps_dir, env)


async def run_daemon(apps_dir: Path, settings: AwtrixSettings) -> None:
    dotenv.load_dotenv(override=False)

    scheduler = AsyncIOScheduler()
    http = httpx.AsyncClient()
    client = AwtrixClient(base_url=settings.base_url)
    state = DaemonState(scheduler, http, client)
    heartbeat_path = Path(
        os.environ.get("DAEMON_HEARTBEAT_FILE", "/tmp/awtrix-daemon-heartbeat")
    )

    try:
        await _reload_apps_dir(state, apps_dir, os.environ)
        scheduler.add_job(
            _touch_heartbeat,
            "interval",
            seconds=DAEMON_HEARTBEAT_INTERVAL_SECONDS,
            id="__heartbeat__",
            next_run_time=datetime.now(),
            args=[heartbeat_path],
        )
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


def _run_validate(file: Path | None, apps_dir: Path) -> int:
    paths = [file] if file else sorted(list(apps_dir.glob("*.yaml")) + list(apps_dir.glob("*.yml")))
    if not paths:
        print(f"no manifest files found in {apps_dir}", file=sys.stderr)
        return 1
    exit_code = 0
    seen_app_ids: dict[str, Path] = {}
    for path in paths:
        try:
            manifest = load_manifest(path, os.environ)
        except ManifestError as exc:
            print(f"INVALID {exc}", file=sys.stderr)
            exit_code = 1
            continue
        if manifest.app_id in seen_app_ids:
            print(
                f"INVALID {path}: app_id '{manifest.app_id}' already used by {seen_app_ids[manifest.app_id]}",
                file=sys.stderr,
            )
            exit_code = 1
            continue
        seen_app_ids[manifest.app_id] = path
        print(f"OK {path} (app_id={manifest.app_id})")
    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(prog="awtrix-daemon")
    parser.add_argument(
        "--apps-dir", type=Path, default=Path(os.environ.get("APPS_DIR", "apps"))
    )
    subparsers = parser.add_subparsers(dest="command")
    validate_parser = subparsers.add_parser("validate", help="Validate manifest YAML syntax/schema and exit")
    validate_parser.add_argument(
        "file",
        type=Path,
        nargs="?",
        default=None,
        help="Specific manifest file to validate; validates all files under --apps-dir if omitted",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    if args.command == "validate":
        sys.exit(_run_validate(args.file, args.apps_dir))

    print("awtrix-daemon: Metric Daemon starting...", file=sys.stderr)

    asyncio.run(run_daemon(args.apps_dir, AwtrixSettings()))


if __name__ == "__main__":
    main()
