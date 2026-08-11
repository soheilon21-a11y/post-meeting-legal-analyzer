from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.queries.base import Query

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext
    from app.domain.shared.identifiers import OrganizationId


@dataclass(frozen=True, slots=True, kw_only=True)
class GetOrganizationQuery(Query):
    organization_id: OrganizationId
    actor: ActorContext
