from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.analysis.enums import AnalysisStatus
from app.domain.analysis.enums import AnalysisType
from app.domain.analysis.enums import ItemStatus
from app.domain.analysis.enums import RiskLevel
from app.domain.analysis.rules import ensure_analysis_can_be_approved
from app.domain.analysis.rules import ensure_analysis_can_change
from app.domain.analysis.rules import ensure_item_can_complete
from app.domain.analysis.rules import ensure_material_item_has_evidence
from app.domain.exceptions.evidence import MissingEvidence
from app.domain.exceptions.invariant import InvariantViolation
from app.domain.exceptions.lifecycle import InvalidStateTransition
from app.domain.shared.aggregate_root import AggregateRoot
from app.domain.shared.entity import Entity
from app.domain.shared.identifiers import AnalysisId
from app.domain.shared.identifiers import EntityId

if TYPE_CHECKING:
    from app.domain.analysis.value_objects import ConfidenceScore
    from app.domain.analysis.value_objects import Deadline as DeadlineValue
    from app.domain.analysis.value_objects import EvidenceQuote
    from app.domain.analysis.value_objects import ResponsibleParty
    from app.domain.analysis.value_objects import SourceLocation


class Citation(Entity[EntityId]):
    def __init__(self, quote: EvidenceQuote, location: SourceLocation) -> None:
        super().__init__()
        self._quote = quote
        self._location = location

    @property
    def quote(self) -> EvidenceQuote:
        return self._quote

    @property
    def location(self) -> SourceLocation:
        return self._location


class Deadline(Entity[EntityId]):
    def __init__(self, due_date: DeadlineValue, responsible_party: ResponsibleParty) -> None:
        super().__init__()
        self._due_date = due_date
        self._responsible_party = responsible_party
        self._status = ItemStatus.OPEN

    @property
    def due_date(self) -> DeadlineValue:
        return self._due_date

    @property
    def responsible_party(self) -> ResponsibleParty:
        return self._responsible_party

    @property
    def status(self) -> ItemStatus:
        return self._status

    def complete(self) -> None:
        if self._status is ItemStatus.DISMISSED:
            raise ValueError("Dismissed deadlines cannot be completed")
        self._status = ItemStatus.COMPLETED


class _AnalysisItem(Entity[EntityId]):
    def __init__(
        self,
        title: str,
        description: str,
        confidence: ConfidenceScore,
        citations: tuple[Citation, ...],
    ) -> None:
        if not title.strip() or not description.strip():
            raise InvariantViolation("Analysis items require title and description")
        super().__init__()
        self._title = title.strip()
        self._description = description.strip()
        self._confidence = confidence
        self._citations = list(citations)
        self._status = ItemStatus.OPEN

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    @property
    def confidence(self) -> ConfidenceScore:
        return self._confidence

    @property
    def citations(self) -> tuple[Citation, ...]:
        return tuple(self._citations)

    @property
    def status(self) -> ItemStatus:
        return self._status

    def add_citation(self, citation: Citation) -> None:
        self._citations.append(citation)

    def dismiss(self) -> None:
        self._status = ItemStatus.DISMISSED


class Risk(_AnalysisItem):
    def __init__(
        self,
        title: str,
        description: str,
        level: RiskLevel,
        confidence: ConfidenceScore,
        citations: tuple[Citation, ...] = (),
    ) -> None:
        ensure_material_item_has_evidence(level, len(citations))
        super().__init__(title, description, confidence, citations)
        self._level = level

    @property
    def level(self) -> RiskLevel:
        return self._level


class Obligation(_AnalysisItem):
    def __init__(
        self,
        title: str,
        description: str,
        responsible_party: ResponsibleParty,
        deadline: Deadline | None,
        confidence: ConfidenceScore,
        citations: tuple[Citation, ...] = (),
    ) -> None:
        if not citations:
            raise MissingEvidence("obligation", ["source citation"])
        super().__init__(title, description, confidence, citations)
        self._responsible_party = responsible_party
        self._deadline = deadline

    @property
    def responsible_party(self) -> ResponsibleParty:
        return self._responsible_party

    @property
    def deadline(self) -> Deadline | None:
        return self._deadline

    def assign_deadline(self, deadline: Deadline) -> None:
        self._deadline = deadline


class ActionItem(_AnalysisItem):
    def __init__(
        self,
        title: str,
        description: str,
        responsible_party: ResponsibleParty,
        confidence: ConfidenceScore,
        deadline: Deadline | None = None,
        citations: tuple[Citation, ...] = (),
    ) -> None:
        super().__init__(title, description, confidence, citations)
        self._responsible_party = responsible_party
        self._deadline = deadline

    @property
    def responsible_party(self) -> ResponsibleParty:
        return self._responsible_party

    @property
    def deadline(self) -> Deadline | None:
        return self._deadline

    def assign_deadline(self, deadline: Deadline) -> None:
        self._deadline = deadline

    def complete(self) -> None:
        ensure_item_can_complete(self._status, self._deadline is not None)
        self._status = ItemStatus.COMPLETED


class LegalAnalysis(AggregateRoot[AnalysisId]):
    def __init__(
        self,
        analysis_type: AnalysisType,
        analysis_id: AnalysisId | None = None,
    ) -> None:
        super().__init__(analysis_id)
        self._analysis_type = analysis_type
        self._status = AnalysisStatus.DRAFT
        self._items: list[_AnalysisItem] = []
        self._summary: str | None = None

    @property
    def analysis_type(self) -> AnalysisType:
        return self._analysis_type

    @property
    def status(self) -> AnalysisStatus:
        return self._status

    @property
    def summary(self) -> str | None:
        return self._summary

    @property
    def items(self) -> tuple[_AnalysisItem, ...]:
        return tuple(self._items)

    def begin_processing(self) -> None:
        if self._status is not AnalysisStatus.DRAFT:
            raise InvalidStateTransition("LegalAnalysis", self._status, AnalysisStatus.PROCESSING)
        self._status = AnalysisStatus.PROCESSING

    def set_summary(self, summary: str) -> None:
        ensure_analysis_can_change(self._status)
        if not summary.strip():
            raise InvariantViolation("analysis summary must not be blank", field_name="summary")
        self._summary = summary.strip()

    def add_item(self, item: _AnalysisItem) -> None:
        ensure_analysis_can_change(self._status)
        self._items.append(item)

    def mark_ready_for_review(self) -> None:
        if self._status is not AnalysisStatus.PROCESSING:
            raise InvalidStateTransition(
                "LegalAnalysis", self._status, AnalysisStatus.READY_FOR_REVIEW
            )
        if not self._summary:
            raise InvariantViolation("An analysis requires a summary before review")
        self._status = AnalysisStatus.READY_FOR_REVIEW

    def approve(self) -> None:
        ensure_analysis_can_be_approved(self._status, len(self._items))
        self._status = AnalysisStatus.APPROVED

    def reject(self) -> None:
        if self._status is not AnalysisStatus.READY_FOR_REVIEW:
            raise InvalidStateTransition("LegalAnalysis", self._status, AnalysisStatus.REJECTED)
        self._status = AnalysisStatus.REJECTED
