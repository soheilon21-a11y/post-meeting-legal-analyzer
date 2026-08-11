from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from uuid import UUID
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Immutable business fact raised by an aggregate."""

    aggregate_id: UUID
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def event_name(self) -> str:
        return type(self).__name__
