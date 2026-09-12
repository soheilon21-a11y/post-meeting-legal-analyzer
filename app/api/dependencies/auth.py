from __future__ import annotations

from fastapi import Depends
from fastapi import Header
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer

from app.core.exceptions.domain import UnauthorizedError
from app.core.security.tokens import TokenPayload
from app.core.security.tokens import TokenService

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


async def get_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    authorization: str | None = Header(default=None),
) -> TokenPayload:
    token = _extract_token(credentials, authorization)
    if token is None:
        raise UnauthorizedError(detail="No authentication token provided")

    token_service = TokenService()
    return token_service.decode_token(token)


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
