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
import threading
import time

import psutil
import uvicorn

from .. import __version__
from .app import create_app
from .security import AccessPolicy

TOKEN_ENV = "COVER_MAKER_TOKEN"
PARENT_ENV = "COVER_MAKER_PARENT_PID"


def _watch_parent(parent_pid: int, server: uvicorn.Server) -> None:
    while psutil.pid_exists(parent_pid):
        time.sleep(1)
    server.should_exit = True


def serve(host: str = "127.0.0.1") -> None:
    token = os.environ.get(TOKEN_ENV)
    if not token or len(token) < 32:
        raise SystemExit(f"{TOKEN_ENV} must be set to a token of at least 32 characters.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, 0))
    port: int = sock.getsockname()[1]

    policy = AccessPolicy(token=token, host=f"{host}:{port}")
    config = uvicorn.Config(create_app(policy), log_level="warning", access_log=False)
    server = uvicorn.Server(config)

    parent = os.environ.get(PARENT_ENV)
    if parent and parent.isdigit():
        threading.Thread(target=_watch_parent, args=(int(parent), server), daemon=True).start()

    handshake = {"event": "ready", "port": port, "pid": os.getpid(), "version": __version__}
    sys.stdout.write(json.dumps(handshake) + "\n")
    sys.stdout.flush()
    server.run(sockets=[sock])
