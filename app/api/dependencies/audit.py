from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer

from app.api.dependencies.db import get_db
from app.core.exceptions.domain import UnauthorizedError
from app.core.security.tokens import TokenService
from app.infrastructure.persistence.audit_event_dispatcher import AuditEventDispatcher

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_audit_dispatcher(
    session: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuditEventDispatcher | None:
    """Build an AuditEventDispatcher if authentication context is available.

    Returns None when no token is present or the token cannot be decoded,
    allowing the analysis service to skip audit event dispatch gracefully.
    A token that does decode but carries a missing or non-UUID ``org_id``
    (or a non-UUID ``sub``) is a malformed claim, not an anonymous request:
    raise UnauthorizedError (401) with a clear message instead of letting
    ``UUID()`` bubble up as a 500.
    """
    if credentials is None:
        return None

    try:
        token_service = TokenService()
        payload = token_service.decode_token(credentials.credentials)
    except Exception:
        return None

    if not payload.org_id:
        raise UnauthorizedError("Invalid organization claim in token")

    try:
        organization_id = UUID(payload.org_id)
    except ValueError:
        raise UnauthorizedError("Invalid organization claim in token") from None

    actor_id: UUID | None = None
    if payload.sub:
        try:
            actor_id = UUID(payload.sub)
        except ValueError:
            raise UnauthorizedError("Invalid subject claim in token") from None

    return AuditEventDispatcher(
        session=session,
        organization_id=organization_id,
        actor_id=actor_id,
    )
