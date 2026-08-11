from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.ports.repositories import MatterRepository
from app.domain.ports.repositories import OrganizationRepository

if TYPE_CHECKING:
    from app.application.dtos.base import PageRequest
    from app.domain.matter.entities import Matter
    from app.domain.shared.identifiers import OrganizationId


class MatterReadRepository(MatterRepository, Protocol):
    async def list_by_organization(
        self,
        organization_id: OrganizationId,
        page: PageRequest,
    ) -> tuple[list[Matter], int]: ...


class MatterUnitOfWork(UnitOfWork, Protocol):
    @property
    def organizations(self) -> OrganizationRepository: ...

    @property
    def matters(self) -> MatterReadRepository: ...
