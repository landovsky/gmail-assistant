"""HTTP middleware — Basic Auth for admin/API routes."""

from __future__ import annotations

import base64
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Paths that never require authentication
_PUBLIC_PREFIXES = ("/webhook/", "/admin/statics/")
_PUBLIC_EXACT = ("/api/health",)


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Require HTTP Basic Auth on all routes except public ones."""

    def __init__(self, app, username: str, password: str) -> None:
        super().__init__(app)
        self._username = username
        self._password = password

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow public paths through without auth
        if path in _PUBLIC_EXACT or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        # Check Authorization header
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8")
                user, _, pwd = decoded.partition(":")
                user_ok = secrets.compare_digest(user, self._username)
                pwd_ok = secrets.compare_digest(pwd, self._password)
                if user_ok and pwd_ok:
                    return await call_next(request)
            except Exception:
                pass

        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Gmail Assistant"'},
        )
