from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.queries.base import Query

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext
    from app.domain.shared.identifiers import DocumentId
    from app.domain.shared.identifiers import MatterId


@dataclass(frozen=True, slots=True, kw_only=True)
class GetDocumentQuery(Query):
    matter_id: MatterId
    document_id: DocumentId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class GetDocumentVersionsQuery(Query):
    matter_id: MatterId
    document_id: DocumentId
    actor: ActorContext
