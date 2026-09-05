from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.security.tokens import TokenService
from app.main import create_app


@pytest.fixture
def async_client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def valid_jwt_token():
    """Create a valid JWT token with org_id and sub for audit dispatcher."""
    token_service = TokenService()
    # org_id must be a valid UUID string - get_audit_dispatcher does UUID(payload.org_id)
    # user_id must also be a valid UUID string since actor_id = UUID(payload.sub)
    return token_service.create_access_token(
        user_id="12345678-1234-1234-1234-123456789012", org_id="11111111-1111-1111-1111-111111111111"
    )


@pytest.fixture
def setup_audit_tables():
    """Ensure the minimal database rows needed for audit persistence exist."""
    import asyncio

    async def _seed_reference_rows() -> None:
        from sqlalchemy import text as sa_text

        from app.db.base import Base
        from app.db.models import AuditEvent
        from app.db.models import Matter
        from app.db.models import Organization
        from app.db.models import User

        settings = get_settings()
        engine = create_async_engine(settings.postgres.database_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all,
                tables=[
                    Organization.__table__,
                    User.__table__,
                    Matter.__table__,
                    AuditEvent.__table__,
                ],
            )
            await conn.execute(
                sa_text(
                    """
                    INSERT INTO organizations (id, name)
                    VALUES ('11111111-1111-1111-1111-111111111111', 'Test Organization')
                    ON CONFLICT (id) DO NOTHING
                    """
                )
            )
            await conn.execute(
                sa_text(
                    """
                    INSERT INTO users (id, organization_id, email, display_name, hashed_password, is_active)
                    VALUES (
                        '12345678-1234-1234-1234-123456789012',
                        '11111111-1111-1111-1111-111111111111',
                        'audit-test@example.com',
                        'Audit Test User',
                        'not-used-in-this-test',
                        true
                    )
                    ON CONFLICT (id) DO NOTHING
                    """
                )
            )
        await engine.dispose()

    asyncio.run(_seed_reference_rows())


async def test_audit_event_persistence_against_real_postgres(async_client, valid_jwt_token, setup_audit_tables):
    """End-to-end: POST /api/v1/analyze persists an AuditEvent row to real PostgreSQL.

    Verifies:
    - AuditEvent row exists in PostgreSQL after the analysis request
    - Correct event_type is stored (analysis_request)
    - resource_id (analysis aggregate ID) is correct
    - organization_id is correct
    - request_id is preserved in metadata_json
    - event metadata contains expected identifiers
    """
    # Generate a unique request ID to verify it's preserved in the audit record
    test_request_id = str(uuid.uuid4())

    # Send analysis request with valid auth token and request ID
    response = await async_client.post(
        "/api/v1/analyze",
        json={"text": "The parties agreed to confidentiality and privilege terms", "use_llm": False},
        headers={
            "Authorization": f"Bearer {valid_jwt_token}",
            "X-Request-ID": test_request_id,
        },
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Query the REAL PostgreSQL database to verify AuditEvent was persisted
    settings = get_settings()
    engine: AsyncEngine = create_async_engine(settings.postgres.database_url, echo=False)

    async with engine.connect() as conn:
        from sqlalchemy import text as sa_text

        result = await conn.execute(
            sa_text(
                "SELECT event_type, resource_id, organization_id, metadata, created_at "
                "FROM audit_events ORDER BY created_at DESC LIMIT 1"
            )
        )
        row = result.fetchone()

    # Verify an AuditEvent row was actually persisted
    assert row is not None, (
        "No AuditEvent row was persisted to PostgreSQL. "
        "The dispatcher may have returned None (no auth org_id) or the event was not mapped."
    )

    event_type = row[0]
    resource_id = row[1]
    organization_id = row[2]
    metadata = row[3] or {}
    created_at = row[4]

    # --- Verification ---

    # 1. Correct event type is stored
    assert event_type == "analysis_request", (
        f"Expected event_type='analysis_request', got '{event_type}'"
    )

    # 2. resource_id (analysis aggregate ID) is correct and is a UUID
    assert resource_id is not None, "resource_id should not be None"
    uuid.UUID(str(resource_id))

    # 3. organization_id is correct (non-null, set from JWT token)
    assert organization_id is not None, "organization_id should not be None when auth is provided"

    # 4. request_id is preserved in metadata
    assert "request_id" in metadata, "request_id should be present in metadata"
    assert metadata["request_id"] == test_request_id, (
        f"Expected request_id={test_request_id} in metadata, got {metadata.get('request_id')}"
    )

    # 5. Event metadata contains expected identifiers
    assert "event_id" in metadata, "event_id should be in metadata"
    assert "event_name" in metadata, "event_name should be in metadata"
    assert "aggregate_id" in metadata, "aggregate_id should be in metadata"
    assert metadata["aggregate_id"] == str(resource_id), "aggregate_id should match resource_id"

    # 6. created_at is a valid timestamp
    assert created_at is not None, "created_at should not be None"

    print(
        f"\n--- AuditEvent Verification ---\n"
        f"event_type: {event_type}\n"
        f"resource_id: {resource_id}\n"
        f"organization_id: {organization_id}\n"
        f"request_id in metadata: {metadata.get('request_id')}\n"
        f"created_at: {created_at}\n"
        f"----------------------------------------\n"
    )
