from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 -- FastAPI evaluates path annotations at runtime

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Path
from fastapi import Response
from fastapi import status
from pydantic import BaseModel

from app.api.dependencies.audit import get_audit_dispatcher
from app.api.dependencies.db import get_db
from app.application.exceptions.processing import ProcessingError
from app.application.mappers.analysis import DefaultAnalysisMapper
from app.application.services.analysis_service import AnalysisApplicationService
from app.core.config import get_settings
from app.db.models.analysis import Analysis
from app.domain.analysis.entities import LegalAnalysis
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

    mapper = DefaultAnalysisMapper()
    return mapper.to_response(analysis)


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
