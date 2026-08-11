from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import Protocol

from app.application.dtos.responses.redline_responses import RedlineChangeResponse
from app.application.dtos.responses.redline_responses import RedlineCitationResponse
from app.application.dtos.responses.redline_responses import RedlineResponse

if TYPE_CHECKING:
    from app.domain.redlining.entities import RedlineJob


class RedlineMapper(Protocol):
    def to_response(self, job: RedlineJob) -> RedlineResponse: ...


class DefaultRedlineMapper:
    def to_response(self, job: RedlineJob) -> RedlineResponse:
        return RedlineResponse(
            id=job.id,
            status=job.status.value,
            changes=tuple(self._change(change) for change in job.changes),
        )

    @staticmethod
    def _change(change: Any) -> RedlineChangeResponse:
        citations = change.citations
        pairs = tuple(zip(citations[::2], citations[1::2], strict=False))
        return RedlineChangeResponse(
            id=change.id,
            clause_path=change.clause_path.value,
            change_type=change.change_type.value,
            original_text=change.original_text,
            proposed_text=change.proposed_text.value,
            rationale=change.rationale.value,
            risk_level=change.risk_level,
            confidence=change.confidence.value,
            review_status=change.review_status.value,
            citations=tuple(
                RedlineCitationResponse(
                    source_id=location.source_id,
                    quote=quote.value,
                    page_number=location.page_number,
                    start_offset=location.start_offset,
                    end_offset=location.end_offset,
                )
                for quote, location in pairs
            ),
        )
