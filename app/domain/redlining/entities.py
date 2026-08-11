from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.exceptions.invariant import InvariantViolation
from app.domain.exceptions.redlining import UnsafeRedlineOperation
from app.domain.redlining.enums import ChangeType
from app.domain.redlining.enums import RedlineStatus
from app.domain.redlining.enums import ReviewStatus
from app.domain.redlining.rules import ensure_change_can_be_approved
from app.domain.redlining.rules import ensure_job_can_be_exported
from app.domain.shared.aggregate_root import AggregateRoot
from app.domain.shared.entity import Entity
from app.domain.shared.identifiers import EntityId
from app.domain.shared.identifiers import RedlineJobId

if TYPE_CHECKING:
    from app.domain.analysis.value_objects import ConfidenceScore
    from app.domain.analysis.value_objects import EvidenceQuote
    from app.domain.analysis.value_objects import SourceLocation
    from app.domain.redlining.value_objects import ClausePath
    from app.domain.redlining.value_objects import ProposedText
    from app.domain.redlining.value_objects import Rationale


class RedlineChange(Entity[EntityId]):
    def __init__(
        self,
        clause_path: ClausePath,
        change_type: ChangeType,
        original_text: str,
        proposed_text: ProposedText,
        rationale: Rationale,
        confidence: ConfidenceScore,
        citations: tuple[EvidenceQuote | SourceLocation, ...] = (),
        risk_level: str = "medium",
    ) -> None:
        if not original_text.strip():
            raise InvariantViolation("original_text must not be blank", field_name="original_text")
        if original_text.strip() == proposed_text.value:
            raise InvariantViolation("A redline must change the original text")
        super().__init__()
        self._clause_path = clause_path
        self._change_type = change_type
        self._original_text = original_text.strip()
        self._proposed_text = proposed_text
        self._rationale = rationale
        self._confidence = confidence
        self._citations = tuple(citations)
        self._risk_level = risk_level
        self._review_status = ReviewStatus.PENDING

    @property
    def clause_path(self) -> ClausePath:
        return self._clause_path

    @property
    def change_type(self) -> ChangeType:
        return self._change_type

    @property
    def original_text(self) -> str:
        return self._original_text

    @property
    def proposed_text(self) -> ProposedText:
        return self._proposed_text

    @property
    def rationale(self) -> Rationale:
        return self._rationale

    @property
    def confidence(self) -> ConfidenceScore:
        return self._confidence

    @property
    def review_status(self) -> ReviewStatus:
        return self._review_status

    @property
    def risk_level(self) -> str:
        return self._risk_level

    @property
    def citations(self) -> tuple[EvidenceQuote | SourceLocation, ...]:
        return self._citations

    def approve(self) -> None:
        ensure_change_can_be_approved(self._review_status, self._original_text)
        self._review_status = ReviewStatus.APPROVED

    def reject(self) -> None:
        if self._review_status is not ReviewStatus.PENDING:
            raise UnsafeRedlineOperation("reject_change", "change has already been reviewed")
        self._review_status = ReviewStatus.REJECTED


class RedlineJob(AggregateRoot[RedlineJobId]):
    def __init__(self, redline_job_id: RedlineJobId | None = None) -> None:
        super().__init__(redline_job_id)
        self._status = RedlineStatus.DRAFT
        self._changes: list[RedlineChange] = []

    @property
    def status(self) -> RedlineStatus:
        return self._status

    @property
    def changes(self) -> tuple[RedlineChange, ...]:
        return tuple(self._changes)

    def begin_processing(self) -> None:
        if self._status is not RedlineStatus.DRAFT:
            raise UnsafeRedlineOperation("begin_processing", "job is not in draft status")
        self._status = RedlineStatus.PROCESSING

    def add_change(self, change: RedlineChange) -> None:
        if self._status not in (RedlineStatus.DRAFT, RedlineStatus.PROCESSING):
            raise UnsafeRedlineOperation("add_change", "job is no longer mutable")
        self._changes.append(change)

    def mark_ready_for_review(self) -> None:
        if self._status is not RedlineStatus.PROCESSING:
            raise UnsafeRedlineOperation("mark_ready_for_review", "job is not processing")
        self._status = RedlineStatus.READY_FOR_REVIEW

    def mark_reviewed(self) -> None:
        if self._status is not RedlineStatus.READY_FOR_REVIEW:
            raise UnsafeRedlineOperation("mark_reviewed", "job is not ready for review")
        if any(change.review_status is ReviewStatus.PENDING for change in self._changes):
            raise UnsafeRedlineOperation("mark_reviewed", "pending changes remain")
        self._status = RedlineStatus.REVIEWED

    def export(self) -> None:
        ensure_job_can_be_exported(
            self._status,
            sum(change.review_status is ReviewStatus.PENDING for change in self._changes),
        )
        self._status = RedlineStatus.EXPORTED
