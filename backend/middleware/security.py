"""
Security middleware:
- Rate limiting per IP
- Security headers (CSP, HSTS, XFO)
- Request ID injection
- Request logging
"""
import time
import uuid
import logging
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from backend.core.config import settings

logger = logging.getLogger(__name__)

# In-memory rate limiter (use Redis in production for multi-process)
_rate_store: dict[str, list[float]] = defaultdict(list)


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.time()
        request_id = str(uuid.uuid4())[:8]

        # Inject request ID
        request.state.request_id = request_id

        # Rate limiting (skip static files)
        if request.url.path.startswith("/api/"):
            ip = request.client.host if request.client else "unknown"
            if not self._rate_ok(ip, settings.RATE_LIMIT_PER_MINUTE, 60):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"},
                    headers={"Retry-After": "60"},
                )

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"[{request_id}] Unhandled error: {e}", exc_info=True)
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})

        # Security headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        if settings.ENV == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # CSP - allows fonts, charts, FA icons
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

        # Log
        elapsed = (time.time() - start) * 1000
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"→ {response.status_code} ({elapsed:.1f}ms)"
        )

        return response

    def _rate_ok(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        calls = _rate_store[key]
        calls[:] = [t for t in calls if now - t < window]
        if len(calls) >= limit:
            return False
        calls.append(now)
        return True
