from __future__ import annotations

from datetime import UTC
from datetime import datetime
from unittest.mock import AsyncMock
from uuid import UUID
from uuid import uuid4

import pytest
from httpx import ASGITransport
from httpx import AsyncClient

from app.api.dependencies.db import get_db
from app.db.models import Analysis
from app.db.models import AnalysisItem
from app.db.models import AnalysisStatus
from app.db.models import AnalysisType
from app.db.models import Citation
from app.db.models import ItemType
from app.main import create_app

ANALYSIS_ID = UUID("33333333-3333-3333-3333-333333333333")
TRANSCRIPT_SOURCE_ID = uuid4()


def _sample_analysis() -> Analysis:
    """Same shape as the seeded model fixtures in tests/test_models.py."""
    analysis = Analysis(
        id=ANALYSIS_ID,
        matter_id=uuid4(),
        analysis_type=AnalysisType.FULL_MEETING,
        status=AnalysisStatus.COMPLETED,
        result_metadata={
            "summary": (
                "The parties negotiated an indemnity cap of twenty percent of the "
                "purchase price, subject to counsel review."
            )
        },
    )
    risk = AnalysisItem(
        item_type=ItemType.RISK,
        title="Uncapped consequential damages",
        description="Clause 8.2 may expose the client to consequential damages.",
        severity="high",
        confidence_score=0.87,
    )
    risk.citations = [
        Citation(
            source_type="meeting_transcript",
            source_id=str(TRANSCRIPT_SOURCE_ID),
            quoted_text="we accept a cap of twenty percent of the price",
        ),
        Citation(
            source_type="corpus_document",
            source_id="contract-1",
            quoted_text="Liability shall not exceed the Fees paid under this Agreement.",
            page_number=12,
        ),
    ]
    obligation = AnalysisItem(
        item_type=ItemType.OBLIGATION,
        title="Deliver signed addendum",
        description="Supplier must deliver the signed addendum to all buyers.",
        responsible_party="Supplier",
        due_date=datetime(2026, 10, 1, tzinfo=UTC),
        confidence_score=0.91,
    )
    obligation.citations = [
        Citation(
            source_type="meeting_transcript",
            source_id=str(TRANSCRIPT_SOURCE_ID),
            quoted_text="the supplier will send the addendum by October first",
        )
    ]
    task = AnalysisItem(
        item_type=ItemType.TASK,
        title="Circulate meeting minutes",
        description="Send minutes to all attendees for approval.",
        responsible_party="Counsel",
        confidence_score=0.99,
    )
    analysis.items = [risk, obligation, task]
    return analysis


def _fake_session(analysis: Analysis | None) -> AsyncMock:
    session = AsyncMock()

    async def fake_get(model: type, pk: object, *args: object, **kwargs: object) -> object:
        if model is Analysis and analysis is not None and pk == analysis.id:
            return analysis
        return None

    session.get = AsyncMock(side_effect=fake_get)
    return session


async def _get_report(analysis: Analysis | None, path_id: UUID):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: _fake_session(analysis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(f"/api/v1/analyses/{path_id}/report")


@pytest.mark.anyio
async def test_analysis_report_returns_pdf_attachment() -> None:
    response = await _get_report(_sample_analysis(), ANALYSIS_ID)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'attachment; filename="analysis-report.pdf"'
    assert response.content[:4] == b"%PDF"
    assert len(response.content) > 1000


@pytest.mark.anyio
async def test_analysis_report_unknown_id_returns_404() -> None:
    response = await _get_report(_sample_analysis(), uuid4())

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
