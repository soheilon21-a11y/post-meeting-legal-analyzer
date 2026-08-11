from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.exceptions.validation import ApplicationValidationError
from app.domain.matter.enums import MatterClassification
from app.domain.matter.enums import MatterMemberRole

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext


@dataclass(frozen=True, slots=True)
class CreateMatterRequest:
    organization_id: str
    name: str
    actor: ActorContext
    classification: MatterClassification = MatterClassification.GENERAL
    matter_number: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ApplicationValidationError("Matter name must not be blank", field="name")


@dataclass(frozen=True, slots=True)
class MatterActorRequest:
    matter_id: str
    actor: ActorContext


@dataclass(frozen=True, slots=True)
class RenameMatterRequest(MatterActorRequest):
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ApplicationValidationError("Matter name must not be blank", field="name")


@dataclass(frozen=True, slots=True)
class AddMatterMemberRequest(MatterActorRequest):
    user_id: str = ""
    role: MatterMemberRole = MatterMemberRole.VIEWER


@dataclass(frozen=True, slots=True)
class ChangeMatterMemberRoleRequest(MatterActorRequest):
    user_id: str = ""
    role: MatterMemberRole = MatterMemberRole.VIEWER


@dataclass(frozen=True, slots=True)
class RemoveMatterMemberRequest(MatterActorRequest):
    user_id: str = ""
