from __future__ import annotations

from typing import Any
from uuid import UUID
from uuid import uuid4

import pytest
from httpx import ASGITransport
from httpx import AsyncClient
from sqlalchemy import BinaryExpression

from app.api.dependencies.db import get_db
from app.core.security.tokens import TokenService
from app.db.models import AuditEvent
from app.db.models import DocumentVersion
from app.db.models import Matter
from app.db.models import MatterMember
from app.db.models import Organization
from app.db.models import ProcessingStatus
from app.db.models import User
from app.main import create_app

EMAIL = "attorney@example.com"
PASSWORD = "Str0ng-Passw0rd!"


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
    """Collect ``column == literal`` conditions from a WHERE clause."""
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
    """Tiny in-memory stand-in serving real select()/get() lookups.

    One instance spans the whole register → login → redline flow, so rows
    created by one request are visible to the next — the same
    session-per-request semantics as get_db, without needing PostgreSQL.
    """

    def __init__(self) -> None:
        self.rows: list[Any] = []

    def add(self, instance: Any) -> None:
        self.rows.append(instance)

    def add_all(self, instances: Any) -> None:
        self.rows.extend(instances)

    async def flush(self) -> None:
        return None

    async def get(self, model: type, pk: Any, *args: Any, **kwargs: Any) -> Any:
        for row in self.rows:
            if isinstance(row, model) and getattr(row, "id", None) == pk:
                return row
        return None

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> _Result:
        entity = statement.column_descriptions[0]["entity"]
        conditions = _eq_conditions(statement.whereclause)
        matches = [
            row
            for row in self.rows
            if isinstance(row, entity)
            and all(getattr(row, key, None) == value for key, value in conditions.items())
        ]
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


async def _register(client: AsyncClient, **overrides: Any) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "display_name": "Test Attorney",
            "organization_name": "Test Firm",
            **overrides,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.anyio
async def test_register_then_login_then_use_token_on_redline(
    app: Any, session: FakeSession
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        registered = await _register(client)

        assert UUID(registered["user_id"])
        assert UUID(registered["organization_id"])
        assert registered["matter_number"]
        assert registered["token_type"] == "bearer"
        payload = TokenService().decode_token(registered["access_token"])
        assert payload.sub == registered["user_id"]
        assert payload.org_id == registered["organization_id"]
        assert payload.token_type == "access"
        refresh_payload = TokenService().decode_token(registered["refresh_token"])
        assert refresh_payload.token_type == "refresh"
        assert refresh_payload.exp > payload.exp  # longer-lived refresh token

        logged_in = await client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )
        assert logged_in.status_code == 200, logged_in.text
        token = logged_in.json()["access_token"]

        # The token minted via login (Swagger-friendly) works on protected
        # endpoints through the standard Authorization header.
        base_version = DocumentVersion(
            id=uuid4(),
            document_id=uuid4(),
            version_number=1,
            object_storage_key="local/base",
            processing_status=ProcessingStatus.COMPLETED,
        )
        comparison_version = DocumentVersion(
            id=uuid4(),
            document_id=uuid4(),
            version_number=1,
            object_storage_key="local/comparison",
            processing_status=ProcessingStatus.COMPLETED,
        )
        session.add(base_version)
        session.add(comparison_version)

        created = await client.post(
            "/api/v1/redlines/",
            json={
                "matter_id": registered["matter_number"],
                "base_document_id": str(base_version.id),
                "comparison_document_id": str(comparison_version.id),
                "deterministic_seed": 42,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert created.status_code == 201, created.text
    body = created.json()
    assert UUID(body["id"])
    assert body["status"] == "pending"


@pytest.mark.anyio
async def test_register_persists_hashed_password_membership_and_audit(
    app: Any, session: FakeSession
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        registered = await _register(client)

    users = session.of_type(User)
    orgs = session.of_type(Organization)
    matters = session.of_type(Matter)
    members = session.of_type(MatterMember)
    audits = session.of_type(AuditEvent)

    assert [u.id for u in users] == [UUID(registered["user_id"])]
    assert [o.name for o in orgs] == ["Test Firm"]
    assert len(matters) == 1 and matters[0].id == UUID(registered["matter_id"])
    assert [m.role.value for m in members] == ["editor"]
    assert members[0].user_id == users[0].id
    assert members[0].matter_id == matters[0].id
    assert [a.event_type for a in audits] == ["auth.registered"]

    # Stored only as a passlib hash; never returned in any response body.
    assert users[0].hashed_password != PASSWORD
    assert users[0].hashed_password.startswith(("$2", "$argon2"))
    assert PASSWORD not in str(registered)
    assert users[0].organization_id == orgs[0].id
    assert matters[0].organization_id == orgs[0].id


@pytest.mark.anyio
async def test_login_wrong_password_returns_401_and_audits_failure(
    app: Any, session: FakeSession
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register(client)
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": EMAIL, "password": "totally-wrong-password"},
        )

    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Invalid email or password"
    failures = [
        event
        for event in session.of_type(AuditEvent)
        if event.event_type == "auth.login_failed"
    ]
    assert len(failures) == 1
    assert failures[0].actor_id == UUID(failures[0].metadata_json["aggregate_id"])
    assert "totally-wrong-password" not in str(failures[0].metadata_json)
    assert "$2" not in str(failures[0].metadata_json)  # no hash material in audit


@pytest.mark.anyio
async def test_login_unknown_email_returns_401(app: Any) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": PASSWORD},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.anyio
async def test_login_success_carries_request_id_into_audit_metadata(
    app: Any, session: FakeSession
) -> None:
    request_id = "req-trace-me"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register(client)
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
            headers={"X-Request-ID": request_id},
        )

    assert response.status_code == 200, response.text
    assert response.headers["X-Request-ID"] == request_id
    successes = [
        event
        for event in session.of_type(AuditEvent)
        if event.event_type == "auth.login_success"
    ]
    assert len(successes) == 1
    assert successes[0].metadata_json["request_id"] == request_id


@pytest.mark.anyio
async def test_duplicate_email_register_returns_409_without_partial_rows(
    app: Any, session: FakeSession
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register(client)
        rows_after_first = list(session.rows)

        second = await client.post(
            "/api/v1/auth/register",
            json={
                "email": EMAIL,
                "password": "Another-Str0ng-Pass!",
                "display_name": "Impostor",
            },
        )

    assert second.status_code == 409, second.text
    assert "already exists" in second.json()["detail"]
    # No partial rows left behind: the duplicate attempt changed nothing.
    assert session.rows == rows_after_first


@pytest.mark.anyio
async def test_refresh_returns_new_access_token(app: Any) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        registered = await _register(client)
        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": registered["refresh_token"]}
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    payload = TokenService().decode_token(body["access_token"])
    assert payload.token_type == "access"
    assert payload.sub == registered["user_id"]
    assert payload.org_id == registered["organization_id"]


@pytest.mark.anyio
async def test_refresh_rejects_access_token_and_garbage(app: Any) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        registered = await _register(client)

        with_access = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": registered["access_token"]}
        )
        with_garbage = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "not.a.jwt"}
        )

    assert with_access.status_code == 401
    assert with_access.json()["detail"] == "A refresh token is required"
    assert with_garbage.status_code == 401
    assert "invalid or expired" in with_garbage.json()["detail"]


@pytest.mark.anyio
async def test_openapi_declares_httpbearer_scheme_on_protected_endpoints(app: Any) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/openapi.json")

    spec = response.json()
    scheme = spec["components"]["securitySchemes"]["HTTPBearer"]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"

    for path, method in (
        ("/api/v1/redlines/", "post"),
        ("/api/v1/redlines/upload", "post"),
        ("/api/v1/redlines/{redline_id}", "get"),
        ("/api/v1/redlines/{redline_id}/report", "get"),
    ):
        security = spec["paths"][path][method].get("security")
        assert security == [{"HTTPBearer": []}], f"{method.upper()} {path} unprotected"

    # Auth endpoints themselves are public (no security requirement).
    assert spec["paths"]["/api/v1/auth/login"]["post"].get("security") is None
    assert spec["paths"]["/api/v1/auth/register"]["post"].get("security") is None
