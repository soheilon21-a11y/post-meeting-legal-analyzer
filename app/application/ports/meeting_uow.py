from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.ports.repositories import MatterRepository
from app.domain.ports.repositories import MeetingRepository

if TYPE_CHECKING:
    from app.domain.meeting.entities import Meeting
    from app.domain.shared.identifiers import MatterId
    from app.domain.shared.identifiers import MeetingId


class MeetingReadRepository(MeetingRepository, Protocol):
    async def get_for_matter(
        self, matter_id: MatterId, meeting_id: MeetingId
    ) -> Meeting | None: ...


class MeetingUnitOfWork(UnitOfWork, Protocol):
    @property
    def matters(self) -> MatterRepository: ...

    @property
    def meetings(self) -> MeetingReadRepository: ...
