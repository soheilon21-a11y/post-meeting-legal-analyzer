from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from app.application.exceptions.not_found import ResourceNotFound
from app.domain.exceptions.redlining import UnsafeRedlineOperation
from app.domain.redlining.enums import ReviewStatus

if TYPE_CHECKING:
    from app.application.dtos.internal.redline_generation import RedlineGenerationInput
    from app.application.services.redline_service import RedlineApplicationService
    from app.domain.redlining.entities import RedlineChange
    from app.domain.redlining.entities import RedlineJob


@dataclass(frozen=True, slots=True)
class RedlineReviewProgress:
    """Snapshot of how many proposed changes still require a decision."""

    total: int
    pending: int
    approved: int
    rejected: int

    @property
    def is_complete(self) -> bool:
        return self.pending == 0 and self.total > 0


class RedlineReviewWorkflow:
    """Coordinates the multi-step redline review lifecycle.

    The workflow composes the generation service with the review state
    machine so callers can drive a redline from draft to export without
    depending on persistence or transport details.
    """

    def __init__(self, redline_service: RedlineApplicationService) -> None:
        self._service = redline_service

    async def prepare(self, job: RedlineJob, request: RedlineGenerationInput) -> None:
        """Generate proposed changes and leave the job ready for review."""
        await self._service.generate(job, request)

    def decide(self, job: RedlineJob, change_id: str, approve: bool) -> None:
        """Record a reviewer decision for a single proposed change."""
        change = self._find_change(job, change_id)
        if approve:
            change.approve()
        else:
            change.reject()

    def finalize(self, job: RedlineJob) -> None:
        """Complete the review once every proposed change has been decided."""
        progress = self.progress(job)
        if progress.total == 0:
            raise UnsafeRedlineOperation(
                "mark_reviewed", "a redline requires at least one proposed change"
            )
        job.mark_reviewed()

    def publish(self, job: RedlineJob) -> None:
        """Export the reviewed redline for downstream consumption."""
        job.export()

    @staticmethod
    def progress(job: RedlineJob) -> RedlineReviewProgress:
        pending = sum(change.review_status is ReviewStatus.PENDING for change in job.changes)
        approved = sum(change.review_status is ReviewStatus.APPROVED for change in job.changes)
        rejected = sum(change.review_status is ReviewStatus.REJECTED for change in job.changes)
        return RedlineReviewProgress(
            total=len(job.changes),
            pending=pending,
            approved=approved,
            rejected=rejected,
        )

    @staticmethod
    def _find_change(job: RedlineJob, change_id: str) -> RedlineChange:
        try:
            target_id = UUID(change_id)
        except ValueError as exc:
            raise ResourceNotFound("RedlineChange", change_id) from exc
        change = next((item for item in job.changes if item.id == target_id), None)
        if change is None:
            raise ResourceNotFound("RedlineChange", change_id)
        return change
