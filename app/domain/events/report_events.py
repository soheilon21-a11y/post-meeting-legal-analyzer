from dataclasses import dataclass

from app.domain.shared.domain_event import DomainEvent
from app.domain.shared.identifiers import ReportId


@dataclass(frozen=True, slots=True)
class ReportReady(DomainEvent):
    aggregate_id: ReportId


@dataclass(frozen=True, slots=True)
class ReportExported(DomainEvent):
    aggregate_id: ReportId
