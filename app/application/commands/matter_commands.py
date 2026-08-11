from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.commands.base import Command
from app.domain.matter.enums import MatterClassification
from app.domain.matter.enums import MatterMemberRole

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext
    from app.domain.shared.identifiers import MatterId
    from app.domain.shared.identifiers import OrganizationId
    from app.domain.shared.identifiers import UserId


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateMatterCommand(Command):
    organization_id: OrganizationId
    name: str
    actor: ActorContext
    classification: MatterClassification = MatterClassification.GENERAL
    matter_number: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class RenameMatterCommand(Command):
    matter_id: MatterId
    name: str
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class AddMatterMemberCommand(Command):
    matter_id: MatterId
    user_id: UserId
    role: MatterMemberRole
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangeMatterMemberRoleCommand(Command):
    matter_id: MatterId
    user_id: UserId
    role: MatterMemberRole
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class RemoveMatterMemberCommand(Command):
    matter_id: MatterId
    user_id: UserId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ApplyMatterLegalHoldCommand(Command):
    matter_id: MatterId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ReleaseMatterLegalHoldCommand(Command):
    matter_id: MatterId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class PutMatterOnHoldCommand(Command):
    matter_id: MatterId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ResumeMatterCommand(Command):
    matter_id: MatterId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class CloseMatterCommand(Command):
    matter_id: MatterId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ArchiveMatterCommand(Command):
    matter_id: MatterId
    actor: ActorContext
