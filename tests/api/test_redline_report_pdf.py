from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID
from uuid import uuid4

import pytest
from httpx import ASGITransport
from httpx import AsyncClient

from app.api.dependencies.db import get_db
from app.core.security.tokens import TokenService
from app.db.models import Document
from app.db.models import DocumentClassification
from app.db.models import DocumentType
from app.db.models import DocumentVersion
from app.db.models import ProcessingStatus
from app.db.models import RedlineChange
from app.db.models import RedlineJob
from app.db.models import RedlineStatus
from app.db.models import ReviewStatus
from app.main import create_app

JOB_ID = UUID("44444444-4444-4444-4444-444444444444")
CHANGE_A_ID = UUID("55555555-5555-5555-5555-555555555555")
CHANGE_B_ID = UUID("66666666-6666-6666-6666-666666666666")


def _linked_version(document_title: str, filename: str) -> DocumentVersion:
    document = Document(
        id=uuid4(),
        matter_id=uuid4(),
        document_type=DocumentType.CONTRACT,
        title=document_title,
        source_filename=filename,
        mime_type="application/pdf",
        sha256_hash="0" * 64,
        classification=DocumentClassification.INTERNAL,
    )
    version = DocumentVersion(
        id=uuid4(),
        document_id=document.id,
        version_number=1,
        object_storage_key=f"local/uploads/{document.id}/v1",
        page_count=1,
        processing_status=ProcessingStatus.COMPLETED,
    )
    document.versions = [version]
    return version


def _sample_job() -> RedlineJob:
    """A completed redline job with two changes and stored citations."""
    job = RedlineJob(
        id=JOB_ID,
        matter_id=uuid4(),
        base_document_version_id=uuid4(),
        comparison_document_version_id=uuid4(),
        status=RedlineStatus.COMPLETED,
        configuration={"deterministic_seed": 42},
    )
    job.base_version = _linked_version("Supplier Agreement v1", "base_agreement.pdf")
    job.comparison_version = _linked_version("Supplier Agreement v2", "comparison_agreement.docx")
    job.changes = [
        RedlineChange(
            id=CHANGE_A_ID,
            redline_job_id=JOB_ID,
            section_path="Clause 4.1 / Payment terms",
            change_type="substitution",
            original_text="Payment is due within 30 days of invoice receipt.",
            proposed_text="Payment is due within 45 days of invoice receipt.",
            rationale="Aligns the term with the negotiated schedule.",
            risk_level="medium",
            confidence=0.92,
            review_status=ReviewStatus.PENDING,
            source_citations=[
                {
                    "quote": "Payment is due within 30 days of invoice receipt.",
                    "source_id": "BASE document text (part 1)",
                    "page_number": 1,
                    "start_offset": 0,
                    "end_offset": 48,
                }
            ],
        ),
        RedlineChange(
            id=CHANGE_B_ID,
            redline_job_id=JOB_ID,
            section_path="Clause 8.2 / Limitation of liability",
            change_type="scope_expansion",
            original_text="Supplier liability is capped at direct damages.",
            proposed_text="Supplier liability covers direct damages and fees.",
            rationale="Reflects the agreed expansion of recoverable costs.",
            risk_level="high",
            confidence=0.81,
            review_status=ReviewStatus.APPROVED,
            source_citations=[
                {
                    "quote": "Supplier liability is capped at direct damages.",
                    "source_id": "comparison_agreement",
                    "page_number": 2,
                }
            ],
        ),
    ]
    return job


def _empty_job() -> RedlineJob:
    """A pending job without changes or linked document versions."""
    return RedlineJob(
        id=uuid4(),
        matter_id=uuid4(),
        base_document_version_id=uuid4(),
        comparison_document_version_id=uuid4(),
        status=RedlineStatus.PENDING,
        configuration=None,
    )


def _fake_session(job: RedlineJob | None) -> AsyncMock:
    session = AsyncMock()

    async def fake_get(model: type, pk: object, *args: object, **kwargs: object) -> object:
        if model is RedlineJob and job is not None and pk == job.id:
            return job
        return None

    session.get = AsyncMock(side_effect=fake_get)
    return session


async def _get_report(job: RedlineJob | None, path_id: UUID, *, auth: bool = True):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: _fake_session(job)
    headers = {}
    if auth:
        token = TokenService().create_access_token(str(uuid4()), str(uuid4()))
        headers["Authorization"] = f"Bearer {token}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(f"/api/v1/redlines/{path_id}/report", headers=headers)


@pytest.mark.anyio
async def test_redline_report_returns_pdf_with_change_ids() -> None:
    response = await _get_report(_sample_job(), JOB_ID)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'attachment; filename="redline-report.pdf"'
    assert response.content[:4] == b"%PDF"
    assert len(response.content) > 1000
    assert str(CHANGE_A_ID).encode() in response.content
    assert str(CHANGE_B_ID).encode() in response.content


@pytest.mark.anyio
async def test_redline_report_handles_job_without_changes() -> None:
    job = _empty_job()
    response = await _get_report(job, job.id)

    assert response.status_code == 200, response.text
    assert response.content[:4] == b"%PDF"


@pytest.mark.anyio
async def test_redline_report_unknown_id_returns_404() -> None:
    response = await _get_report(_sample_job(), uuid4())

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.anyio
async def test_redline_report_without_auth_returns_401() -> None:
    response = await _get_report(_sample_job(), JOB_ID, auth=False)

    assert response.status_code == 401, response.text
    assert response.json()["status"] == 401
