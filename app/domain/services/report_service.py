from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.services.result import ServiceResult
from app.domain.specifications.legal import AnalysisIsApproved

if TYPE_CHECKING:
    from app.domain.analysis.entities import LegalAnalysis
    from app.domain.reporting.entities import LegalReport


class ReportDomainService:
    """Coordinates report generation eligibility from an approved analysis."""

    def begin_from_analysis(
        self,
        analysis: LegalAnalysis,
        report: LegalReport,
    ) -> ServiceResult:
        if not AnalysisIsApproved().is_satisfied_by(analysis):
            raise ValueError("Reports can only be generated from approved analyses")
        report.begin_generation()
        return ServiceResult(aggregate_id=report.id, status=report.status.value)
