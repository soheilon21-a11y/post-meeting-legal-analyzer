from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

from app.application.dtos.base import PageRequest
from app.application.queries.base import Query

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext
    from app.domain.shared.identifiers import MatterId
    from app.domain.shared.identifiers import OrganizationId


@dataclass(frozen=True, slots=True, kw_only=True)
class GetMatterQuery(Query):
    matter_id: MatterId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ListOrganizationMattersQuery(Query):
    organization_id: OrganizationId
    actor: ActorContext
    page: PageRequest = field(default_factory=PageRequest)
