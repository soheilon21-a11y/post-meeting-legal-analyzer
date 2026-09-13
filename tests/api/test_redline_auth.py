from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport
from httpx import AsyncClient

from app.api.dependencies.db import get_db
from app.core.security import tokens as tokens_module
from app.core.security.tokens import TokenService
from app.main import create_app


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.first.return_value = value
    result.scalars.return_value.all.return_value = []
    return result


def _empty_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_scalar_result(None), _scalar_result(None)])
    session.get = AsyncMock(return_value=None)
    return session


@pytest.mark.anyio
async def test_post_redlines_without_token_is_not_rejected_with_401_403() -> None:
    """Phase 1 contract: a missing token must never 401/403 on redlines.

    With no credential at all the request proceeds as the matter's default
    user — here the matter simply does not exist, so the honest outcome is
    404, not an authentication wall.
    """
    app = create_app()
    app.dependency_overrides[get_db] = _empty_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/redlines/",
            json={
                "matter_id": "matter-1",
                "base_document_id": str(uuid4()),
                "comparison_document_id": str(uuid4()),
                "deterministic_seed": 42,
            },
        )

    assert response.status_code == 404, response.text
    assert "not found" in response.json()["detail"]


@pytest.mark.anyio
async def test_get_redline_without_token_is_allowed() -> None:
    """Reads never wrote audit rows, so no token is simply accepted."""
    from app.db.models.redline import RedlineJob
    from app.db.models.redline import RedlineStatus

    job = RedlineJob(
        id=uuid4(),
        matter_id=uuid4(),
        base_document_version_id=uuid4(),
        comparison_document_version_id=uuid4(),
        status=RedlineStatus.PENDING,
        configuration={},
    )
    job.changes = []

    session = AsyncMock()
    session.get = AsyncMock(return_value=job)
    session.add = MagicMock()
    session.flush = AsyncMock()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/redlines/{job.id}")

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(job.id)


@pytest.mark.anyio
async def test_post_redlines_with_expired_token_returns_401(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: expired JWT must 401 (problem+json), never 500."""
    monkeypatch.setattr(
        tokens_module.TokenPayload,
        "_default_expiry",
        lambda self: datetime.now(UTC) - timedelta(minutes=5),
    )
    token = TokenService().create_access_token(str(uuid4()), str(uuid4()))

    response = await async_client.post(
        "/api/v1/redlines/",
        json={"matter_id": "matter-1", "title": "Supplier Agreement Review"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401, response.text
    body = response.json()
    assert body["status"] == 401
    assert "invalid or expired" in body["detail"]
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.anyio
async def test_post_redlines_with_garbage_token_returns_401(
    async_client: AsyncClient,
) -> None:
    """Regression: an undecodable bearer token must 401, never 500."""
    response = await async_client.post(
        "/api/v1/redlines/",
        json={"matter_id": "matter-1", "title": "Supplier Agreement Review"},
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )

    assert response.status_code == 401, response.text
    body = response.json()
    assert body["status"] == 401
