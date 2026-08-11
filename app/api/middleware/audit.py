from __future__ import annotations

from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.logging import get_logger

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
