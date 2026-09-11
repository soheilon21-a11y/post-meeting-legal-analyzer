from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import time
from typing import TYPE_CHECKING
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Path
from fastapi import Response
from fastapi import status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.dependencies.audit import get_audit_dispatcher
from app.api.dependencies.db import get_db
from app.application.exceptions.processing import ProcessingError
from app.application.mappers.analysis import DefaultAnalysisMapper
from app.application.services.analysis_service import AnalysisApplicationService
from app.core.config import get_settings
from app.db.models.analysis import Analysis
from app.db.models.analysis import AnalysisItem
from app.db.models.analysis import AnalysisStatus as OrmAnalysisStatus
from app.db.models.analysis import AnalysisType as OrmAnalysisType
from app.db.models.analysis import Citation as CitationRecord
from app.db.models.analysis import ItemType
from app.db.models.matter import Matter
from app.domain.analysis.entities import Citation as DomainCitation
from app.domain.analysis.entities import Deadline
from app.domain.analysis.entities import LegalAnalysis
from app.domain.analysis.entities import Obligation
from app.domain.analysis.entities import Risk
from app.domain.analysis.enums import AnalysisStatus as DomainAnalysisStatus
from app.domain.analysis.enums import AnalysisType
from app.domain.meeting.entities import Meeting
from app.domain.meeting.entities import TranscriptSegment
from app.domain.meeting.enums import MeetingSource
from app.domain.meeting.value_objects import MeetingTitle
from app.infrastructure.embeddings import OllamaEmbeddings
from app.infrastructure.llm import OllamaAnalysisGeneration
from app.infrastructure.llm import RuleBasedAnalysisGeneration
from app.infrastructure.reporting.analysis_report_pdf import render_analysis_report_pdf
from app.infrastructure.retrieval import EmbeddedRetrieval
from app.infrastructure.retrieval import NoOpRetrieval
from app.infrastructure.retrieval import QdrantVectorIndex

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.application.dtos.responses.analysis_responses import AnalysisResponse
    from app.application.ports.rag_retrieval import RetrievalPort
    from app.domain.ports.event_dispatcher import EventDispatcher

router = APIRouter(tags=["Analysis"])

_DOMAIN_TO_ORM_ANALYSIS_STATUS: dict[str, OrmAnalysisStatus] = {
    DomainAnalysisStatus.DRAFT.value: OrmAnalysisStatus.PENDING,
    DomainAnalysisStatus.PROCESSING.value: OrmAnalysisStatus.PROCESSING,
    DomainAnalysisStatus.READY_FOR_REVIEW.value: OrmAnalysisStatus.COMPLETED,
    DomainAnalysisStatus.APPROVED.value: OrmAnalysisStatus.APPROVED,
    DomainAnalysisStatus.REJECTED.value: OrmAnalysisStatus.REJECTED,
}

_TRANSCRIPT_SOURCE_ID = "transcript"


def _build_retrieval(matter_id: str | None) -> RetrievalPort:
    """Return RAG retrieval when a matter scope is provided, else a no-op.

    Retrieval degrades gracefully to empty evidence if the embedding model
    or vector index is unavailable, so analysis remains usable.
    """
    if matter_id is None:
        return NoOpRetrieval()
    settings = get_settings()
    return EmbeddedRetrieval(
        embeddings=OllamaEmbeddings(),
        index=QdrantVectorIndex.from_settings(),
        score_threshold=settings.ai.vector_similarity_threshold,
    )


class AnalyzeRequest(BaseModel):
    text: str
    use_llm: bool = True
    model: str | None = None
    matter_id: str | None = None


class AnalyzeJobResponse(BaseModel):
    analysis_id: str
    job_id: str
    status: str


@router.post("/analyze", response_model=None)
async def analyze(
    request: AnalyzeRequest,
    event_dispatcher: EventDispatcher | None = Depends(get_audit_dispatcher),
    session: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    """Analyze meeting text and return structured legal findings.

    When *use_llm* is ``True`` (default), the endpoint attempts to call the
    local Ollama server.  If Ollama is unreachable or the model is missing, it
    falls back to a lightweight rule-based scanner so the API always returns a
    usable 200 response.

    Set *use_llm* to ``False`` to force the rule-based path.

    When *matter_id* is supplied, the transcript is grounded against that
    matter's indexed corpus via local RAG retrieval; retrieved evidence is
    passed to the model alongside the transcript.  Without *matter_id*, no
    retrieval is performed.

    When *matter_id* resolves to an existing matter (UUID or matter_number),
    the finished analysis is persisted as an ``Analysis`` row (plus
    ``AnalysisItem``/``Citation`` rows) under the same id the response
    returns, so ``GET /analyses/{id}/report`` can serve it.  Persistence
    requires a matter because ``analyses.matter_id`` is a non-nullable FK;
    matter-less analyses stay in-memory only.  ``get_db`` commits on
    success and rolls back on error.
    """
    meeting = Meeting(
        MeetingTitle("Analysis"),
        datetime.now(UTC),
        MeetingSource.TEXT,
    )
    meeting.add_transcript_segment(TranscriptSegment(1, request.text))
    meeting.complete_transcription()

    analysis = LegalAnalysis(AnalysisType.FULL_MEETING)

    generation: OllamaAnalysisGeneration | RuleBasedAnalysisGeneration
    if request.use_llm:
        generation = OllamaAnalysisGeneration(model_name=request.model)
    else:
        generation = RuleBasedAnalysisGeneration()

    retrieval = _build_retrieval(request.matter_id)

    service = AnalysisApplicationService(
        retrieval=retrieval,
        generation=generation,
        matter_id=request.matter_id,
        event_dispatcher=event_dispatcher,
    )

    try:
        await service.execute(analysis, meeting)
    except ProcessingError:
        if not request.use_llm:
            raise
        # Ollama failed — fallback to rule-based so the user still gets 200
        fallback = AnalysisApplicationService(
            retrieval=retrieval,
            generation=RuleBasedAnalysisGeneration(),
            matter_id=request.matter_id,
            event_dispatcher=event_dispatcher,
        )
        analysis = LegalAnalysis(AnalysisType.FULL_MEETING)
        await fallback.execute(analysis, meeting)

    await _persist_if_matter_known(session, analysis, request)

    mapper = DefaultAnalysisMapper()
    return mapper.to_response(analysis)


async def _resolve_matter_for_analysis(
    session: AsyncSession,
    raw: str,
) -> Matter | None:
    """Look up a matter by UUID or matter_number; None when unknown."""
    try:
        matter_id = UUID(raw)
    except ValueError:
        result = await session.execute(select(Matter).where(Matter.matter_number == raw))
        return result.scalars().first()
    return await session.get(Matter, matter_id)


async def _persist_if_matter_known(
    session: AsyncSession,
    analysis: LegalAnalysis,
    request: AnalyzeRequest,
) -> None:
    """Persist the domain analysis as ORM rows when a matter context exists.

    ``analyses.matter_id`` is a non-nullable FK, so analyses requested without
    a (resolvable) matter cannot be stored; they keep the previous in-memory
    behavior instead of failing the request.
    """
    if request.matter_id is None:
        return
    matter = await _resolve_matter_for_analysis(session, request.matter_id)
    if matter is None:
        return
    session.add(_analysis_record(analysis, matter_id=matter.id, model_id=request.model))


def _analysis_record(
    analysis: LegalAnalysis,
    *,
    matter_id: UUID,
    model_id: str | None,
) -> Analysis:
    record = Analysis(
        id=analysis.id,
        matter_id=matter_id,
        analysis_type=OrmAnalysisType(analysis.analysis_type.value),
        status=_DOMAIN_TO_ORM_ANALYSIS_STATUS[str(analysis.status)],
        model_id=model_id,
        result_metadata={"summary": analysis.summary} if analysis.summary else None,
    )
    for item in analysis.items:
        record.items.append(_item_record(item, analysis_id=analysis.id))
    return record


def _item_record(item: Any, *, analysis_id: UUID) -> AnalysisItem:
    item_type = ItemType.TASK
    severity: str | None = None
    if isinstance(item, Risk):
        item_type, severity = ItemType.RISK, item.level.value
    elif isinstance(item, Obligation):
        item_type = ItemType.OBLIGATION
    party: Any = getattr(item, "responsible_party", None)
    record = AnalysisItem(
        id=item.id,
        analysis_id=analysis_id,
        item_type=item_type,
        title=item.title,
        description=item.description,
        severity=severity,
        status=item.status.value,
        responsible_party=party.value if party is not None else None,
        due_date=_deadline_to_datetime(item),
        confidence_score=item.confidence.value,
    )
    for citation in item.citations:
        record.citations.append(_citation_record(citation, analysis_id, record.id))
    return record


def _citation_record(citation: DomainCitation, analysis_id: UUID, item_id: UUID) -> CitationRecord:
    location = citation.location
    source_type = (
        "meeting_transcript"
        if location.source_id.strip().lower() == _TRANSCRIPT_SOURCE_ID
        else "corpus_document"
    )
    return CitationRecord(
        id=citation.id,
        analysis_id=analysis_id,
        item_id=item_id,
        source_type=source_type,
        source_id=location.source_id[:255],
        page_number=location.page_number,
        start_offset=location.start_offset,
        end_offset=location.end_offset,
        quoted_text=citation.quote.value,
    )


def _deadline_to_datetime(item: Any) -> datetime | None:
    deadline: Deadline | None = getattr(item, "deadline", None)
    if deadline is None:
        return None
    return datetime.combine(deadline.due_date.value, time.min, tzinfo=UTC)


@router.get(
    "/analyses/{analysis_id}/report",
    response_class=Response,
    summary="Download the analysis result as a PDF report",
)
async def get_analysis_report(
    analysis_id: UUID = Path(..., description="The analysis UUID"),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Render a completed analysis as a professional, downloadable PDF.

    Loads the ``Analysis`` row (with its items and citations) from
    PostgreSQL via the shared ORM models and returns a deliverable-style
    report: summary, risks/obligations/action-item tables, and verbatim
    citation footnotes distinguishing meeting-transcript evidence from
    corpus sources.  Unknown analysis ids yield a 404.
    """
    analysis = await session.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Analysis {analysis_id} not found",
        )
    pdf_bytes = render_analysis_report_pdf(analysis)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="analysis-report.pdf"'},
    )
