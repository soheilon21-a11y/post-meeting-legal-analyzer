from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from app.application.dtos.internal.ai_jobs import AIJobHandle
    from app.application.dtos.internal.ai_jobs import AIJobRequest


class AIJobOrchestrationPort(Protocol):
    async def enqueue(self, request: AIJobRequest) -> AIJobHandle:
        """Enqueue work without binding the application layer to a queue product."""

    async def mark_running(self, job_id: str) -> None: ...

    async def mark_completed(self, job_id: str) -> None: ...

    async def mark_failed(self, job_id: str, reason: str) -> None: ...
