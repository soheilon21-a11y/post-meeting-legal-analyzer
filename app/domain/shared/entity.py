from __future__ import annotations

from typing import Generic
from typing import TypeVar
from typing import cast
from uuid import UUID

from app.domain.shared.identifiers import new_entity_id

TId = TypeVar("TId", bound=UUID)


class Entity(Generic[TId]):
    """Base class for identity-based domain objects."""

    __slots__ = ("_id",)

    def __init__(self, entity_id: TId | None = None) -> None:
        self._id = entity_id or cast(TId, new_entity_id())

    @property
    def id(self) -> TId:
        return self._id

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, Entity):
            return False
        return type(self) is type(other) and self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))
