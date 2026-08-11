from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.redlining.enums import ReviewStatus
from app.domain.services.result import ServiceResult

if TYPE_CHECKING:
    from collections.abc import Mapping

    from app.domain.redlining.entities import RedlineJob
    from app.domain.shared.identifiers import EntityId


class RedlineDomainService:
    """Applies a deterministic human review decision to every redline change."""

    def review_changes(
        self,
        job: RedlineJob,
        decisions: Mapping[EntityId, ReviewStatus],
    ) -> ServiceResult:
        expected_ids = {change.id for change in job.changes}
        if set(decisions) != expected_ids:
            raise ValueError("A review decision is required for every redline change")

        for change in job.changes:
            decision = decisions[change.id]
            if decision is ReviewStatus.APPROVED:
                change.approve()
            elif decision is ReviewStatus.REJECTED:
                change.reject()
            else:
                raise ValueError("Review decisions must be approved or rejected")

        job.mark_reviewed()
        return ServiceResult(aggregate_id=job.id, status=job.status.value)
