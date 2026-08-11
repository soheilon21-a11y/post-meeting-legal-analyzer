from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.authorization import ApplicationAuthorizationService
from app.application.authorization import MatterAction
from app.application.commands.matter_commands import AddMatterMemberCommand
from app.application.commands.matter_commands import CreateMatterCommand
from app.application.commands.matter_commands import RenameMatterCommand
from app.application.commands.organization_commands import CreateOrganizationCommand
from app.application.commands.organization_commands import RenameOrganizationCommand
from app.application.dtos.base import PageRequest
from app.application.dtos.internal.security import ActorContext
from app.application.dtos.requests.organization_requests import CreateOrganizationRequest
from app.application.exceptions import AuthorizationError
from app.application.exceptions import ResourceNotFound
from app.application.handlers.matter_handlers import MatterCommandHandler
from app.application.handlers.matter_handlers import MatterQueryHandler
from app.application.handlers.organization_handlers import OrganizationCommandHandler
from app.application.handlers.organization_handlers import OrganizationQueryHandler
from app.application.queries.matter_queries import GetMatterQuery
from app.application.queries.matter_queries import ListOrganizationMattersQuery
from app.application.queries.organization_queries import GetOrganizationQuery
from app.domain.matter.entities import Matter
from app.domain.matter.enums import MatterMemberRole
from app.domain.matter.value_objects import MatterName
from app.domain.organization.entities import Organization
from app.domain.organization.value_objects import OrganizationName
from app.domain.shared.identifiers import MatterId
from app.domain.shared.identifiers import OrganizationId
from app.domain.shared.identifiers import UserId


class InMemoryOrganizationRepository:
    def __init__(self) -> None:
        self.items: dict[OrganizationId, Organization] = {}

    async def get(self, organization_id: OrganizationId) -> Organization | None:
        return self.items.get(organization_id)

    async def save(self, organization: Organization) -> None:
        self.items[organization.id] = organization


class InMemoryMatterRepository:
    def __init__(self) -> None:
        self.items: dict[MatterId, Matter] = {}

    async def get(self, matter_id: MatterId) -> Matter | None:
        return self.items.get(matter_id)

    async def save(self, matter: Matter) -> None:
        self.items[matter.id] = matter

    async def list_by_organization(
        self, organization_id: OrganizationId, page: PageRequest
    ) -> tuple[list[Matter], int]:
        items = list(self.items.values())
        return items[page.offset : page.offset + page.limit], len(items)


class FakeOrganizationUnitOfWork:
    def __init__(self, organizations: InMemoryOrganizationRepository) -> None:
        self.organizations = organizations
        self.commits = 0

    async def __aenter__(self) -> FakeOrganizationUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


class FakeMatterUnitOfWork:
    def __init__(
        self,
        organizations: InMemoryOrganizationRepository,
        matters: InMemoryMatterRepository,
    ) -> None:
        self.organizations = organizations
        self.matters = matters
        self.commits = 0

    async def __aenter__(self) -> FakeMatterUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


def _actor(organization_id: OrganizationId | None = None) -> ActorContext:
    return ActorContext(user_id=UserId(uuid4()), organization_id=organization_id)


@pytest.mark.anyio
async def test_create_and_query_organization() -> None:
    repository = InMemoryOrganizationRepository()
    admin = ActorContext(user_id=UserId(uuid4()), is_platform_admin=True)
    unit_of_work = FakeOrganizationUnitOfWork(repository)
    handler = OrganizationCommandHandler(lambda: unit_of_work)

    response = await handler.handle(
        CreateOrganizationCommand(
            request=CreateOrganizationRequest("Acme Legal", admin, retention_days=90)
        )
    )
    queried = await OrganizationQueryHandler(lambda: unit_of_work).handle(
        GetOrganizationQuery(organization_id=OrganizationId(response.id), actor=admin)
    )

    assert response.name == "Acme Legal"
    assert queried.retention_days == 90
    assert unit_of_work.commits == 1


@pytest.mark.anyio
async def test_organization_mutation_requires_organization_access() -> None:
    organization = Organization(OrganizationName("Acme"))
    repository = InMemoryOrganizationRepository()
    repository.items[organization.id] = organization
    unit_of_work = FakeOrganizationUnitOfWork(repository)
    handler = OrganizationCommandHandler(lambda: unit_of_work)

    with pytest.raises(AuthorizationError):
        await handler.handle(
            RenameOrganizationCommand(
                organization_id=organization.id,
                name="Unauthorized",
                actor=_actor(),
            )
        )


@pytest.mark.anyio
async def test_create_matter_adds_creator_as_owner_and_supports_query() -> None:
    organization = Organization(OrganizationName("Acme"))
    organizations = InMemoryOrganizationRepository()
    organizations.items[organization.id] = organization
    matters = InMemoryMatterRepository()
    actor = _actor(organization.id)
    unit_of_work = FakeMatterUnitOfWork(organizations, matters)
    command_handler = MatterCommandHandler(lambda: unit_of_work)

    response = await command_handler.handle(
        CreateMatterCommand(
            organization_id=organization.id,
            name="Contract review",
            actor=actor,
        )
    )
    query_handler = MatterQueryHandler(lambda: unit_of_work)
    queried = await query_handler.handle(
        GetMatterQuery(matter_id=MatterId(response.id), actor=actor)
    )

    assert queried.name == "Contract review"
    assert len(queried.members) == 1
    assert queried.members[0].user_id == actor.user_id
    assert queried.members[0].role == "owner"


@pytest.mark.anyio
async def test_matter_commands_apply_authorization_and_mutations() -> None:
    organization = Organization(OrganizationName("Acme"))
    organizations = InMemoryOrganizationRepository()
    organizations.items[organization.id] = organization
    matters = InMemoryMatterRepository()
    owner = _actor(organization.id)
    matter = Matter(MatterName("Matter"))
    matter.add_member(owner.user_id, MatterMemberRole.OWNER)
    matters.items[matter.id] = matter
    unit_of_work = FakeMatterUnitOfWork(organizations, matters)
    handler = MatterCommandHandler(lambda: unit_of_work)

    await handler.handle(RenameMatterCommand(matter_id=matter.id, name="Renamed", actor=owner))
    member = UserId(uuid4())
    await handler.handle(
        AddMatterMemberCommand(
            matter_id=matter.id,
            user_id=member,
            role=MatterMemberRole.EDITOR,
            actor=owner,
        )
    )

    assert matter.name.value == "Renamed"
    assert any(item.user_id == member for item in matter.members)


@pytest.mark.anyio
async def test_matter_lookup_and_listing_translate_resources() -> None:
    organizations = InMemoryOrganizationRepository()
    matters = InMemoryMatterRepository()
    organization = Organization(OrganizationName("Acme"))
    organizations.items[organization.id] = organization
    actor = _actor(organization.id)
    first = Matter(MatterName("One"))
    first.add_member(actor.user_id, MatterMemberRole.OWNER)
    matters.items[first.id] = first
    unit_of_work = FakeMatterUnitOfWork(organizations, matters)
    handler = MatterQueryHandler(lambda: unit_of_work)

    page = await handler.list_by_organization(
        ListOrganizationMattersQuery(
            organization_id=organization.id,
            actor=actor,
            page=PageRequest(limit=10),
        )
    )

    assert page.page.total == 1
    assert page.items[0].name == "One"

    with pytest.raises(ResourceNotFound):
        await handler.handle(GetMatterQuery(matter_id=MatterId(uuid4()), actor=actor))


def test_authorization_roles_are_explicit() -> None:
    service = ApplicationAuthorizationService()
    assert MatterAction.READ.value == "read"
    assert service is not None
