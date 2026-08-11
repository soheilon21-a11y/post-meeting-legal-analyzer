from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

from app.application.ports.unit_of_work import UnitOfWork

if TYPE_CHECKING:
    from app.application.ports.meeting_uow import MeetingReadRepository
    from app.domain.analysis.entities import LegalAnalysis
    from app.domain.ports.repositories import MatterRepository
    from app.domain.shared.identifiers import AnalysisId
    from app.domain.shared.identifiers import MatterId


class AnalysisReadRepository(Protocol):
    async def get(self, analysis_id: AnalysisId) -> LegalAnalysis | None: ...

    async def get_for_matter(
        self, matter_id: MatterId, analysis_id: AnalysisId
    ) -> LegalAnalysis | None: ...

    async def save(self, analysis: LegalAnalysis) -> None: ...


class AnalysisUnitOfWork(UnitOfWork, Protocol):
    @property
    def matters(self) -> MatterRepository: ...

    @property
    def meetings(self) -> MeetingReadRepository: ...

    @property
    def analyses(self) -> AnalysisReadRepository: ...
