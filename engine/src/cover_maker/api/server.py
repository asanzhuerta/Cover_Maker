"""Run the local API: bind 127.0.0.1 on a free port and announce it on stdout.

Handshake: the first stdout line is a JSON object
``{"event": "ready", "port": <int>, "pid": <int>, "version": <str>}`` that the
desktop shell reads to learn where the engine listens. The session token comes
from the ``COVER_MAKER_TOKEN`` environment variable (never from argv, which is
visible to other processes). If ``COVER_MAKER_PARENT_PID`` is set, the engine
exits when that process disappears; outside Windows, whose Job Object already
ends the whole tree with the shell, it first stops its own child processes
(ADR-013).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import socket
import sys
import tempfile
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import psutil
import uvicorn

from .. import __version__, diagnostics
from ..paths import Paths
from . import discovery
from .app import create_app
from .engine import EngineService
from .security import AccessPolicy

TOKEN_ENV = "COVER_MAKER_TOKEN"
PARENT_ENV = "COVER_MAKER_PARENT_PID"


def _stop_children() -> None:
    """Kill the separation worker and running tools (ffmpeg, yt-dlp)."""
    for child in psutil.Process().children(recursive=True):
        with contextlib.suppress(psutil.Error):
            child.kill()


def _watch_parent(parent_pid: int, server: uvicorn.Server) -> None:
    while psutil.pid_exists(parent_pid):
        time.sleep(1)
    if sys.platform != "win32":
        _stop_children()
    server.should_exit = True


def build_service(demo: bool) -> EngineService:
    """Real engine, or a demo engine with a fake separator and its own data folder."""
    if not demo:
        return EngineService(Paths.default())
    from ..separation.backends.fake import FakeBackend
    from ..separation.service import InProcessService

    paths = Paths(Path(tempfile.gettempdir()) / "cover_maker_demo").ensure()
    service = EngineService(paths, separation=InProcessService(FakeBackend()), demo=True)
    for model in service.catalog.models.values():
        service.installs.record(model, None)
    return service


def _log_failures(service: EngineService) -> None:
    """Keep failures in logs/engine.log: the installed app has no console."""
    service.paths.logs.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        service.paths.logs / diagnostics.LOG_FILE, maxBytes=1_000_000, backupCount=2,
        encoding="utf-8",
    )  # fmt: skip
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    log = logging.getLogger("cover_maker")
    log.info("engine %s starting", __version__)

    def record(event: dict[str, Any]) -> None:
        kind = str(event.get("type", ""))
        if kind.endswith(".failed") or kind in ("job.finished", "separation.retry"):
            details = {k: v for k, v in event.items() if k not in ("seq", "type")}
            level = logging.WARNING if kind.endswith(".failed") else logging.INFO
            log.log(level, "%s %s", kind, details)

    service.bus.subscribe(record)


def serve(host: str = "127.0.0.1", *, demo: bool = False) -> None:
    token = os.environ.get(TOKEN_ENV)
    if not token or len(token) < 32:
        raise SystemExit(f"{TOKEN_ENV} must be set to a token of at least 32 characters.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, 0))
    port: int = sock.getsockname()[1]

    client_token = discovery.new_client_token() if discovery.enabled() else None
    policy = AccessPolicy(
        token=token, host=f"{host}:{port}",
        client_tokens=frozenset({client_token}) if client_token else frozenset(),
    )  # fmt: skip
    service = build_service(demo)
    _log_failures(service)
    service.start()
    config = uvicorn.Config(create_app(policy, service), log_level="warning", access_log=False)
    server = uvicorn.Server(config)

    parent = os.environ.get(PARENT_ENV)
    if parent and parent.isdigit():
        threading.Thread(target=_watch_parent, args=(int(parent), server), daemon=True).start()

    handshake = {"event": "ready", "port": port, "pid": os.getpid(), "version": __version__}
    sys.stdout.write(json.dumps(handshake) + "\n")
    sys.stdout.flush()
    home = service.paths.home
    if client_token:
        info = discovery.Discovery(
            port=port, token=client_token, pid=os.getpid(), version=__version__, host=host
        )
        discovery.write(home, info)
    try:
        server.run(sockets=[sock])
    finally:
        if client_token:
            discovery.remove(home, os.getpid())
        service.stop()
