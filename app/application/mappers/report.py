from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

from app.application.dtos.responses.report_responses import ReportResponse
from app.application.dtos.responses.report_responses import ReportSectionResponse

if TYPE_CHECKING:
    from app.domain.reporting.entities import LegalReport


class ReportMapper(Protocol):
    def to_response(self, report: LegalReport) -> ReportResponse: ...


class DefaultReportMapper:
    def to_response(self, report: LegalReport) -> ReportResponse:
        return ReportResponse(
            id=report.id,
            title=report.title.value,
            status=report.status.value,
            sections=tuple(
                ReportSectionResponse(
                    id=section.id,
                    heading=section.heading,
                    content=section.content,
                    sequence_number=section.sequence_number,
                )
                for section in report.sections
            ),
            exported_formats=frozenset(item.value for item in report.exported_formats),
        )
