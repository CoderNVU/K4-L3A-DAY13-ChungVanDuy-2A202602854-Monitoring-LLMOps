from __future__ import annotations

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        clear_contextvars()

        req_id = request.headers.get("x-request-id")
        if req_id and req_id.strip():
            correlation_id = req_id.strip()
        else:
            correlation_id = f"req-{uuid.uuid4().hex[:8]}"

        bind_contextvars(correlation_id=correlation_id)
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)

        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = str(duration_ms)

        return response
