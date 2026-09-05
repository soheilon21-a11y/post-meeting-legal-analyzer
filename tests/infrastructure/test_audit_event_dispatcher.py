from __future__ import annotations

import uuid
from typing import Any

import pytest
import structlog.contextvars

from app.db.models.audit import AuditEvent
from app.db.models.audit import AuditEventType
from app.domain.events.analysis_events import AnalysisApproved
from app.domain.events.analysis_events import AnalysisReadyForReview
from app.domain.shared.domain_event import DomainEvent
from app.domain.shared.identifiers import AnalysisId
from app.infrastructure.persistence.audit_event_dispatcher import AuditEventDispatcher


class FakeSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushed: int = 0

    def add(self, instance: Any) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flushed += 1


class UnsupportedEvent(DomainEvent):
    aggregate_id: uuid.UUID


def _org_id() -> uuid.UUID:
    return uuid.uuid4()


def _analysis_id() -> AnalysisId:
    return AnalysisId(uuid.uuid4())


@pytest.fixture(autouse=True)
def _clear_context() -> None:
    structlog.contextvars.clear_contextvars()


@pytest.mark.anyio
async def test_dispatch_maps_analysis_ready_for_review() -> None:
    session = FakeSession()
    org_id = _org_id()
    analysis_id = _analysis_id()
    dispatcher = AuditEventDispatcher(session, org_id)

    event = AnalysisReadyForReview(aggregate_id=analysis_id)
    await dispatcher.dispatch(event)

    assert len(session.added) == 1
    record = session.added[0]
    assert isinstance(record, AuditEvent)
    assert record.event_type == AuditEventType.ANALYSIS_REQUEST
    assert record.organization_id == org_id
    assert record.resource_type == "analysis"
    assert record.resource_id == analysis_id


@pytest.mark.anyio
async def test_dispatch_maps_analysis_approved() -> None:
    session = FakeSession()
    org_id = _org_id()
    analysis_id = _analysis_id()
    dispatcher = AuditEventDispatcher(session, org_id)

    event = AnalysisApproved(aggregate_id=analysis_id)
    await dispatcher.dispatch(event)

    assert len(session.added) == 1
    record = session.added[0]
    assert isinstance(record, AuditEvent)
    assert record.event_type == AuditEventType.ANALYSIS_APPROVE


@pytest.mark.anyio
async def test_dispatch_preserves_identifiers() -> None:
    session = FakeSession()
    org_id = _org_id()
    matter_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    analysis_id = _analysis_id()
    dispatcher = AuditEventDispatcher(
        session, org_id, actor_id=actor_id, matter_id=matter_id
    )

    await dispatcher.dispatch(AnalysisReadyForReview(aggregate_id=analysis_id))

    record = session.added[0]
    assert record.organization_id == org_id
    assert record.matter_id == matter_id
    assert record.actor_id == actor_id
    assert record.resource_id == analysis_id


@pytest.mark.anyio
async def test_dispatch_includes_request_id_from_context() -> None:
    session = FakeSession()
    structlog.contextvars.bind_contextvars(request_id="req-abc-123")
    analysis_id = _analysis_id()
    dispatcher = AuditEventDispatcher(session, _org_id())

    await dispatcher.dispatch(AnalysisReadyForReview(aggregate_id=analysis_id))

    record = session.added[0]
    assert record.metadata_json is not None
    assert record.metadata_json["request_id"] == "req-abc-123"


@pytest.mark.anyio
async def test_dispatch_omits_request_id_when_not_in_context() -> None:
    session = FakeSession()
    analysis_id = _analysis_id()
    dispatcher = AuditEventDispatcher(session, _org_id())

    await dispatcher.dispatch(AnalysisReadyForReview(aggregate_id=analysis_id))

    record = session.added[0]
    assert record.metadata_json is not None
    assert "request_id" not in record.metadata_json


@pytest.mark.anyio
async def test_dispatch_preserves_event_metadata() -> None:
    session = FakeSession()
    analysis_id = _analysis_id()
    dispatcher = AuditEventDispatcher(session, _org_id())

    event = AnalysisReadyForReview(aggregate_id=analysis_id)
    await dispatcher.dispatch(event)

    record = session.added[0]
    metadata = record.metadata_json
    assert metadata is not None
    assert metadata["event_id"] == str(event.event_id)
    assert metadata["event_name"] == "AnalysisReadyForReview"
    assert metadata["aggregate_id"] == str(analysis_id)
    assert "occurred_at" in metadata


@pytest.mark.anyio
async def test_dispatch_many_handles_multiple_events() -> None:
    session = FakeSession()
    org_id = _org_id()
    a1 = _analysis_id()
    a2 = _analysis_id()
    dispatcher = AuditEventDispatcher(session, org_id)

    events = (
        AnalysisReadyForReview(aggregate_id=a1),
        AnalysisApproved(aggregate_id=a2),
    )
    await dispatcher.dispatch_many(events)

    assert len(session.added) == 2
    assert session.added[0].resource_id == a1
    assert session.added[0].event_type == AuditEventType.ANALYSIS_REQUEST
    assert session.added[1].resource_id == a2
    assert session.added[1].event_type == AuditEventType.ANALYSIS_APPROVE


@pytest.mark.anyio
async def test_dispatch_skips_unsupported_events() -> None:
    session = FakeSession()
    dispatcher = AuditEventDispatcher(session, _org_id())

    unsupported = UnsupportedEvent(aggregate_id=uuid.uuid4())
    await dispatcher.dispatch(unsupported)

    assert session.added == []
    assert session.flushed == 0


@pytest.mark.anyio
async def test_dispatch_many_with_mixed_events_only_persists_mapped() -> None:
    session = FakeSession()
    org_id = _org_id()
    analysis_id = _analysis_id()
    dispatcher = AuditEventDispatcher(session, org_id)

    events: tuple[DomainEvent, ...] = (
        AnalysisReadyForReview(aggregate_id=analysis_id),
        UnsupportedEvent(aggregate_id=uuid.uuid4()),
        AnalysisApproved(aggregate_id=analysis_id),
    )
    await dispatcher.dispatch_many(events)

    assert len(session.added) == 2
    assert session.flushed == 2


@pytest.mark.anyio
async def test_dispatch_calls_session_add_and_flush() -> None:
    session = FakeSession()
    dispatcher = AuditEventDispatcher(session, _org_id())

    await dispatcher.dispatch(AnalysisReadyForReview(aggregate_id=_analysis_id()))

    assert len(session.added) == 1
    assert session.flushed == 1


@pytest.mark.anyio
async def test_dispatch_many_flushes_per_event() -> None:
    session = FakeSession()
    dispatcher = AuditEventDispatcher(session, _org_id())
    analysis_id = _analysis_id()

    events = (
        AnalysisReadyForReview(aggregate_id=analysis_id),
        AnalysisApproved(aggregate_id=analysis_id),
    )
    await dispatcher.dispatch_many(events)

    assert session.flushed == 2
