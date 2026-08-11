from dataclasses import dataclass

from app.domain.shared.domain_event import DomainEvent
from app.domain.shared.identifiers import MatterId


@dataclass(frozen=True, slots=True)
class LegalHoldApplied(DomainEvent):
    aggregate_id: MatterId


@dataclass(frozen=True, slots=True)
class MatterClosed(DomainEvent):
    aggregate_id: MatterId
