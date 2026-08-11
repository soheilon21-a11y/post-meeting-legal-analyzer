from dataclasses import dataclass

from app.domain.shared.domain_event import DomainEvent
from app.domain.shared.identifiers import MeetingId


@dataclass(frozen=True, slots=True)
class MeetingReady(DomainEvent):
    aggregate_id: MeetingId
