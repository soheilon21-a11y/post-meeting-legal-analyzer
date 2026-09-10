from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

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
