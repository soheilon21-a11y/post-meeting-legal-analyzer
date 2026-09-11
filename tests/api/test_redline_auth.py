from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.core.security import tokens as tokens_module
from app.core.security.tokens import TokenService

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.mark.anyio
async def test_post_redlines_without_auth_header_returns_401(
    async_client: AsyncClient,
) -> None:
    response = await async_client.post(
        "/api/v1/redlines/",
        json={"matter_id": "matter-1", "title": "Supplier Agreement Review"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["status"] == 401


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
