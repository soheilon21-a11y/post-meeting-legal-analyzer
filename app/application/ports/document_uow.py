from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.ports.repositories import DocumentRepository
from app.domain.ports.repositories import MatterRepository

if TYPE_CHECKING:
    from app.domain.document.entities import Document
    from app.domain.shared.identifiers import DocumentId
    from app.domain.shared.identifiers import MatterId


class DocumentReadRepository(DocumentRepository, Protocol):
    async def get_for_matter(
        self, matter_id: MatterId, document_id: DocumentId
    ) -> Document | None: ...


class DocumentUnitOfWork(UnitOfWork, Protocol):
    @property
    def matters(self) -> MatterRepository: ...

    @property
    def documents(self) -> DocumentReadRepository: ...
