from dataclasses import dataclass

from app.domain.shared.domain_event import DomainEvent
from app.domain.shared.identifiers import AnalysisId


@dataclass(frozen=True, slots=True)
class AnalysisReadyForReview(DomainEvent):
    aggregate_id: AnalysisId


@dataclass(frozen=True, slots=True)
class AnalysisApproved(DomainEvent):
    aggregate_id: AnalysisId
