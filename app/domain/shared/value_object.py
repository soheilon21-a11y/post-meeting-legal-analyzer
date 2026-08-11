from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import cast


class ValueObject(ABC):
    """Base class for immutable, equality-by-value domain objects."""

    __slots__ = ()

    @abstractmethod
    def _equality_components(self) -> tuple[object, ...]:
        """Return the values that define this value object."""

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if type(self) is not type(other):
            return False
        other_value = cast(ValueObject, other)
        return self._equality_components() == other_value._equality_components()

    def __hash__(self) -> int:
        return hash((type(self), self._equality_components()))
