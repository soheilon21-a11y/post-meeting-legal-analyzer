from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.authorization import ApplicationAuthorizationService
from app.application.commands.organization_commands import ActivateOrganizationCommand
from app.application.commands.organization_commands import ArchiveOrganizationCommand
from app.application.commands.organization_commands import CreateOrganizationCommand
from app.application.commands.organization_commands import RenameOrganizationCommand
from app.application.commands.organization_commands import SuspendOrganizationCommand
from app.application.lookup import ResourceLookupService
from app.application.mappers.organization import DefaultOrganizationMapper

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.dtos.responses.organization_responses import OrganizationResponse
    from app.application.mappers.organization import OrganizationMapper
    from app.application.ports.organization_uow import OrganizationUnitOfWork
    from app.application.queries.organization_queries import GetOrganizationQuery


class OrganizationCommandHandler:
    def __init__(
        self,
        uow_factory: Callable[[], OrganizationUnitOfWork],
        mapper: OrganizationMapper | None = None,
        authorization: ApplicationAuthorizationService | None = None,
        lookup: ResourceLookupService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._mapper = mapper or DefaultOrganizationMapper()
        self._authorization = authorization or ApplicationAuthorizationService()
        self._lookup = lookup or ResourceLookupService()

    async def handle(
        self,
        command: (
            CreateOrganizationCommand
            | RenameOrganizationCommand
            | SuspendOrganizationCommand
            | ActivateOrganizationCommand
            | ArchiveOrganizationCommand
        ),
    ) -> OrganizationResponse:
        if isinstance(command, CreateOrganizationCommand):
            return await self._create(command)
        async with self._uow_factory() as uow:
            organization = await self._lookup.organization(
                uow.organizations, command.organization_id
            )
            self._authorization.require_organization_access(
                command.actor, organization.id, "modify"
            )
            if isinstance(command, RenameOrganizationCommand):
                from app.domain.organization.value_objects import OrganizationName

                organization.rename(OrganizationName(command.name))
            elif isinstance(command, SuspendOrganizationCommand):
                organization.suspend()
            elif isinstance(command, ActivateOrganizationCommand):
                organization.activate()
            else:
                organization.archive()
            await uow.organizations.save(organization)
            await uow.commit()
            return self._mapper.to_response(organization)

    async def _create(self, command: CreateOrganizationCommand) -> OrganizationResponse:
        self._authorization.require_platform_admin(command.request.actor, "create")
        organization = self._mapper.to_domain(command.request)
        async with self._uow_factory() as uow:
            await uow.organizations.save(organization)
            await uow.commit()
        return self._mapper.to_response(organization)


class OrganizationQueryHandler:
    def __init__(
        self,
        uow_factory: Callable[[], OrganizationUnitOfWork],
        mapper: OrganizationMapper | None = None,
        authorization: ApplicationAuthorizationService | None = None,
        lookup: ResourceLookupService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._mapper = mapper or DefaultOrganizationMapper()
        self._authorization = authorization or ApplicationAuthorizationService()
        self._lookup = lookup or ResourceLookupService()

    async def handle(self, query: GetOrganizationQuery) -> OrganizationResponse:
        async with self._uow_factory() as uow:
            organization = await self._lookup.organization(uow.organizations, query.organization_id)
            self._authorization.require_organization_access(query.actor, organization.id, "read")
            return self._mapper.to_response(organization)
