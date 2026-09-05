from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer

from app.api.dependencies.db import get_db
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

    Returns None when no authentication token is present, allowing the
    analysis service to skip audit event dispatch gracefully.
    """
    if credentials is None:
        return None

    try:
        token_service = TokenService()
        payload = token_service.decode_token(credentials.credentials)
    except Exception:
        return None

    if not payload.org_id:
        return None

    organization_id = UUID(payload.org_id)
    actor_id = UUID(payload.sub) if payload.sub else None

    return AuditEventDispatcher(
        session=session,
        organization_id=organization_id,
        actor_id=actor_id,
    )
