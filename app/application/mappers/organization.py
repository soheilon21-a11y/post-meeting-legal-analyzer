from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

from app.application.dtos.responses.organization_responses import OrganizationResponse
from app.domain.organization.entities import Organization
from app.domain.organization.value_objects import OrganizationName
from app.domain.organization.value_objects import RetentionPolicy

if TYPE_CHECKING:
    from app.application.dtos.requests.organization_requests import CreateOrganizationRequest


class OrganizationMapper(Protocol):
    def to_domain(self, request: CreateOrganizationRequest) -> Organization: ...

    def to_response(self, organization: Organization) -> OrganizationResponse: ...


class DefaultOrganizationMapper:
    def to_domain(self, request: CreateOrganizationRequest) -> Organization:
        return Organization(
            name=OrganizationName(request.name),
            retention_policy=RetentionPolicy(request.retention_days),
        )

    def to_response(self, organization: Organization) -> OrganizationResponse:
        return OrganizationResponse(
            id=organization.id,
            name=organization.name.value,
            status=organization.status.value,
            retention_days=organization.retention_policy.days,
        )
