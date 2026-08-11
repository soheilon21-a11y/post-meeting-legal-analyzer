from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

from app.application.dtos.responses.matter_responses import MatterMemberResponse
from app.application.dtos.responses.matter_responses import MatterResponse

if TYPE_CHECKING:
    from app.domain.matter.entities import Matter


class MatterMapper(Protocol):
    def to_response(self, matter: Matter) -> MatterResponse: ...


class DefaultMatterMapper:
    def to_response(self, matter: Matter) -> MatterResponse:
        members = tuple(
            MatterMemberResponse(user_id=member.user_id, role=member.role.value)
            for member in matter.members
        )
        return MatterResponse(
            id=matter.id,
            name=matter.name.value,
            matter_number=matter.matter_number.value if matter.matter_number else None,
            classification=matter.classification.value,
            status=matter.status.value,
            legal_hold=matter.legal_hold,
            members=members,
        )
