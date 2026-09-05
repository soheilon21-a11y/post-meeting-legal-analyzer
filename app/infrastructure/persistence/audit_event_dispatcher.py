from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import structlog.contextvars

from app.db.models.audit import AuditEvent
from app.db.models.audit import AuditEventType
from app.domain.events.analysis_events import AnalysisApproved
from app.domain.events.analysis_events import AnalysisReadyForReview

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.shared.domain_event import DomainEvent

_EVENT_TYPE_MAP: dict[type[DomainEvent], AuditEventType] = {
    AnalysisReadyForReview: AuditEventType.ANALYSIS_REQUEST,
    AnalysisApproved: AuditEventType.ANALYSIS_APPROVE,
}


class AuditEventDispatcher:
    """Persists domain events as AuditEvent records via SQLAlchemy.

    Implements the ``EventDispatcher`` protocol so it can be injected into
    application services that need to record audit-worthy state transitions.

    Only events present in ``_EVENT_TYPE_MAP`` are persisted; unknown event
    types are silently skipped so that future domain events do not break
    existing audit infrastructure.

    The *request_id* is read from the structlog contextvars bound by
    ``RequestIdMiddleware`` and stored in the ``metadata`` JSONB column
    when available.
    """

    def __init__(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None = None,
        matter_id: uuid.UUID | None = None,
    ) -> None:
        self._session = session
        self._organization_id = organization_id
        self._actor_id = actor_id
        self._matter_id = matter_id

    async def dispatch(self, event: DomainEvent) -> None:
        audit_record = self._build_audit_record(event)
        if audit_record is not None:
            self._session.add(audit_record)
            await self._session.flush()

    async def dispatch_many(self, events: tuple[DomainEvent, ...]) -> None:
        for event in events:
            await self.dispatch(event)

    def _build_audit_record(self, event: DomainEvent) -> AuditEvent | None:
        event_type = _EVENT_TYPE_MAP.get(type(event))
        if event_type is None:
            return None

        metadata: dict[str, Any] = {
            "event_id": str(event.event_id),
            "event_name": event.event_name,
            "occurred_at": event.occurred_at.isoformat(),
            "aggregate_id": str(event.aggregate_id),
        }

        request_id = structlog.contextvars.get_contextvars().get("request_id")
        if request_id:
            metadata["request_id"] = request_id

        return AuditEvent(
            organization_id=self._organization_id,
            matter_id=self._matter_id,
            actor_id=self._actor_id,
            event_type=event_type,
            resource_type="analysis",
            resource_id=event.aggregate_id,
            metadata_json=metadata,
        )
