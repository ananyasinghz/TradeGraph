"""Simple in-memory per-IP rate limiter for sensitive routes."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.app.core.config import Settings

_SENSITIVE_SUFFIXES = (
    "/ask",
    "/uploads",
    "/ingest/run",
    "/ingest/promote-cbic",
    "/eval/run",
    "/eval/hs-classify",
    "/auth/whoami",
    "/auth/audit",
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, settings: Settings) -> None:
        super().__init__(app)
        self._limit = settings.rate_limit_per_minute
        self._window = 60.0
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _is_sensitive(self, path: str) -> bool:
        return any(path.endswith(s) or f"{s}/" in path for s in _SENSITIVE_SUFFIXES)

    async def dispatch(self, request: Request, call_next: object) -> Response:
        if request.method == "OPTIONS" or not self._is_sensitive(request.url.path):
            return await call_next(request)  # type: ignore[misc]
        client = request.client.host if request.client else "unknown"
        key = f"{client}:{request.url.path}"
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self._window:
                q.popleft()
            if len(q) >= self._limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": "Too many requests — slow down and retry",
                        }
                    },
                )
            q.append(now)
        return await call_next(request)  # type: ignore[misc]
