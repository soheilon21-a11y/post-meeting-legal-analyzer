from __future__ import annotations

import warnings
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
from app.db.models import Matter
from app.db.models import MatterClassification
from app.db.models import MatterMember
from app.db.models import MatterMemberRole
from app.db.models import MatterStatus
from app.db.models import User
from app.main import create_app

MATTER_ID = UUID("11111111-1111-1111-1111-111111111111")
USER_ID = UUID("22222222-2222-2222-2222-222222222222")
ORG_ID = UUID("33333333-3333-3333-3333-333333333333")
BASE_VERSION_ID = uuid4()
COMPARISON_VERSION_ID = uuid4()

_MATTER_ORM = Matter(
    id=MATTER_ID,
    organization_id=ORG_ID,
    name="Create matter",
    matter_number="matter-1",
    status=MatterStatus.ACTIVE,
    classification=MatterClassification.GENERAL,
)
_USER_ORM = User(
    id=USER_ID,
    organization_id=ORG_ID,
    email="editor@example.test",
    display_name="test-user-1",
    hashed_password="not-used",
    is_active=True,
    is_deleted=False,
)
_MATTER_ORM.members = [
    MatterMember(matter_id=MATTER_ID, user_id=USER_ID, role=MatterMemberRole.EDITOR)
]


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.first.return_value = value
    result.scalars.return_value.all.return_value = []
    return result


def _fake_session() -> AsyncMock:
    session = AsyncMock()

    def fake_execute(statement: object, *args: object, **kwargs: object) -> MagicMock:
        entity = statement.column_descriptions[0]["entity"]
        if entity is Matter:
            return _scalar_result(_MATTER_ORM)
        if entity is User:
            return _scalar_result(_USER_ORM)
        return _scalar_result(None)  # audit-chain lookup: fresh (empty) chain

    session.execute = AsyncMock(side_effect=fake_execute)

    async def fake_get(model: type, pk: object, *args: object, **kwargs: object) -> object:
        if model is DocumentVersion:
            return MagicMock(id=pk)
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
