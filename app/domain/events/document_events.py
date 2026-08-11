from dataclasses import dataclass

from app.domain.shared.domain_event import DomainEvent
from app.domain.shared.identifiers import DocumentId


@dataclass(frozen=True, slots=True)
class DocumentVersionCompleted(DomainEvent):
    aggregate_id: DocumentId
