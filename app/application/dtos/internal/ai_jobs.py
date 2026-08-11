from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from uuid import UUID
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class AIJobRequest:
    job_type: str
    matter_id: UUID
    target_id: UUID
    payload: dict[str, str]
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class AIJobHandle:
    job_id: UUID = field(default_factory=uuid4)
