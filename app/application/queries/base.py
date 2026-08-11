from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from uuid import UUID
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class Query:
    """Immutable metadata shared by read-only application messages."""

    query_id: UUID = field(default_factory=uuid4)
