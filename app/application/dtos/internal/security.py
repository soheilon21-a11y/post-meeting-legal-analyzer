from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.shared.identifiers import OrganizationId
    from app.domain.shared.identifiers import UserId


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Authenticated actor context supplied by an outer boundary."""

    user_id: UserId
    organization_id: OrganizationId | None = None
    is_platform_admin: bool = False
