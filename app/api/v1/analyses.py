from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter
from pydantic import BaseModel

from app.application.exceptions.processing import ProcessingError
from app.application.mappers.analysis import DefaultAnalysisMapper
from app.application.services.analysis_service import AnalysisApplicationService
from app.domain.analysis.entities import LegalAnalysis
from app.domain.analysis.enums import AnalysisType
from app.domain.meeting.entities import Meeting
from app.domain.meeting.entities import TranscriptSegment
from app.domain.meeting.enums import MeetingSource
from app.domain.meeting.value_objects import MeetingTitle
from app.infrastructure.llm import OllamaAnalysisGeneration
from app.infrastructure.llm import RuleBasedAnalysisGeneration
from app.infrastructure.retrieval import NoOpRetrieval

if TYPE_CHECKING:
    from app.application.dtos.responses.analysis_responses import AnalysisResponse

router = APIRouter(tags=["Analysis"])


class AnalyzeRequest(BaseModel):
    text: str
    use_llm: bool = True
    model: str | None = None


class AnalyzeJobResponse(BaseModel):
    analysis_id: str
    job_id: str
    status: str


@router.post("/analyze", response_model=None)
async def analyze(request: AnalyzeRequest) -> AnalysisResponse:
    """Analyze meeting text and return structured legal findings.

    When *use_llm* is ``True`` (default), the endpoint attempts to call the
    local Ollama server.  If Ollama is unreachable or the model is missing, it
    falls back to a lightweight rule-based scanner so the API always returns a
    usable 200 response.

    Set *use_llm* to ``False`` to force the rule-based path.
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

    service = AnalysisApplicationService(
        retrieval=NoOpRetrieval(),
        generation=generation,
    )

    try:
        await service.execute(analysis, meeting)
    except ProcessingError:
        if not request.use_llm:
            raise
        # Ollama failed — fallback to rule-based so the user still gets 200
        fallback = AnalysisApplicationService(
            retrieval=NoOpRetrieval(),
            generation=RuleBasedAnalysisGeneration(),
        )
        analysis = LegalAnalysis(AnalysisType.FULL_MEETING)
        await fallback.execute(analysis, meeting)

    mapper = DefaultAnalysisMapper()
    return mapper.to_response(analysis)
