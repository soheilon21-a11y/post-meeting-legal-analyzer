from dataclasses import dataclass

from app.domain.shared.domain_event import DomainEvent
from app.domain.shared.identifiers import RedlineJobId


@dataclass(frozen=True, slots=True)
class RedlineReadyForReview(DomainEvent):
    aggregate_id: RedlineJobId


@dataclass(frozen=True, slots=True)
class RedlineExported(DomainEvent):
    aggregate_id: RedlineJobId
