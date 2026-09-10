from __future__ import annotations

import warnings
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from uuid import UUID
from uuid import uuid4

import pytest
from httpx import ASGITransport
from httpx import AsyncClient

from app.api.dependencies.db import get_db
from app.core.security.tokens import TokenService
from app.db.models import DocumentVersion
from app.db.models import MatterMemberRole
from app.main import create_app

MATTER_ID = UUID("11111111-1111-1111-1111-111111111111")
USER_ID = UUID("22222222-2222-2222-2222-222222222222")
BASE_VERSION_ID = uuid4()
COMPARISON_VERSION_ID = uuid4()


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.first.return_value = value
    return result


def _fake_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_result(
                SimpleNamespace(
                    id=MATTER_ID,
                    members=[
                        SimpleNamespace(user_id=USER_ID, role=MatterMemberRole.EDITOR)
                    ],
                )
            ),
            _scalar_result(SimpleNamespace(id=USER_ID, display_name="test-user-1")),
        ]
    )

    async def fake_get(model: type, pk: object, *args: object, **kwargs: object) -> object:
        if model is DocumentVersion:
            return SimpleNamespace(id=pk)
        return None

    session.get = AsyncMock(side_effect=fake_get)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.mark.anyio
async def test_create_redline_authenticated_returns_201_without_never_awaited_warning() -> None:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: _fake_session()
    token = TokenService().create_access_token("test-user-1", "org-1")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/redlines/",
                json={
                    "matter_id": "matter-1",
                    "base_document_id": str(BASE_VERSION_ID),
                    "comparison_document_id": str(COMPARISON_VERSION_ID),
                    "deterministic_seed": 42,
                },
                headers={"Authorization": f"Bearer {token}"},
            )

    assert response.status_code == 201, response.text
    body = response.json()
    assert UUID(body["id"])
    assert body["status"] == "pending"
    assert body["changes"] == []
    assert not [w for w in caught if "never awaited" in str(w.message)]


@pytest.mark.anyio
async def test_create_redline_with_missing_matter_returns_404_not_500() -> None:
    app = create_app()
    session = _fake_session()
    session.execute = AsyncMock(side_effect=[_scalar_result(None), _scalar_result(None)])
    app.dependency_overrides[get_db] = lambda: session
    token = TokenService().create_access_token("test-user-1", "org-1")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/redlines/",
            json={
                "matter_id": "matter-does-not-exist",
                "base_document_id": str(BASE_VERSION_ID),
                "comparison_document_id": str(COMPARISON_VERSION_ID),
                "deterministic_seed": 42,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
