"""HTTP request logging middleware."""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("jurisguard.http")


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        path = request.url.path
        method = request.method
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-Id"] = req_id
            return response
        finally:
            ms = (time.perf_counter() - start) * 1000
            level = logging.WARNING if status >= 400 else logging.INFO
            logger.log(level, "%s %s %s %.1fms req=%s", method, path, status, ms, req_id)
