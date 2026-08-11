from __future__ import annotations

from dataclasses import dataclass
from typing import Generic
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ApplicationResult(Generic[T]):
    """Immutable result returned by a use case or application service."""

    value: T


@dataclass(frozen=True, slots=True)
class PageRequest:
    """Framework-independent pagination input."""

    offset: int = 0
    limit: int = 100

    def __post_init__(self) -> None:
        if self.offset < 0:
            raise ValueError("offset must not be negative")
        if self.limit < 1 or self.limit > 1000:
            raise ValueError("limit must be between 1 and 1000")


@dataclass(frozen=True, slots=True)
class PageInfo:
    """Immutable pagination metadata returned by read use cases."""

    offset: int
    limit: int
    total: int

    def __post_init__(self) -> None:
        if self.offset < 0:
            raise ValueError("offset must not be negative")
        if self.limit < 1:
            raise ValueError("limit must be positive")
        if self.total < 0:
            raise ValueError("total must not be negative")
