from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.commands.base import Command

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext
    from app.application.dtos.requests.organization_requests import CreateOrganizationRequest
    from app.domain.shared.identifiers import OrganizationId


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateOrganizationCommand(Command):
    request: CreateOrganizationRequest


@dataclass(frozen=True, slots=True, kw_only=True)
class RenameOrganizationCommand(Command):
    organization_id: OrganizationId
    name: str
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class SuspendOrganizationCommand(Command):
    organization_id: OrganizationId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ActivateOrganizationCommand(Command):
    organization_id: OrganizationId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ArchiveOrganizationCommand(Command):
    organization_id: OrganizationId
    actor: ActorContext
