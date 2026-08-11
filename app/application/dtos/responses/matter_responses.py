from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class MatterMemberResponse:
    user_id: UUID
    role: str


@dataclass(frozen=True, slots=True)
class MatterResponse:
    id: UUID
    name: str
    matter_number: str | None
    classification: str
    status: str
    legal_hold: bool
    members: tuple[MatterMemberResponse, ...]
