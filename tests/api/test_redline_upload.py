from __future__ import annotations

import io
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from docx import Document as DocxDocument
from httpx import ASGITransport
from httpx import AsyncClient
from reportlab.pdfgen import canvas

from app.api.dependencies.db import get_db
from app.core.security.tokens import TokenService
from app.db.models import Document
from app.db.models import DocumentSegment
from app.db.models import DocumentVersion
from app.db.models import MatterMemberRole
from app.db.models import RedlineJob
from app.infrastructure.documents.extraction import MAX_UPLOAD_BYTES
from app.main import create_app

if TYPE_CHECKING:
    from collections.abc import Sequence

MATTER_ID = UUID("11111111-1111-1111-1111-111111111111")
USER_ID = UUID("22222222-2222-2222-2222-222222222222")

BASE_LINES = [
    "Payment is due within 30 days of invoice receipt.",
    "Supplier liability is capped at direct damages.",
]
COMPARISON_PARAGRAPHS = [
    "Payment is due within 45 days of invoice receipt.",
    "Supplier liability covers direct damages and reasonable attorney fees.",
]


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.first.return_value = value
    return result


def _fake_session() -> AsyncMock:
    """Matter/user lookups succeed with an EDITOR membership; nothing else
    touches the database in the upload flow (rows only go through add())."""
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_result(
                SimpleNamespace(
                    id=MATTER_ID,
                    members=[SimpleNamespace(user_id=USER_ID, role=MatterMemberRole.EDITOR)],
                )
            ),
            _scalar_result(SimpleNamespace(id=USER_ID, display_name="test-user-1")),
        ]
    )
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _client_with(session: AsyncMock) -> AsyncClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _auth_headers() -> dict[str, str]:
    token = TokenService().create_access_token("test-user-1", "org-1")
    return {"Authorization": f"Bearer {token}"}


def _docx_bytes(paragraphs: Sequence[str]) -> bytes:
    document = DocxDocument()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _pdf_bytes(lines: Sequence[str]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setFont("Helvetica", 12)
    y_position = 720
    for line in lines:
        pdf.drawString(72, y_position, line)
        y_position -= 16
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _upload_files(
    base: tuple[str, bytes, str] = (
        "base_agreement.pdf",
        _pdf_bytes(BASE_LINES),
        "application/pdf",
    ),
    comparison: tuple[str, bytes, str] = (
        "comparison_agreement.docx",
        _docx_bytes(COMPARISON_PARAGRAPHS),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
) -> dict[str, tuple[str, bytes, str]]:
    return {"base_file": base, "comparison_file": comparison}


def _added_objects(session: AsyncMock) -> list[object]:
    return [call.args[0] for call in session.add.call_args_list]


def _added_of(session: AsyncMock, model: type) -> list[object]:
    return [obj for obj in _added_objects(session) if isinstance(obj, model)]


@pytest.mark.anyio
async def test_upload_pdf_and_docx_creates_job_and_persists_versions() -> None:
    session = _fake_session()

    async with _client_with(session) as client:
        response = await client.post(
            "/api/v1/redlines/upload",
            files=_upload_files(),
            data={"matter_id": "matter-1"},
            headers=_auth_headers(),
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert UUID(body["id"])
    assert body["status"] == "pending"
    assert body["changes"] == []

    job = _added_of(session, RedlineJob)
    assert len(job) == 1
    documents = _added_of(session, Document)
    versions = _added_of(session, DocumentVersion)
    segments = _added_of(session, DocumentSegment)
    assert len(documents) == 2
    assert len(versions) == 2
    assert len(segments) >= 2
    assert str(job[0].matter_id) == str(MATTER_ID)
    assert job[0].base_document_version_id == versions[0].id
    assert job[0].comparison_document_version_id == versions[1].id
    assert {version.document_id for version in versions} == {document.id for document in documents}


@pytest.mark.anyio
async def test_upload_persists_filenames_source_ids_and_extracted_text() -> None:
    session = _fake_session()

    async with _client_with(session) as client:
        response = await client.post(
            "/api/v1/redlines/upload",
            files=_upload_files(),
            data={"matter_id": "matter-1", "deterministic_seed": "7", "title": "Supplier Review"},
            headers=_auth_headers(),
        )

    assert response.status_code == 201, response.text
    job = _added_of(session, RedlineJob)[0]
    assert job.configuration == {
        "deterministic_seed": 7,
        "base_source_id": "base_agreement",
        "comparison_source_id": "comparison_agreement",
    }

    documents = {doc.source_filename: doc for doc in _added_of(session, Document)}
    assert set(documents) == {"base_agreement.pdf", "comparison_agreement.docx"}
    assert documents["base_agreement.pdf"].title == "Supplier Review"
    assert documents["base_agreement.pdf"].matter_id == MATTER_ID
    assert documents["base_agreement.pdf"].mime_type == "application/pdf"
    assert len(documents["comparison_agreement.docx"].sha256_hash) == 64

    versions = _added_of(session, DocumentVersion)
    segments = _added_of(session, DocumentSegment)
    base_texts = [
        segment.text
        for segment in segments
        if segment.document_version_id == versions[0].id
    ]
    assert any("Payment is due within 30 days" in text for text in base_texts)
    comparison_texts = [
        segment.text
        for segment in segments
        if segment.document_version_id == versions[1].id
    ]
    assert any("45 days" in text for text in comparison_texts)
    assert all(len(segment.content_hash) == 64 for segment in segments)


@pytest.mark.anyio
async def test_upload_unsupported_format_returns_422_and_persists_nothing() -> None:
    session = _fake_session()

    async with _client_with(session) as client:
        response = await client.post(
            "/api/v1/redlines/upload",
            files=_upload_files(
                base=("budget.xlsx", b"PK\x03\x04fake-spreadsheet", "application/vnd.ms-excel"),
            ),
            data={"matter_id": "matter-1"},
            headers=_auth_headers(),
        )

    assert response.status_code == 422, response.text
    assert "Unsupported file format" in response.json()["detail"]
    assert _added_objects(session) == []


@pytest.mark.anyio
async def test_upload_empty_extraction_returns_422() -> None:
    session = _fake_session()

    async with _client_with(session) as client:
        response = await client.post(
            "/api/v1/redlines/upload",
            files=_upload_files(base=("scan.pdf", _pdf_bytes([]), "application/pdf")),
            data={"matter_id": "matter-1"},
            headers=_auth_headers(),
        )

    assert response.status_code == 422, response.text
    assert "No extractable text" in response.json()["detail"]
    assert _added_objects(session) == []


@pytest.mark.anyio
async def test_upload_oversized_file_returns_413() -> None:
    session = _fake_session()
    payload = b"x" * (MAX_UPLOAD_BYTES + 1)

    async with _client_with(session) as client:
        response = await client.post(
            "/api/v1/redlines/upload",
            files=_upload_files(base=("huge.txt", payload, "text/plain")),
            data={"matter_id": "matter-1"},
            headers=_auth_headers(),
        )

    assert response.status_code == 413, response.text
    assert "exceeds maximum" in response.json()["detail"]
    assert _added_objects(session) == []


@pytest.mark.anyio
async def test_upload_without_auth_returns_401() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/redlines/upload",
            files=_upload_files(),
            data={"matter_id": "matter-1"},
        )

    assert response.status_code == 401, response.text
