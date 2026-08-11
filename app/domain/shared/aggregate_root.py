from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Generic
from typing import TypeVar

from app.domain.shared.entity import Entity

if TYPE_CHECKING:
    from collections.abc import Iterator

    from app.domain.shared.domain_event import DomainEvent

from uuid import UUID

TAggregateId = TypeVar("TAggregateId", bound=UUID)


class AggregateRoot(Entity[TAggregateId], Generic[TAggregateId]):
    """Entity that owns a consistency boundary and domain event queue."""

    __slots__ = ("_domain_events",)

    def __init__(self, entity_id: TAggregateId | None = None) -> None:
        super().__init__(entity_id)
        self._domain_events: list[DomainEvent] = []

    def record_event(self, event: DomainEvent) -> None:
        if event.aggregate_id != self.id:
            raise ValueError("Domain event aggregate_id must match the aggregate root id")
        self._domain_events.append(event)

    def pull_events(self) -> tuple[DomainEvent, ...]:
        events = tuple(self._domain_events)
        self._domain_events.clear()
        return events

    def pending_events(self) -> Iterator[DomainEvent]:
        return iter(self._domain_events)
