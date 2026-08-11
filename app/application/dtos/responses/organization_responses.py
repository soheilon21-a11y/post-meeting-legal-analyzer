from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class OrganizationResponse:
    id: UUID
    name: str
    status: str
    retention_days: int | None
