from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.exceptions.lifecycle import InvalidStateTransition
from app.domain.services.result import ServiceResult
from app.domain.specifications.legal import MeetingIsReady

if TYPE_CHECKING:
    from app.domain.analysis.entities import LegalAnalysis
    from app.domain.meeting.entities import Meeting


class AnalysisDomainService:
    """Coordinates analysis readiness across a meeting and an analysis aggregate."""

    def prepare_for_review(
        self,
        meeting: Meeting,
        analysis: LegalAnalysis,
        summary: str,
    ) -> ServiceResult:
        if not MeetingIsReady().is_satisfied_by(meeting):
            raise InvalidStateTransition("Meeting", meeting.status, "ready")
        analysis.set_summary(summary)
        analysis.mark_ready_for_review()
        return ServiceResult(aggregate_id=analysis.id, status=analysis.status.value)
