from __future__ import annotations

from typing import Any
from uuid import UUID
from uuid import uuid4

import pytest
from httpx import ASGITransport
from httpx import AsyncClient

from app.api.dependencies.db import get_db
from app.core.security.tokens import TokenService
from app.db.models import AuditEvent
from app.db.models import Document
from app.db.models import DocumentClassification
from app.db.models import DocumentType
from app.db.models import DocumentVersion
from app.db.models import Matter
from app.db.models import MatterClassification
from app.db.models import MatterMember
from app.db.models import MatterMemberRole
from app.db.models import MatterStatus
from app.db.models import ProcessingStatus
from app.db.models import RedlineChange
from app.db.models import RedlineJob
from app.db.models import User
from app.main import create_app

ORG_ID = UUID("aaaaaaaa-0000-0000-0000-000000000001")
OWNER_ID = UUID("aaaaaaaa-0000-0000-0000-000000000002")
EDITOR_ID = UUID("aaaaaaaa-0000-0000-0000-000000000003")


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
    from sqlalchemy import BinaryExpression

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
    """In-memory session double with hash-chain-aware audit lookups.

    Mirrors the tests/api/test_auth_flow.py FakeSession, plus: (a) the
    ``sessions`` table's different primary key name, and (b) the audit-chain
    head lookup (SELECT ... ORDER BY seq DESC LIMIT 1 → scalars().first())
    returning the row with the *greatest* seq, as a real database would.
    """

    def __init__(self) -> None:
        self.rows: list[Any] = []

    def add(self, instance: Any) -> None:
        if instance not in self.rows:
            self.rows.append(instance)
        if isinstance(instance, RedlineChange):
            job = self._find(RedlineJob, instance.redline_job_id)
            if job is not None:
                if not isinstance(job.changes, list):
                    job.changes = []
                job.changes.append(instance)

    async def flush(self) -> None:
        return None

    def _find(self, model: type, pk: Any) -> Any:
        for row in self.rows:
            if isinstance(row, model):
                row_id = getattr(row, "id", None)
                if row_id is None:
                    row_id = getattr(row, "session_id", None)
                if row_id == pk:
                    return row
        return None

    async def get(self, model: type, pk: Any, *args: Any, **kwargs: Any) -> Any:
        return self._find(model, pk)

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
            matches.sort(
                key=lambda row: row.seq if row.seq is not None else 0, reverse=True
            )
        return _Result(matches)


def _seeded_session() -> FakeSession:
    session = FakeSession()
    owner = User(
        id=OWNER_ID,
        organization_id=ORG_ID,
        email="owner@example.test",
        display_name="matter-owner",
        hashed_password="not-used",
        is_active=True,
        is_deleted=False,
    )
    editor = User(
        id=EDITOR_ID,
        organization_id=ORG_ID,
        email="editor@example.test",
        display_name="matter-editor",
        hashed_password="not-used",
        is_active=True,
        is_deleted=False,
    )
    matter = Matter(
        id=uuid4(),
        organization_id=ORG_ID,
        name="Supplier negotiation",
        matter_number="matter-1",
        status=MatterStatus.ACTIVE,
        classification=MatterClassification.GENERAL,
    )
    matter.members = [
        MatterMember(matter_id=matter.id, user_id=OWNER_ID, role=MatterMemberRole.OWNER),
        MatterMember(
            matter_id=matter.id, user_id=EDITOR_ID, role=MatterMemberRole.EDITOR
        ),
    ]
    base_document = Document(
        id=uuid4(),
        matter_id=matter.id,
        document_type=DocumentType.CONTRACT,
        title="Base agreement",
        source_filename="base.txt",
        mime_type="text/plain",
        sha256_hash="0" * 64,
        classification=DocumentClassification.INTERNAL,
        created_by_id=OWNER_ID,
    )
    base_version = DocumentVersion(
        id=uuid4(),
        document_id=base_document.id,
        version_number=1,
        object_storage_key="local/base",
        processing_status=ProcessingStatus.COMPLETED,
    )
    base_document.versions = [base_version]
    comparison_document = Document(
        id=uuid4(),
        matter_id=matter.id,
        document_type=DocumentType.CONTRACT,
        title="Comparison agreement",
        source_filename="comparison.txt",
        mime_type="text/plain",
        sha256_hash="1" * 64,
        classification=DocumentClassification.INTERNAL,
        created_by_id=OWNER_ID,
    )
    comparison_version = DocumentVersion(
        id=uuid4(),
        document_id=comparison_document.id,
        version_number=1,
        object_storage_key="local/comparison",
        processing_status=ProcessingStatus.COMPLETED,
    )
    comparison_document.versions = [comparison_version]
    session.add(owner)
    session.add(editor)
    session.add(matter)
    session.add(base_document)
    session.add(base_version)
    session.add(comparison_document)
    session.add(comparison_version)
    session.matter = matter
    session.base_version = base_version
    session.comparison_version = comparison_version
    return session


def _app(session: FakeSession) -> Any:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    return session, app


def _patch_offline_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    """No Ollama/Qdrant in unit tests: embed fast-fails (caught by the
    endpoint's RAG try/except) and generation is stubbed deterministically."""
    from app.application.dtos.internal.redline_generation import GeneratedRedlineChange
    from app.application.dtos.internal.redline_generation import GeneratedRedlineCitation
    from app.application.dtos.internal.redline_generation import RedlineGenerationResult
    from app.infrastructure.llm.ollama_redline import OllamaRedlineGeneration

    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")

    async def fake_generate(self: Any, request: Any) -> RedlineGenerationResult:
        return RedlineGenerationResult(
            changes=(
                GeneratedRedlineChange(
                    clause_path="Clause 4 / Payment terms",
                    change_type="substitution",
                    original_text="Payment is due within 30 days of invoice receipt.",
                    proposed_text="Payment is due within 45 days of invoice receipt.",
                    rationale="Aligns the term with the negotiated schedule.",
                    risk_level="medium",
                    confidence=0.9,
                    citations=(
                        GeneratedRedlineCitation(
                            source_id="BASE document text (part 1)",
                            quote="Payment is due within 30 days of invoice receipt.",
                            page_number=1,
                            start_offset=0,
                            end_offset=48,
                        ),
                    ),
                ),
            )
        )

    monkeypatch.setattr(OllamaRedlineGeneration, "generate", fake_generate)


@pytest.mark.anyio
async def test_full_no_token_flow_create_generate_review(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 1: create → generate → review all succeed with NO token, every
    audit row attributed to the matter owner (default user)."""
    _patch_offline_generation(monkeypatch)
    session, app = _app(_seeded_session())

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/redlines/",
            json={
                "matter_id": "matter-1",
                "base_document_id": str(session.base_version.id),
                "comparison_document_id": str(session.comparison_version.id),
                "deterministic_seed": 42,
            },
        )
        assert created.status_code == 201, created.text
        job_id = created.json()["id"]

        generated = await client.post(
            f"/api/v1/redlines/{job_id}/generate",
            json={
                "base_document_id": str(session.base_version.id),
                "comparison_document_id": str(session.comparison_version.id),
                "deterministic_seed": 42,
            },
        )
        assert generated.status_code == 200, generated.text
        changes = generated.json()["changes"]
        assert len(changes) == 1

        reviewed = await client.post(
            f"/api/v1/redlines/{job_id}/review",
            json={"change_id": changes[0]["id"], "approve": True},
        )
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()["status"] == "reviewed"

        fetched = await client.get(f"/api/v1/redlines/{job_id}")
        assert fetched.status_code == 200, fetched.text

        listed = await client.get("/api/v1/redlines/", params={"matter_id": "matter-1"})
        assert listed.status_code == 200, listed.text
        assert len(listed.json()) == 1

    audits = [row for row in session.rows if isinstance(row, AuditEvent)]
    assert [str(a.event_type) for a in audits] == [
        "redline_create",
        "redline_generate",
        "redline_approve",
    ]
    for audit in audits:
        assert audit.actor_id == OWNER_ID
        assert audit.actor_email == "owner@example.test"
        assert audit.metadata_json["auth"] == "anonymous (default user)"
        assert audit.prev_hash and audit.row_hash
    assert [a.seq for a in audits] == [1, 2, 3]
    assert audits[1].prev_hash == audits[0].row_hash
    assert audits[2].prev_hash == audits[1].row_hash


@pytest.mark.anyio
async def test_tokenless_attribution_falls_back_to_editor_without_owner() -> None:
    """Default user = the member holding EDITOR membership when there is no
    explicit OWNER row."""
    session = _seeded_session()
    session.matter.members = [
        MatterMember(
            matter_id=session.matter.id, user_id=EDITOR_ID, role=MatterMemberRole.EDITOR
        )
    ]
    _, app = _app(session)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/redlines/",
            json={
                "matter_id": "matter-1",
                "base_document_id": str(session.base_version.id),
                "comparison_document_id": str(session.comparison_version.id),
                "deterministic_seed": 42,
            },
        )

    assert created.status_code == 201, created.text
    audits = [row for row in session.rows if isinstance(row, AuditEvent)]
    assert audits[0].actor_id == EDITOR_ID
    assert audits[0].actor_email == "editor@example.test"
    assert audits[0].metadata_json["auth"] == "anonymous (default user)"


@pytest.mark.anyio
async def test_valid_token_still_attributes_to_the_token_user() -> None:
    """Existing behavior: a valid Bearer token wins over the default user."""
    session, app = _app(_seeded_session())
    token = TokenService().create_access_token(str(EDITOR_ID), str(ORG_ID))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/redlines/",
            json={
                "matter_id": "matter-1",
                "base_document_id": str(session.base_version.id),
                "comparison_document_id": str(session.comparison_version.id),
                "deterministic_seed": 42,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert created.status_code == 201, created.text
    audits = [row for row in session.rows if isinstance(row, AuditEvent)]
    assert audits[0].actor_id == EDITOR_ID
    assert audits[0].actor_email == "editor@example.test"
    assert audits[0].metadata_json["auth"] == "token"


@pytest.mark.anyio
async def test_token_user_without_membership_is_still_forbidden() -> None:
    """Hardening kept: a *valid* token for a non-member is a real 403
    (anonymous requests are the only ones routed to the default user)."""
    session, app = _app(_seeded_session())
    outsider = User(
        id=uuid4(),
        organization_id=ORG_ID,
        email="outsider@example.test",
        display_name="outsider",
        hashed_password="not-used",
        is_active=True,
        is_deleted=False,
    )
    session.add(outsider)
    token = TokenService().create_access_token(str(outsider.id), str(ORG_ID))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/redlines/",
            json={
                "matter_id": "matter-1",
                "base_document_id": str(session.base_version.id),
                "comparison_document_id": str(session.comparison_version.id),
                "deterministic_seed": 42,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert created.status_code == 403, created.text


@pytest.mark.anyio
async def test_tokenless_matter_without_any_member_is_not_an_auth_error() -> None:
    """No token and no default user → 409 (never 401/403)."""
    session, app = _app(_seeded_session())
    session.matter.members = []

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/redlines/",
            json={
                "matter_id": "matter-1",
                "base_document_id": str(session.base_version.id),
                "comparison_document_id": str(session.comparison_version.id),
                "deterministic_seed": 42,
            },
        )

    assert created.status_code == 409, created.text
