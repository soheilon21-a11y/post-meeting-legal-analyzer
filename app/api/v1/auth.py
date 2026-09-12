from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID
from uuid import uuid4

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies.db import get_db
from app.core.exceptions.domain import ConflictError
from app.core.exceptions.domain import UnauthorizedError
from app.core.security.hashing import hash_password
from app.core.security.hashing import verify_password
from app.core.security.tokens import InvalidTokenError
from app.core.security.tokens import TokenService
from app.db.models.matter import Matter
from app.db.models.matter import MatterClassification
from app.db.models.matter import MatterMember
from app.db.models.matter import MatterMemberRole
from app.db.models.matter import MatterStatus
from app.db.models.organization import Organization
from app.db.models.user import User
from app.domain.events.auth_events import AuthLoginFailed
from app.domain.events.auth_events import AuthLoginSuccess
from app.domain.events.auth_events import AuthRegistered
from app.domain.shared.identifiers import UserId
from app.infrastructure.persistence.audit_event_dispatcher import AuditEventDispatcher

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["Auth"])

_INVALID_CREDENTIALS_DETAIL = "Invalid email or password"


# ─── API Schemas ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    display_name: str = Field(min_length=1, max_length=255)
    organization_name: str | None = Field(default=None, min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterResponse(TokenPairResponse):
    user_id: str
    organization_id: str
    email: str
    display_name: str
    matter_id: str
    matter_number: str


class LoginResponse(TokenPairResponse):
    user_id: str
    organization_id: str
    email: str
    display_name: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ─── Shared helpers ─────────────────────────────────────────────────────────

def _token_pair(user_id: str, organization_id: str) -> tuple[str, str]:
    """Mint an access/refresh pair for real UUIDs (30-min / 7-day TTLs).

    Payloads carry only sub, org_id, type and standard claims — never the
    email, password hash or any document content.
    """
    token_service = TokenService()
    return (
        token_service.create_access_token(user_id, organization_id),
        token_service.create_refresh_token(user_id, organization_id),
    )


async def _emit_auth_audit(
    session: AsyncSession,
    event: AuthRegistered | AuthLoginSuccess | AuthLoginFailed,
    *,
    organization_id: UUID,
    actor_id: UUID | None,
) -> None:
    """Persist an auth domain event through the existing audit dispatcher.

    The event row joins the request's own session (same transaction as the
    auth rows) and metadata carries identifiers only — no credentials.
    """
    await AuditEventDispatcher(
        session=session,
        organization_id=organization_id,
        actor_id=actor_id,
    ).dispatch(event)


# ─── Endpoints ─────────────────────────────────────────────────────────────


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user, organization and starter matter",
)
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """Register a new account directly — no terminal, no seed script needed.

    Creates an ``Organization`` (reused when an existing ``organization_name``
    is supplied), a ``User`` with an argon2/bcrypt-hashed password and an
    EDITOR membership on a personal starter matter — mirroring the row shapes
    of scripts/seed_dev_data.py, all through this request's single session.
    Duplicate emails return 409 before any row is created (and a late
    unique-constraint violation still rolls the whole transaction back, so
    no partial state survives).  Emits an ``auth.registered`` audit event and
    returns a usable access/refresh token pair plus the starter matter ids.
    Passwords and hashes are never returned or logged.
    """
    email = request.email.strip()
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalars().first() is not None:
        raise ConflictError(entity="User", field="email", value=email)

    organization: Organization | None = None
    if request.organization_name is not None:
        org_result = await session.execute(
            select(Organization).where(Organization.name == request.organization_name)
        )
        organization = org_result.scalars().first()
    if organization is None:
        organization = Organization(
            id=uuid4(),
            name=request.organization_name or f"{request.display_name}'s workspace",
        )
        session.add(organization)

    user = User(
        id=uuid4(),
        organization_id=organization.id,
        email=email,
        display_name=request.display_name,
        # Explicit (not flush-time default) so the account is active within
        # this same session, not only after a reload.
        is_active=True,
        hashed_password=hash_password(request.password),
    )
    matter = Matter(
        id=uuid4(),
        organization_id=organization.id,
        name=f"{request.display_name}'s starter matter",
        matter_number=f"matter-{user.id.hex[:12]}",
        status=MatterStatus.ACTIVE,
        classification=MatterClassification.GENERAL,
    )
    membership = MatterMember(
        id=uuid4(),
        matter_id=matter.id,
        user_id=user.id,
        role=MatterMemberRole.EDITOR,
    )
    session.add(user)
    session.add(matter)
    session.add(membership)
    # Wire the relationship in memory too (same rows, same session) so the
    # matter's membership check can serve this request without a reload.
    matter.members = [membership]

    try:
        await session.flush()
    except IntegrityError as exc:
        # Lost a registration race on the unique email (or collision on the
        # generated matter_number): the surrounding get_db rollback leaves no
        # partial rows behind.
        raise ConflictError(entity="User", field="email", value=email) from exc

    await _emit_auth_audit(
        session,
        AuthRegistered(aggregate_id=UserId(user.id)),
        organization_id=organization.id,
        actor_id=user.id,
    )

    access_token, refresh_token = _token_pair(str(user.id), str(organization.id))
    return RegisterResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=str(user.id),
        organization_id=str(organization.id),
        email=user.email,
        display_name=user.display_name,
        matter_id=str(matter.id),
        matter_number=str(matter.matter_number),
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Exchange credentials for an access/refresh token pair",
)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Log in with email and password and receive JWTs for Swagger's Authorize.

    Verifies against the stored argon2/bcrypt hash.  Wrong credentials return
    401 with a single generic message (no account enumeration).  Success and
    attributable failures emit ``auth.login_success`` / ``auth.login_failed``
    audit events through the existing dispatcher; the request-id middleware
    chain applies exactly as on every other endpoint.
    """
    email = request.email.strip()
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalars().first()

    credentials_ok = user is not None and verify_password(
        request.password, user.hashed_password
    )
    if user is None or not credentials_ok:
        if user is not None:
            # Attributable to a known organization → auditable.  Unknown
            # emails have no organization scope, and audit_events is
            # organization-scoped by schema (NOT NULL FK), so there is no
            # row to attach the failure to.
            await _emit_auth_audit(
                session,
                AuthLoginFailed(aggregate_id=UserId(user.id)),
                organization_id=user.organization_id,
                actor_id=user.id,
            )
        raise UnauthorizedError(_INVALID_CREDENTIALS_DETAIL)

    if not user.is_active:
        await _emit_auth_audit(
            session,
            AuthLoginFailed(aggregate_id=UserId(user.id)),
            organization_id=user.organization_id,
            actor_id=user.id,
        )
        raise UnauthorizedError("Account is disabled")

    await _emit_auth_audit(
        session,
        AuthLoginSuccess(aggregate_id=UserId(user.id)),
        organization_id=user.organization_id,
        actor_id=user.id,
    )

    access_token, refresh_token = _token_pair(str(user.id), str(user.organization_id))
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=str(user.id),
        organization_id=str(user.organization_id),
        email=user.email,
        display_name=user.display_name,
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Exchange a refresh token for a new access token",
)
async def refresh(
    request: RefreshRequest,
) -> RefreshResponse:
    """Rotate the short-lived access token using a valid refresh token.

    Accepts only tokens minted by ``TokenService.create_refresh_token``
    (``type == "refresh"``); expired, forged or access-type tokens return
    401.  The response contains no user data — only the new access token.
    """
    try:
        payload = TokenService().decode_token(request.refresh_token)
    except InvalidTokenError as exc:
        raise UnauthorizedError("Refresh token is invalid or expired") from exc
    if payload.token_type != "refresh":
        raise UnauthorizedError("A refresh token is required")

    return RefreshResponse(
        access_token=TokenService().create_access_token(payload.sub, payload.org_id),
    )


__all__ = ["router"]
