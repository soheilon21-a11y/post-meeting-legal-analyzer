from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.exceptions.validation import ApplicationValidationError

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext


@dataclass(frozen=True, slots=True)
class CreateOrganizationRequest:
    name: str
    actor: ActorContext
    retention_days: int | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ApplicationValidationError("Organization name must not be blank", field="name")
        if self.retention_days is not None and self.retention_days < 0:
            raise ApplicationValidationError(
                "Retention days must not be negative", field="retention_days"
            )


@dataclass(frozen=True, slots=True)
class RenameOrganizationRequest:
    organization_id: str
    name: str
    actor: ActorContext

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ApplicationValidationError("Organization name must not be blank", field="name")
