from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint

from app.core.logging import get_logger

if TYPE_CHECKING:
    from fastapi import Request
    from starlette.responses import Response

logger = get_logger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        audit_id = uuid4().hex
        request.state.audit_id = audit_id

        logger.debug(
            "audit_request",
            audit_id=audit_id,
            method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else None,
        )

        response = await call_next(request)

        logger.debug(
            "audit_response",
            audit_id=audit_id,
            status_code=response.status_code,
        )

        return response
