"""HTTP middleware — Basic Auth for admin/API routes.

Uses pure ASGI middleware (not BaseHTTPMiddleware) to avoid
known issues with response streaming in Starlette.
"""

from __future__ import annotations

import base64
import secrets
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

# Paths that never require authentication
_PUBLIC_PREFIXES = ("/webhook/", "/admin/statics/")
_PUBLIC_EXACT = ("/api/health",)


class BasicAuthMiddleware:
    """Require HTTP Basic Auth on all routes except public ones."""

    def __init__(self, app: ASGIApp, username: str, password: str) -> None:
        self.app = app
        self._username = username
        self._password = password

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]

        # Allow public paths through without auth
        if path in _PUBLIC_EXACT or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            await self.app(scope, receive, send)
            return

        # Check Authorization header
        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode("utf-8", errors="ignore")

        if auth.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8")
                user, _, pwd = decoded.partition(":")
                if secrets.compare_digest(user, self._username) and secrets.compare_digest(
                    pwd, self._password
                ):
                    await self.app(scope, receive, send)
                    return
            except Exception:
                pass

        response = Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Gmail Assistant"'},
        )
        await response(scope, receive, send)
