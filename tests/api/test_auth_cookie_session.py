from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from http.cookies import SimpleCookie
from typing import Any
from uuid import UUID
from uuid import uuid4

import pytest
from httpx import ASGITransport
from httpx import AsyncClient
from sqlalchemy import BinaryExpression

from app.api.dependencies.db import get_db
from app.core.security.tokens import SESSION_COOKIE_NAME
from app.core.security.tokens import TokenService
from app.db.models import AuditEvent
from app.db.models import DocumentVersion
from app.db.models import ProcessingStatus
from app.db.models import User
from app.db.models.session import Session
from app.main import create_app

EMAIL = "cookie-attorney@example.com"
PASSWORD = "Str0ng-Passw0rd!"
CSRF_HEADER = {"X-Requested-With": "XMLHttpRequest"}


class _Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Any]:
        return list(self._rows)


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)


def _eq_conditions(clause: Any) -> dict[str, Any]:
    conditions: dict[str, Any] = {}
    stack = [clause]
    while stack:
        node = stack.pop()
        if node is None:
            continue
        if hasattr(node, "clauses"):
            stack.extend(node.clauses)
            continue
        if isinstance(node, BinaryExpression):
            left, right = node.left, node.right
            if hasattr(left, "name") and hasattr(right, "value"):
                conditions[left.name] = right.value
    return conditions


class FakeSession:
    """In-memory session double (per-request semantics like tests/api/
    test_auth_flow.py) extended for the sessions table and audit-chain
    head lookups."""

    def __init__(self) -> None:
        self.rows: list[Any] = []

    def add(self, instance: Any) -> None:
        if instance not in self.rows:
            self.rows.append(instance)

    async def flush(self) -> None:
        return None

    def _id_of(self, row: Any) -> Any:
        row_id = getattr(row, "id", None)
        if row_id is None:
            row_id = getattr(row, "session_id", None)
        return row_id

    async def get(self, model: type, pk: Any, *args: Any, **kwargs: Any) -> Any:
        for row in self.rows:
            if isinstance(row, model) and self._id_of(row) == pk:
                return row
        return None

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> _Result:
        entity = statement.column_descriptions[0]["entity"]
        conditions = _eq_conditions(statement.whereclause)
        matches = [
            row
            for row in self.rows
            if isinstance(row, entity)
            and all(
                getattr(row, key, None) == value for key, value in conditions.items()
            )
        ]
        if entity is AuditEvent:
            # Real DB: ORDER BY seq DESC LIMIT 1 → first() = chain head.
            matches.sort(
                key=lambda row: row.seq if row.seq is not None else 0, reverse=True
            )
        return _Result(matches)

    def of_type(self, model: type) -> list[Any]:
        return [row for row in self.rows if isinstance(row, model)]


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def app(session: FakeSession) -> Any:
    application = create_app()
    application.dependency_overrides[get_db] = lambda: session
    return application


def _client(app: Any) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _register(client: AsyncClient) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "display_name": "Cookie Attorney",
            "organization_name": "Cookie Firm",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _cookie_value(response: Any, key: str = SESSION_COOKIE_NAME) -> str | None:
    morsel = SimpleCookie(response.headers.get("set-cookie", ""))
    return morsel[key].value if key in morsel else None


def _add_document_versions(session: FakeSession) -> tuple[Any, Any]:
    base = DocumentVersion(
        id=uuid4(),
        document_id=uuid4(),
        version_number=1,
        object_storage_key="local/base",
        processing_status=ProcessingStatus.COMPLETED,
    )
    comparison = DocumentVersion(
        id=uuid4(),
        document_id=uuid4(),
        version_number=1,
        object_storage_key="local/comparison",
        processing_status=ProcessingStatus.COMPLETED,
    )
    session.add(base)
    session.add(comparison)
    return base, comparison


# ─── 1. Cookie shape on register/login ─────────────────────────────────────


@pytest.mark.anyio
async def test_register_sets_hardened_local_session_cookie(app: Any, session: FakeSession) -> None:
    async with _client(app) as client:
        registered = await _register(client)

    raw = client_last = None
    del raw, client_last

    assert session.of_type(Session).__len__() == 1
    row = session.of_type(Session)[0]
    assert row.revoked is False
    ttl = row.expires_at - datetime.now(UTC)
    assert timedelta(days=89) < ttl <= timedelta(days=90)  # 90d, NOT 365
    assert registered["user_id"] == str(row.user_id)


@pytest.mark.anyio
async def test_login_sets_httponly_strict_cookie(app: Any, session: FakeSession) -> None:
    async with _client(app) as client:
        await _register(client)
        response = await client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )

    assert response.status_code == 200, response.text
    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "local_session=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=strict" in set_cookie
    assert "secure" not in set_cookie  # documented localhost exception
    assert "max-age=7776000" in set_cookie  # 90 days, not 365

    token = _cookie_value(response)
    assert token is not None
    payload = TokenService().decode_token(token)
    assert payload.token_type == "session"
    UUID(str(payload.jti))
    assert payload.sub == response.json()["user_id"]


# ─── 2. Cookie-only authentication works (no Bearer) ───────────────────────


@pytest.mark.anyio
async def test_cookie_only_auth_successfully_creates_redline(
    app: Any, session: FakeSession
) -> None:
    base, comparison = _add_document_versions(session)
    async with _client(app) as client:
        registered = await _register(client)

        created = await client.post(
            "/api/v1/redlines/",
            json={
                "matter_id": registered["matter_number"],
                "base_document_id": str(base.id),
                "comparison_document_id": str(comparison.id),
                "deterministic_seed": 42,
            },
            headers=CSRF_HEADER,  # cookie-authed mutation
        )

    assert created.status_code == 201, created.text
    audits = [row for row in session.of_type(AuditEvent) if row.event_type == "redline_create"]
    assert len(audits) == 1
    user = session.of_type(User)[0]
    assert audits[0].actor_id == user.id
    assert audits[0].actor_email == user.email  # identity snapshot
    assert audits[0].metadata_json["auth"] == "token"  # cookie is a token path


@pytest.mark.anyio
async def test_cookie_mutation_from_same_origin_is_accepted_without_xhr_marker(
    app: Any, session: FakeSession
) -> None:
    """Swagger UI (served from /docs) cannot add custom headers to its
    fetches; the browser-supplied same-origin Origin must satisfy CSRF."""
    base, comparison = _add_document_versions(session)
    async with _client(app) as client:
        registered = await _register(client)
        created = await client.post(
            "/api/v1/redlines/",
            json={
                "matter_id": registered["matter_number"],
                "base_document_id": str(base.id),
                "comparison_document_id": str(comparison.id),
                "deterministic_seed": 42,
            },
            headers={"Origin": "http://test"},  # == client base_url host
        )

    assert created.status_code == 201, created.text
    audits = [row for row in session.of_type(AuditEvent) if row.event_type == "redline_create"]
    assert len(audits) == 1  # attributed to the cookie user, not anonymous


@pytest.mark.anyio
async def test_cookie_mutation_from_cross_site_origin_without_xhr_marker_is_forbidden(
    app: Any, session: FakeSession
) -> None:
    base, comparison = _add_document_versions(session)
    async with _client(app) as client:
        registered = await _register(client)
        response = await client.post(
            "/api/v1/redlines/",
            json={
                "matter_id": registered["matter_number"],
                "base_document_id": str(base.id),
                "comparison_document_id": str(comparison.id),
                "deterministic_seed": 42,
            },
            headers={"Origin": "https://evil.example"},
        )

    assert response.status_code == 403, response.text
    assert "Cookie-authenticated mutations" in response.json()["detail"]
    assert not [r for r in session.of_type(AuditEvent) if r.event_type == "redline_create"]


@pytest.mark.anyio
async def test_cookie_mutation_without_origin_or_xhr_proof_is_forbidden(
    app: Any, session: FakeSession
) -> None:
    """Non-browser clients send no Origin: keep the explicit-marker (or
    Bearer) requirement for them."""
    base, comparison = _add_document_versions(session)
    async with _client(app) as client:
        registered = await _register(client)
        response = await client.post(
            "/api/v1/redlines/",
            json={
                "matter_id": registered["matter_number"],
                "base_document_id": str(base.id),
                "comparison_document_id": str(comparison.id),
                "deterministic_seed": 42,
            },
        )

    assert response.status_code == 403, response.text
    assert "X-Requested-With" in response.json()["detail"]


# ─── 3. Revocation: logout clears cookie + kills session; expired too ──────


@pytest.mark.anyio
async def test_logout_revokes_session_and_clears_cookie(app: Any, session: FakeSession) -> None:
    async with _client(app) as client:
        await _register(client)
        stolen = client.cookies.get(SESSION_COOKIE_NAME)
        assert stolen

        logout = await client.post("/api/v1/auth/logout", headers=CSRF_HEADER)
        assert logout.status_code == 200, logout.text
        cleared = SimpleCookie(logout.headers.get("set-cookie", ""))[SESSION_COOKIE_NAME]
        assert cleared.value == ""
        assert cleared["max-age"] in (0, "0")  # browser-side removal
        assert "httponly" in logout.headers.get("set-cookie", "").lower()
        assert not client.cookies.get(SESSION_COOKIE_NAME)

        # Server-side: reusing the old cookie value fails after logout.
        reuse = await client.post(
            "/api/v1/redlines/",
            json={
                "matter_id": "whatever",
                "base_document_id": str(uuid4()),
                "comparison_document_id": str(uuid4()),
                "deterministic_seed": 1,
            },
            headers={**CSRF_HEADER, "Cookie": f"{SESSION_COOKIE_NAME}={stolen}"},
        )

    assert reuse.status_code == 401, reuse.text
    assert reuse.json()["detail"] == "Session revoked"
    assert all(row.revoked for row in session.of_type(Session))


@pytest.mark.anyio
async def test_expired_session_row_is_rejected(app: Any, session: FakeSession) -> None:
    async with _client(app) as client:
        await _register(client)
        for row in session.of_type(Session):
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        response = await client.get("/api/v1/redlines/", params={"matter_id": "matter-1"})

    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Session revoked"


@pytest.mark.anyio
async def test_garbage_cookie_token_returns_401(app: Any) -> None:
    async with _client(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, "not.a.valid.jwt")
        response = await client.get("/api/v1/redlines/", params={"matter_id": "matter-1"})

    assert response.status_code == 401, response.text
    assert "invalid or expired" in response.json()["detail"]


# ─── 4. Unknown jti (valid JWT, no sessions row) is rejected ───────────────


@pytest.mark.anyio
async def test_session_token_without_db_row_is_revoked(app: Any) -> None:
    forged = TokenService().create_session_token(str(uuid4()), str(uuid4()), str(uuid4()))
    async with _client(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, forged)
        response = await client.get("/api/v1/redlines/", params={"matter_id": "matter-1"})

    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Session revoked"


@pytest.mark.anyio
async def test_openapi_lists_logout_endpoint(app: Any) -> None:
    async with _client(app) as client:
        spec = (await client.get("/openapi.json")).json()

    assert "/api/v1/auth/logout" in spec["paths"]
    assert "post" in spec["paths"]["/api/v1/auth/logout"]
