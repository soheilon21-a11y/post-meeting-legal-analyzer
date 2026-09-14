from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import Cookie
from fastapi import Depends
from fastapi import Header
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer

from app.api.dependencies.db import get_db
from app.core.exceptions.domain import ForbiddenError
from app.core.exceptions.domain import UnauthorizedError
from app.core.security.tokens import SESSION_COOKIE_NAME
from app.core.security.tokens import TokenPayload
from app.core.security.tokens import TokenService
from app.db.models.session import Session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Named scheme so FastAPI publishes it once under OpenAPI ``securitySchemes``
# with a stable key: Swagger UI's Authorize button then sends
# ``Authorization: Bearer <token>`` on every protected endpoint.  ``auto_error``
# stays off and the raw ``authorization`` header remains as a fallback for
# clients that set the header manually.
bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="HTTPBearer",
    description=(
        "Paste the JWT from POST /api/v1/auth/login (or register/refresh). "
        "Swagger prepends 'Bearer ' automatically."
    ),
)

_bearer_scheme = bearer_scheme

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


async def get_token_payload(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    authorization: str | None = Header(default=None),
    local_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    session: AsyncSession = Depends(get_db),
) -> TokenPayload:
    return await _authenticate(
        request, credentials, authorization, local_session, session, required=True
    )  # type: ignore[return-value]


async def get_optional_token_payload(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    authorization: str | None = Header(default=None),
    local_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    session: AsyncSession = Depends(get_db),
) -> TokenPayload | None:
    """Same resolution as ``get_token_payload`` but with no credential at all.

    Returns ``None`` only when neither a Bearer token nor a session cookie
    was sent.  A token/cookie that is present but invalid, expired or backed
    by a revoked session still yields 401 — the optional dependency relaxes
    *anonymity*, never hardening.
    """
    return await _authenticate(
        request, credentials, authorization, local_session, session, required=False
    )


async def _authenticate(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    authorization: str | None,
    local_session: str | None,
    session: AsyncSession,
    *,
    required: bool,
) -> TokenPayload | None:
    token = _extract_token(credentials, authorization)
    via_cookie = False
    if token is None and local_session:
        token = local_session
        via_cookie = True
    if token is None:
        if required:
            raise UnauthorizedError(detail="No authentication token provided")
        return None

    # decode_token raises InvalidTokenError (→ 401 via the registered
    # handler) for garbage, forged or expired tokens — present-but-bad is
    # never treated as anonymous.
    payload = TokenService().decode_token(token)

    if payload.token_type == "session":
        # Cookie credential: revocation is only possible because every use
        # re-checks the server-side session row (DB; Redis would work the
        # same way — no new dependency).
        await _verify_session_row(session, payload)
    if via_cookie and request.method in _MUTATING_METHODS and not _same_origin_proof(request):
        raise ForbiddenError(
            "Cookie-authenticated mutations require the X-Requested-With: "
            "XMLHttpRequest header or a same-origin Origin/Referer "
            "(Swagger UI at /docs and any local front end qualify)"
        )
    return payload


def _same_origin_proof(request: Request) -> bool:
    """Evidence that a cookie-authenticated mutation came from this app's
    own origin.

    The session cookie is ``HttpOnly; SameSite=Strict``, so a cross-site
    page cannot attach it at all — this check is defence-in-depth for the
    (future) case where SameSite is relaxed.  Accepted proofs: the legacy
    ``X-Requested-With`` marker that same-site XHR/fetch wrappers set, or a
    browser-supplied ``Origin``/``Referer`` whose host:port matches the
    request (Swagger UI's fetches from /docs send it automatically).
    Non-browser callers send neither header and must fall back to a Bearer
    token or the explicit marker.
    """
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return True
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return False
    netloc = urlsplit(origin).netloc
    return bool(netloc) and netloc == request.url.netloc


async def _verify_session_row(session: AsyncSession, payload: TokenPayload) -> None:
    try:
        session_id = UUID(str(payload.jti))
    except (ValueError, TypeError):
        raise UnauthorizedError("Session revoked") from None
    row = await session.get(Session, session_id)
    if row is None or row.revoked:
        raise UnauthorizedError("Session revoked")
    if row.expires_at is not None:
        expires = (
            row.expires_at
            if row.expires_at.tzinfo is not None
            else row.expires_at.replace(tzinfo=UTC)
        )
        if expires < datetime.now(UTC):
            raise UnauthorizedError("Session revoked")


async def get_current_user_id(
    payload: TokenPayload = Depends(get_token_payload),
) -> str:
    return payload.sub


async def get_current_org_id(
    payload: TokenPayload = Depends(get_token_payload),
) -> str | None:
    return payload.org_id


def _extract_token(
    credentials: HTTPAuthorizationCredentials | None,
    header_value: str | None,
) -> str | None:
    if credentials:
        return credentials.credentials
    if header_value and header_value.startswith("Bearer "):
        return header_value[7:]
    return None
