from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.authorization import ApplicationAuthorizationService
from app.application.authorization import MatterAction
from app.application.commands.matter_commands import AddMatterMemberCommand
from app.application.commands.matter_commands import ApplyMatterLegalHoldCommand
from app.application.commands.matter_commands import ArchiveMatterCommand
from app.application.commands.matter_commands import ChangeMatterMemberRoleCommand
from app.application.commands.matter_commands import CloseMatterCommand
from app.application.commands.matter_commands import CreateMatterCommand
from app.application.commands.matter_commands import PutMatterOnHoldCommand
from app.application.commands.matter_commands import ReleaseMatterLegalHoldCommand
from app.application.commands.matter_commands import RemoveMatterMemberCommand
from app.application.commands.matter_commands import RenameMatterCommand
from app.application.commands.matter_commands import ResumeMatterCommand
from app.application.dtos.base import PageInfo
from app.application.dtos.responses.common_responses import PageResponse
from app.application.lookup import ResourceLookupService
from app.application.mappers.matter import DefaultMatterMapper
from app.domain.matter.enums import MatterMemberRole
from app.domain.matter.value_objects import MatterName
from app.domain.matter.value_objects import MatterNumber

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.dtos.responses.matter_responses import MatterResponse
    from app.application.mappers.matter import MatterMapper
    from app.application.ports.matter_uow import MatterUnitOfWork
    from app.application.queries.matter_queries import GetMatterQuery
    from app.application.queries.matter_queries import ListOrganizationMattersQuery


class MatterCommandHandler:
    def __init__(
        self,
        uow_factory: Callable[[], MatterUnitOfWork],
        mapper: MatterMapper | None = None,
        authorization: ApplicationAuthorizationService | None = None,
        lookup: ResourceLookupService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._mapper = mapper or DefaultMatterMapper()
        self._authorization = authorization or ApplicationAuthorizationService()
        self._lookup = lookup or ResourceLookupService()

    async def handle(
        self,
        command: (
            CreateMatterCommand
            | RenameMatterCommand
            | AddMatterMemberCommand
            | ChangeMatterMemberRoleCommand
            | RemoveMatterMemberCommand
            | ApplyMatterLegalHoldCommand
            | ReleaseMatterLegalHoldCommand
            | PutMatterOnHoldCommand
            | ResumeMatterCommand
            | CloseMatterCommand
            | ArchiveMatterCommand
        ),
    ) -> MatterResponse:
        if isinstance(command, CreateMatterCommand):
            return await self._create(command)

        async with self._uow_factory() as uow:
            matter = await self._lookup.matter(uow.matters, command.matter_id)
            action = self._action_for(command)
            self._authorization.require_matter_access(command.actor, matter, action)
            self._mutate(matter, command)
            await uow.matters.save(matter)
            await uow.commit()
            return self._mapper.to_response(matter)

    async def _create(self, command: CreateMatterCommand) -> MatterResponse:
        self._authorization.require_organization_access(
            command.actor, command.organization_id, "create matter"
        )
        async with self._uow_factory() as uow:
            await self._lookup.organization(uow.organizations, command.organization_id)
            from app.domain.matter.entities import Matter

            matter = Matter(
                name=MatterName(command.name),
                classification=command.classification,
                matter_number=(
                    MatterNumber(command.matter_number) if command.matter_number else None
                ),
            )
            matter.add_member(command.actor.user_id, self._owner_role())
            await uow.matters.save(matter)
            await uow.commit()
            return self._mapper.to_response(matter)

    @staticmethod
    def _owner_role() -> MatterMemberRole:
        return MatterMemberRole.OWNER

    @staticmethod
    def _action_for(command: object) -> MatterAction:
        if isinstance(
            command,
            AddMatterMemberCommand | ChangeMatterMemberRoleCommand | RemoveMatterMemberCommand,
        ):
            return MatterAction.MANAGE_MEMBERS
        if isinstance(command, ApplyMatterLegalHoldCommand | ReleaseMatterLegalHoldCommand):
            return MatterAction.MANAGE_HOLD
        if isinstance(command, CloseMatterCommand | ArchiveMatterCommand):
            return MatterAction.CLOSE
        return MatterAction.EDIT

    @staticmethod
    def _mutate(matter: object, command: object) -> None:
        from app.domain.matter.entities import Matter

        assert isinstance(matter, Matter)
        if isinstance(command, RenameMatterCommand):
            matter.rename(MatterName(command.name))
        elif isinstance(command, AddMatterMemberCommand):
            matter.add_member(command.user_id, command.role)
        elif isinstance(command, ChangeMatterMemberRoleCommand):
            matter.change_member_role(command.user_id, command.role)
        elif isinstance(command, RemoveMatterMemberCommand):
            matter.remove_member(command.user_id)
        elif isinstance(command, ApplyMatterLegalHoldCommand):
            matter.apply_legal_hold()
        elif isinstance(command, ReleaseMatterLegalHoldCommand):
            matter.release_legal_hold()
        elif isinstance(command, PutMatterOnHoldCommand):
            matter.put_on_hold()
        elif isinstance(command, ResumeMatterCommand):
            matter.resume()
        elif isinstance(command, CloseMatterCommand):
            matter.close()
        else:
            matter.archive()


class MatterQueryHandler:
    def __init__(
        self,
        uow_factory: Callable[[], MatterUnitOfWork],
        mapper: MatterMapper | None = None,
        authorization: ApplicationAuthorizationService | None = None,
        lookup: ResourceLookupService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._mapper = mapper or DefaultMatterMapper()
        self._authorization = authorization or ApplicationAuthorizationService()
        self._lookup = lookup or ResourceLookupService()

    async def handle(self, query: GetMatterQuery) -> MatterResponse:
        async with self._uow_factory() as uow:
            matter = await self._lookup.matter(uow.matters, query.matter_id)
            self._authorization.require_matter_access(query.actor, matter, MatterAction.READ)
            return self._mapper.to_response(matter)

    async def list_by_organization(
        self, query: ListOrganizationMattersQuery
    ) -> PageResponse[MatterResponse]:
        self._authorization.require_organization_access(query.actor, query.organization_id, "read")
        async with self._uow_factory() as uow:
            await self._lookup.organization(uow.organizations, query.organization_id)
            matters, total = await uow.matters.list_by_organization(
                query.organization_id, query.page
            )
            return PageResponse(
                items=tuple(self._mapper.to_response(matter) for matter in matters),
                page=PageInfo(query.page.offset, query.page.limit, total),
            )
