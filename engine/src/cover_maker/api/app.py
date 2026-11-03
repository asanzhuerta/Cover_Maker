"""FastAPI application for the local engine API."""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .. import __version__
from .security import AccessMiddleware, AccessPolicy

HEARTBEAT_SECONDS = 1.0


def create_app(policy: AccessPolicy) -> FastAPI:
    app = FastAPI(title="Cover_Maker engine", version=__version__, docs_url=None, redoc_url=None)

    @app.get("/health")
    async def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok", "version": __version__}

    @app.websocket("/events")
    async def events(websocket: WebSocket) -> None:  # pyright: ignore[reportUnusedFunction]
        await websocket.accept()
        try:
            hello = json.loads(await asyncio.wait_for(websocket.receive_text(), timeout=5))
        except (TimeoutError, json.JSONDecodeError, WebSocketDisconnect):
            await websocket.close(code=4401)
            return
        if not (isinstance(hello, dict) and policy.token_ok(hello.get("token"))):  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
            await websocket.close(code=4401)
            return
        seq = 0
        try:
            while True:
                seq += 1
                await websocket.send_json({"seq": seq, "type": "heartbeat"})
                await asyncio.sleep(HEARTBEAT_SECONDS)
        except (WebSocketDisconnect, RuntimeError):
            return

    app.add_middleware(AccessMiddleware, policy=policy)
    return app
