from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

from app.application.ports.unit_of_work import UnitOfWork

if TYPE_CHECKING:
    from app.domain.ports.repositories import OrganizationRepository


class OrganizationUnitOfWork(UnitOfWork, Protocol):
    @property
    def organizations(self) -> OrganizationRepository: ...
