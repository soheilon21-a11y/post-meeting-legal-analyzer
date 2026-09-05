from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.audit import get_audit_dispatcher
from app.main import create_app

if TYPE_CHECKING:
    from app.domain.shared.domain_event import DomainEvent


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


def test_analyze_endpoint_receives_dispatcher_dependency(client):
    """Verify the endpoint accepts the dispatcher dependency parameter."""
    mock_dispatcher = MagicMock()
    mock_dispatcher.dispatch = AsyncMock()
    mock_dispatcher.dispatch_many = AsyncMock()

    app_override = create_app()
    app_override.dependency_overrides[get_audit_dispatcher] = lambda: mock_dispatcher

    with TestClient(app_override, raise_server_exceptions=False) as test_client:
        response = test_client.post(
            "/api/v1/analyze",
            json={"text": "Test meeting", "use_llm": False},
        )

    assert response.status_code == 200
    mock_dispatcher.dispatch_many.assert_called()


def test_analyze_endpoint_dispatches_domain_events(client):
    """Verify domain events are dispatched during analysis execution."""
    dispatched_events: list[DomainEvent] = []

    class RecordingDispatcher:
        async def dispatch(self, event: DomainEvent) -> None:
            dispatched_events.append(event)

        async def dispatch_many(self, events: tuple[DomainEvent, ...]) -> None:
            dispatched_events.extend(events)

    app_override = create_app()
    app_override.dependency_overrides[get_audit_dispatcher] = lambda: RecordingDispatcher()

    with TestClient(app_override, raise_server_exceptions=False) as test_client:
        response = test_client.post(
            "/api/v1/analyze",
            json={"text": "The parties agreed to confidentiality terms", "use_llm": False},
        )

    assert response.status_code == 200
    assert len(dispatched_events) > 0

    event_names = [type(e).__name__ for e in dispatched_events]
    assert "AnalysisReadyForReview" in event_names


def test_analyze_endpoint_works_without_dispatcher(client):
    """Verify endpoint works gracefully when dispatcher is None."""
    app_override = create_app()
    app_override.dependency_overrides[get_audit_dispatcher] = lambda: None

    with TestClient(app_override, raise_server_exceptions=False) as test_client:
        response = test_client.post(
            "/api/v1/analyze",
            json={"text": "Test meeting", "use_llm": False},
        )

    assert response.status_code == 200
    assert "id" in response.json()


def test_analyze_endpoint_preserves_request_id_in_events(client):
    """Verify request_id context is preserved when events are dispatched."""
    import structlog.contextvars

    dispatched_events: list[DomainEvent] = []
    request_ids_seen: list[str | None] = []

    class RecordingDispatcher:
        async def dispatch(self, event: DomainEvent) -> None:
            dispatched_events.append(event)
            ctx = structlog.contextvars.get_contextvars()
            request_ids_seen.append(ctx.get("request_id"))

        async def dispatch_many(self, events: tuple[DomainEvent, ...]) -> None:
            for event in events:
                await self.dispatch(event)

    app_override = create_app()
    app_override.dependency_overrides[get_audit_dispatcher] = lambda: RecordingDispatcher()

    test_request_id = "test-request-123"

    with TestClient(app_override, raise_server_exceptions=False) as test_client:
        response = test_client.post(
            "/api/v1/analyze",
            json={"text": "Test meeting", "use_llm": False},
            headers={"X-Request-ID": test_request_id},
        )

    assert response.status_code == 200
    assert len(dispatched_events) > 0
    assert test_request_id in request_ids_seen


def test_analyze_endpoint_no_duplicate_dispatch(client):
    """Verify events are dispatched exactly once per analysis."""
    dispatch_counts: dict[str, int] = {}

    class CountingDispatcher:
        async def dispatch(self, event: DomainEvent) -> None:
            event_name = type(event).__name__
            dispatch_counts[event_name] = dispatch_counts.get(event_name, 0) + 1

        async def dispatch_many(self, events: tuple[DomainEvent, ...]) -> None:
            for event in events:
                await self.dispatch(event)

    app_override = create_app()
    app_override.dependency_overrides[get_audit_dispatcher] = lambda: CountingDispatcher()

    with TestClient(app_override, raise_server_exceptions=False) as test_client:
        response = test_client.post(
            "/api/v1/analyze",
            json={"text": "Test meeting", "use_llm": False},
        )

    assert response.status_code == 200
    for count in dispatch_counts.values():
        assert count == 1, f"Event dispatched {count} times instead of 1"
