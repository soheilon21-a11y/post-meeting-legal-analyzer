from __future__ import annotations

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions.domain import UnauthorizedError
from app.core.security.tokens import TokenPayload, TokenService

_bearer_scheme = HTTPBearer(auto_error=False)


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
