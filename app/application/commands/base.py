from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from uuid import UUID
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class Command:
    """Immutable metadata shared by state-changing application messages."""

    message_id: UUID = field(default_factory=uuid4)
    issued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
