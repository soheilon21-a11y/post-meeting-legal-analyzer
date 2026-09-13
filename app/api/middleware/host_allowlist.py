from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint

from app.core.config import get_settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from fastapi import Request
    from starlette.responses import Response

logger = get_logger(__name__)


class HostAllowlistMiddleware(BaseHTTPMiddleware):
    """DNS-rebinding protection: refuse requests addressed to other hosts.

    A hostile page that manages to re-point its own domain at 127.0.0.1 can
    reach a local-only service; the browser still sends the attacker's Host
    header, so rejecting anything outside the loopback allowlist
    ({127.0.0.1:<port>, localhost:<port>}) closes that hole.  The allowlist
    lives in settings.app.allowed_hosts; the test-suite hosts (test,
    testserver) are in the default purely so the local httpx/TestClient
    fakes keep working, and any real deployment should set APP_ALLOWED_HOSTS
    explicitly.
    """

    def __init__(self, app: object, allowed_hosts: str | None = None) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        raw = (
            allowed_hosts
            if allowed_hosts is not None
            else get_settings().app.allowed_hosts
        )
        self._allowed = {host.strip().lower() for host in raw.split(",") if host.strip()}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        host = (request.headers.get("host") or "").strip().lower()
        # "localhost:8000" → "localhost" (any port is acceptable locally).
        hostname = host.rsplit(":", 1)[0] if ":" in host and "]" not in host else host
        if hostname not in self._allowed:
            logger.warning("host_not_allowed", host=host, path=request.url.path)
            return JSONResponse(
                status_code=HTTPStatus.FORBIDDEN,
                content={
                    "type": "https://tools.ietf.org/html/rfc7231#section-6",
                    "title": "Forbidden",
                    "status": HTTPStatus.FORBIDDEN,
                    "detail": f"Host '{host}' is not in the allowlist",
                },
            )
        return await call_next(request)
