from __future__ import annotations

from uuid import UUID

import pytest
from httpx import ASGITransport
from httpx import AsyncClient

from app.api.dependencies.db import get_db
from app.db.models import Analysis
from app.db.models import AnalysisItem
from app.db.models import AnalysisStatus
from app.db.models import Citation
from app.db.models import Matter
from app.main import create_app

MATTER_ID = UUID("44444444-4444-4444-4444-444444444444")

# Matches every rule-based pattern family (risk/obligation/action) so the
# persisted graph has at least one item of each type with a transcript citation.
TRANSCRIPT = (
    "The supplier must deliver the signed addendum before the deadline. "
    "The parties agreed to review the liability cap and will prepare a redline."
)


class _InMemorySession:
    """Minimal AsyncSession stand-in: keeps added rows addressable by get()."""

    def __init__(self) -> None:
        self.rows: dict[tuple[type, object], object] = {}

    def add(self, obj: object) -> None:
        self.rows[(type(obj), obj.id)] = obj  # type: ignore[attr-defined]

    async def get(self, model: type, ident: object, **kwargs: object) -> object | None:
        return self.rows.get((model, ident))


@pytest.mark.anyio
async def test_analyze_persists_rows_and_report_serves_pdf() -> None:
    """End-to-end regression: POST /analyze -> id -> GET report -> 200 %PDF.

    Guards against the bug where /analyze returned an id that was never
    written to PostgreSQL, so the PDF report always 404'd for real analyses.
    """
    session = _InMemorySession()
    session.add(Matter(id=MATTER_ID))

    app = create_app()
    app.dependency_overrides[get_db] = lambda: session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        analysis_response = await client.post(
            "/api/v1/analyze",
            json={"text": TRANSCRIPT, "use_llm": False, "matter_id": str(MATTER_ID)},
        )
        assert analysis_response.status_code == 200, analysis_response.text
        body = analysis_response.json()
        analysis_id = UUID(body["id"])

        report_response = await client.get(f"/api/v1/analyses/{analysis_id}/report")

    # The response id must be the persisted Analysis.id
    stored = session.rows[(Analysis, analysis_id)]
    assert isinstance(stored, Analysis)
    assert stored.id == analysis_id
    assert stored.matter_id == MATTER_ID
    assert stored.status == AnalysisStatus.COMPLETED
    assert (stored.result_metadata or {}).get("summary") == body["summary"]
    assert stored.items, "analysis items must be persisted with their parent row"
    assert all(isinstance(item, AnalysisItem) for item in stored.items)
    assert {str(item.item_type) for item in stored.items} >= {"risk", "obligation", "task"}
    assert any(item.confidence_score is not None for item in stored.items)
    citations = [citation for item in stored.items for citation in item.citations]
    assert citations, "citations must be persisted and linked to items"
    assert all(isinstance(citation, Citation) for citation in citations)
    assert all(citation.quoted_text for citation in citations)
    assert all(citation.item_id is not None for citation in citations)
    assert all(citation.analysis_id == analysis_id for citation in citations)
    assert all(
        citation.source_type == "meeting_transcript" for citation in citations
    ), "rule-based evidence is transcript-sourced"

    # And the report endpoint can serve it back as a PDF
    assert report_response.status_code == 200, report_response.text
    assert report_response.headers["content-type"] == "application/pdf"
    assert report_response.content[:4] == b"%PDF"
    assert len(report_response.content) > 1000


@pytest.mark.anyio
async def test_analyze_without_matter_id_still_works_without_persisting() -> None:
    """No matter context -> no FK target -> response still 200, nothing stored."""
    session = _InMemorySession()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analyze",
            json={"text": TRANSCRIPT, "use_llm": False},
        )

    assert response.status_code == 200, response.text
    assert (Analysis, UUID(response.json()["id"])) not in session.rows
