from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING
from typing import Generic
from typing import TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


class Specification(ABC, Generic[T]):
    """Composable domain predicate."""

    def is_satisfied_by(self, candidate: T) -> bool:
        raise NotImplementedError

    def and_(self, other: Specification[T]) -> Specification[T]:
        return AndSpecification(self, other)

    def or_(self, other: Specification[T]) -> Specification[T]:
        return OrSpecification(self, other)

    def not_(self) -> Specification[T]:
        return NotSpecification(self)

    def __and__(self, other: Specification[T]) -> Specification[T]:
        return self.and_(other)

    def __or__(self, other: Specification[T]) -> Specification[T]:
        return self.or_(other)

    def __invert__(self) -> Specification[T]:
        return self.not_()


class PredicateSpecification(Specification[T]):
    def __init__(self, predicate: Callable[[T], bool]) -> None:
        self._predicate = predicate

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._predicate(candidate)


class AndSpecification(Specification[T]):
    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) and self._right.is_satisfied_by(candidate)


class OrSpecification(Specification[T]):
    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) or self._right.is_satisfied_by(candidate)


class NotSpecification(Specification[T]):
    def __init__(self, specification: Specification[T]) -> None:
        self._specification = specification

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self._specification.is_satisfied_by(candidate)
