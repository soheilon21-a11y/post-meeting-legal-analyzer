from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from app.domain.shared.domain_event import DomainEvent


class EventDispatcher(Protocol):
    async def dispatch(self, event: DomainEvent) -> None:
        """Dispatch one domain event; implementation belongs outside the domain."""

    async def dispatch_many(self, events: tuple[DomainEvent, ...]) -> None:
        """Dispatch an ordered batch of domain events."""
