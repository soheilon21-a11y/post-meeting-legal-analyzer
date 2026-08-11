from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import Protocol

from app.application.dtos.responses.analysis_responses import AnalysisItemResponse
from app.application.dtos.responses.analysis_responses import AnalysisResponse
from app.application.dtos.responses.analysis_responses import CitationResponse

if TYPE_CHECKING:
    from app.domain.analysis.entities import LegalAnalysis


class AnalysisMapper(Protocol):
    def to_response(self, analysis: LegalAnalysis) -> AnalysisResponse: ...


class DefaultAnalysisMapper:
    def to_response(self, analysis: LegalAnalysis) -> AnalysisResponse:
        return AnalysisResponse(
            id=analysis.id,
            analysis_type=analysis.analysis_type.value,
            status=analysis.status.value,
            summary=analysis.summary,
            items=tuple(self._item_response(item) for item in analysis.items),
        )

    @staticmethod
    def _item_response(item: Any) -> AnalysisItemResponse:
        from app.domain.analysis.entities import ActionItem
        from app.domain.analysis.entities import Obligation
        from app.domain.analysis.entities import Risk

        risk_level = item.level.value if isinstance(item, Risk) else None
        responsible_party = (
            item.responsible_party.value if isinstance(item, Obligation | ActionItem) else None
        )
        due_date = (
            item.deadline.due_date.value
            if isinstance(item, Obligation | ActionItem) and item.deadline
            else None
        )
        return AnalysisItemResponse(
            id=item.id,
            item_type=type(item).__name__.lower(),
            title=item.title,
            description=item.description,
            status=item.status.value,
            confidence=item.confidence.value,
            risk_level=risk_level,
            responsible_party=responsible_party,
            due_date=due_date,
            citations=tuple(
                CitationResponse(
                    id=citation.id,
                    quote=citation.quote.value,
                    source_id=citation.location.source_id,
                    page_number=citation.location.page_number,
                    start_offset=citation.location.start_offset,
                    end_offset=citation.location.end_offset,
                )
                for citation in item.citations
            ),
        )
