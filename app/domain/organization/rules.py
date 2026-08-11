from app.domain.exceptions.lifecycle import InvalidStateTransition
from app.domain.organization.enums import OrganizationStatus


def ensure_organization_can_be_suspended(status: OrganizationStatus) -> None:
    if status is not OrganizationStatus.ACTIVE:
        raise InvalidStateTransition("Organization", status, OrganizationStatus.SUSPENDED)


def ensure_organization_can_be_archived(status: OrganizationStatus) -> None:
    if status is OrganizationStatus.ARCHIVED:
        raise InvalidStateTransition("Organization", status, OrganizationStatus.ARCHIVED)
