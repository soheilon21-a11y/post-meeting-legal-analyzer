from __future__ import annotations

from app.domain.organization.enums import OrganizationStatus
from app.domain.organization.rules import ensure_organization_can_be_archived
from app.domain.organization.rules import ensure_organization_can_be_suspended
from app.domain.organization.value_objects import OrganizationName
from app.domain.organization.value_objects import RetentionPolicy
from app.domain.shared.aggregate_root import AggregateRoot
from app.domain.shared.identifiers import OrganizationId


class Organization(AggregateRoot[OrganizationId]):
    def __init__(
        self,
        name: OrganizationName,
        retention_policy: RetentionPolicy | None = None,
        organization_id: OrganizationId | None = None,
    ) -> None:
        super().__init__(organization_id)
        self._name = name
        self._retention_policy = retention_policy or RetentionPolicy(None)
        self._status = OrganizationStatus.ACTIVE

    @property
    def name(self) -> OrganizationName:
        return self._name

    @property
    def retention_policy(self) -> RetentionPolicy:
        return self._retention_policy

    @property
    def status(self) -> OrganizationStatus:
        return self._status

    def rename(self, name: OrganizationName) -> None:
        self._ensure_active()
        self._name = name

    def change_retention_policy(self, policy: RetentionPolicy) -> None:
        self._ensure_active()
        self._retention_policy = policy

    def suspend(self) -> None:
        ensure_organization_can_be_suspended(self._status)
        self._status = OrganizationStatus.SUSPENDED

    def activate(self) -> None:
        if self._status is OrganizationStatus.ARCHIVED:
            raise ValueError("An archived organization cannot be activated")
        self._status = OrganizationStatus.ACTIVE

    def archive(self) -> None:
        ensure_organization_can_be_archived(self._status)
        self._status = OrganizationStatus.ARCHIVED

    def _ensure_active(self) -> None:
        if self._status is not OrganizationStatus.ACTIVE:
            raise ValueError("Only active organizations can be modified")
