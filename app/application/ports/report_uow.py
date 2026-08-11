from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

from app.application.ports.unit_of_work import UnitOfWork

if TYPE_CHECKING:
    from app.application.ports.analysis_uow import AnalysisReadRepository
    from app.domain.ports.repositories import MatterRepository
    from app.domain.reporting.entities import LegalReport
    from app.domain.shared.identifiers import MatterId
    from app.domain.shared.identifiers import ReportId


class ReportRepository(Protocol):
    async def get_for_matter(
        self, matter_id: MatterId, report_id: ReportId
    ) -> LegalReport | None: ...

    async def save(self, report: LegalReport) -> None: ...


class ReportUnitOfWork(UnitOfWork, Protocol):
    @property
    def matters(self) -> MatterRepository: ...

    @property
    def analyses(self) -> AnalysisReadRepository: ...

    @property
    def reports(self) -> ReportRepository: ...
