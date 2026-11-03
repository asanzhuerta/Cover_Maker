"""Run the local API: bind 127.0.0.1 on a free port and announce it on stdout.

Handshake: the first stdout line is a JSON object
``{"event": "ready", "port": <int>, "pid": <int>, "version": <str>}`` that the
desktop shell reads to learn where the engine listens. The session token comes
from the ``COVER_MAKER_TOKEN`` environment variable (never from argv, which is
visible to other processes). If ``COVER_MAKER_PARENT_PID`` is set, the engine
exits when that process disappears.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

import psutil
import uvicorn

from .. import __version__
from ..paths import Paths
from .app import create_app
from .engine import EngineService
from .security import AccessPolicy

TOKEN_ENV = "COVER_MAKER_TOKEN"
PARENT_ENV = "COVER_MAKER_PARENT_PID"


def _watch_parent(parent_pid: int, server: uvicorn.Server) -> None:
    while psutil.pid_exists(parent_pid):
        time.sleep(1)
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


def serve(host: str = "127.0.0.1", *, demo: bool = False) -> None:
    token = os.environ.get(TOKEN_ENV)
    if not token or len(token) < 32:
        raise SystemExit(f"{TOKEN_ENV} must be set to a token of at least 32 characters.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, 0))
    port: int = sock.getsockname()[1]

    policy = AccessPolicy(token=token, host=f"{host}:{port}")
    service = build_service(demo)
    service.start()
    config = uvicorn.Config(create_app(policy, service), log_level="warning", access_log=False)
    server = uvicorn.Server(config)

    parent = os.environ.get(PARENT_ENV)
    if parent and parent.isdigit():
        threading.Thread(target=_watch_parent, args=(int(parent), server), daemon=True).start()

    handshake = {"event": "ready", "port": port, "pid": os.getpid(), "version": __version__}
    sys.stdout.write(json.dumps(handshake) + "\n")
    sys.stdout.flush()
    try:
        server.run(sockets=[sock])
    finally:
        service.stop()
