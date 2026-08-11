from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

from app.application.ports.unit_of_work import UnitOfWork

if TYPE_CHECKING:
    from app.application.ports.document_uow import DocumentReadRepository
    from app.domain.ports.repositories import MatterRepository
    from app.domain.redlining.entities import RedlineJob
    from app.domain.shared.identifiers import MatterId
    from app.domain.shared.identifiers import RedlineJobId


class RedlineRepository(Protocol):
    async def get_for_matter(
        self, matter_id: MatterId, redline_job_id: RedlineJobId
    ) -> RedlineJob | None: ...

    async def save(self, redline_job: RedlineJob) -> None: ...


class RedlineUnitOfWork(UnitOfWork, Protocol):
    @property
    def matters(self) -> MatterRepository: ...

    @property
    def documents(self) -> DocumentReadRepository: ...

    @property
    def redlines(self) -> RedlineRepository: ...
