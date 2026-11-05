"""Protection for the local API: per-session token, exact Host and Origin allowlist.

The engine only listens on 127.0.0.1, but any web page the user visits could try
to reach it (DNS rebinding, cross-site requests). Every request must therefore
carry the session token, address the exact host:port the engine bound to, and
come from an allowed origin when it carries an Origin header.
"""

from __future__ import annotations

import hmac
from collections.abc import Iterable
from dataclasses import dataclass, field

from starlette.types import ASGIApp, Receive, Scope, Send

# Origins used by the Tauri WebView in production and by the Vite dev server.
DEFAULT_ALLOWED_ORIGINS = frozenset(
    {
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
        "http://localhost:1420",
    }
)


@dataclass(frozen=True)
class AccessPolicy:
    token: str
    host: str
    allowed_origins: frozenset[str] = field(default=DEFAULT_ALLOWED_ORIGINS)
    # Tokens of local clients such as DAW plugins (ADR-008); empty when disabled.
    client_tokens: frozenset[str] = field(default=frozenset())

    def token_ok(self, presented: str | None) -> bool:
        if presented is None:
            return False
        valid = [self.token, *self.client_tokens]
        # Compare against every token so timing does not reveal which matched.
        return any([hmac.compare_digest(presented, t) for t in valid])

    def host_ok(self, host: str | None) -> bool:
        return host == self.host

    def origin_ok(self, origin: str | None) -> bool:
        # Requests without Origin come from the shell itself or local tools.
        return origin is None or origin in self.allowed_origins


def _header(headers: Iterable[tuple[bytes, bytes]], name: bytes) -> str | None:
    for key, value in headers:
        if key.lower() == name:
            return value.decode("latin-1")
    return None


class AccessMiddleware:
    """ASGI middleware enforcing :class:`AccessPolicy` on HTTP and WebSocket.

    WebSocket connections are only checked for Host and Origin here, because
    browsers cannot set an Authorization header on them; they authenticate with
    their first message instead.
    """

    def __init__(self, app: ASGIApp, policy: AccessPolicy) -> None:
        self.app = app
        self.policy = policy

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = scope.get("headers", [])
        host_ok = self.policy.host_ok(_header(headers, b"host"))
        origin = _header(headers, b"origin")
        origin_ok = self.policy.origin_ok(origin)

        if scope["type"] == "http":
            if scope["method"] == "OPTIONS" and host_ok and origin_ok:
                await self._preflight(send, origin)
                return
            auth = _header(headers, b"authorization") or ""
            token = auth.removeprefix("Bearer ") if auth.startswith("Bearer ") else None
            if not (host_ok and origin_ok and self.policy.token_ok(token)):
                await self._reject(send, 401 if host_ok and origin_ok else 403)
                return

            async def send_with_cors(message: dict[str, object]) -> None:
                if message["type"] == "http.response.start" and origin:
                    extra = [
                        (b"access-control-allow-origin", origin.encode()),
                        (b"vary", b"Origin"),
                    ]
                    message["headers"] = [*message.get("headers", []), *extra]  # type: ignore[misc]
                await send(message)

            await self.app(scope, receive, send_with_cors)  # type: ignore[arg-type]
            return

        if not (host_ok and origin_ok):
            await send({"type": "websocket.close", "code": 4403})
            return
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send: Send, status: int) -> None:
        body = b'{"detail":"forbidden"}'
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    @staticmethod
    async def _preflight(send: Send, origin: str | None) -> None:
        headers = [
            (b"access-control-allow-methods", b"GET, POST, PUT, PATCH, DELETE"),
            (b"access-control-allow-headers", b"authorization, content-type"),
            (b"access-control-max-age", b"600"),
            (b"content-length", b"0"),
        ]
        if origin:
            headers.append((b"access-control-allow-origin", origin.encode()))
        await send({"type": "http.response.start", "status": 204, "headers": headers})
        await send({"type": "http.response.body", "body": b""})
