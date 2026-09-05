from __future__ import annotations

import time
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint

from app.core.logging import get_logger

if TYPE_CHECKING:
    from fastapi import Request
    from starlette.responses import Response

logger = get_logger(__name__)


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        logger.debug(
            "request_timing",
            method=request.method,
            path=request.url.path,
            duration_ms=round(duration_ms, 2),
            status_code=response.status_code,
        )

        return response
