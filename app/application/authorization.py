from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from app.application.exceptions.authorization import AuthorizationError
from app.domain.matter.enums import MatterMemberRole

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext
    from app.domain.matter.entities import Matter
    from app.domain.shared.identifiers import OrganizationId


class MatterAction(StrEnum):
    READ = "read"
    EDIT = "edit"
    MANAGE_MEMBERS = "manage_members"
    MANAGE_HOLD = "manage_legal_hold"
    CLOSE = "close"


class ApplicationAuthorizationService:
    """Applies application-level actor checks before domain mutation."""

    def require_platform_admin(self, actor: ActorContext, action: str) -> None:
        if not actor.is_platform_admin:
            raise AuthorizationError(action, "organization")

    def require_organization_access(
        self,
        actor: ActorContext,
        organization_id: OrganizationId,
        action: str,
    ) -> None:
        if actor.is_platform_admin:
            return
        if actor.organization_id != organization_id:
            raise AuthorizationError(action, f"organization:{organization_id}")

    def require_matter_access(
        self,
        actor: ActorContext,
        matter: Matter,
        action: MatterAction,
    ) -> None:
        if actor.is_platform_admin:
            return
        member = next((item for item in matter.members if item.user_id == actor.user_id), None)
        if member is None:
            raise AuthorizationError(action.value, f"matter:{matter.id}")
        if not self._role_allows(member.role, action):
            raise AuthorizationError(action.value, f"matter:{matter.id}")

    @staticmethod
    def _role_allows(role: MatterMemberRole, action: MatterAction) -> bool:
        if role is MatterMemberRole.OWNER:
            return True
        if role is MatterMemberRole.EDITOR:
            return action in {MatterAction.READ, MatterAction.EDIT}
        return action is MatterAction.READ
