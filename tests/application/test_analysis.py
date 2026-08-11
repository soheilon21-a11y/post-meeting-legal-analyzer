from __future__ import annotations

from datetime import UTC
from datetime import date
from datetime import datetime
from typing import ClassVar
from uuid import uuid4

import pytest

from app.application.commands.analysis_commands import ApproveAnalysisCommand
from app.application.commands.analysis_commands import ExecuteAnalysisCommand
from app.application.commands.analysis_commands import RequestAnalysisCommand
from app.application.dtos.internal.ai_jobs import AIJobHandle
from app.application.dtos.internal.ai_jobs import AIJobRequest
from app.application.dtos.internal.analysis_generation import AnalysisGenerationInput
from app.application.dtos.internal.analysis_generation import AnalysisGenerationResult
from app.application.dtos.internal.analysis_generation import EvidenceInput
from app.application.dtos.internal.analysis_generation import GeneratedActionItem
from app.application.dtos.internal.analysis_generation import GeneratedObligation
from app.application.dtos.internal.analysis_generation import GeneratedRisk
from app.application.dtos.internal.security import ActorContext
from app.application.handlers.analysis_handlers import AnalysisCommandHandler
from app.application.handlers.analysis_handlers import AnalysisQueryHandler
from app.application.ports.ai_job_orchestration import AIJobOrchestrationPort
from app.application.ports.llm_generation import AnalysisGenerationPort
from app.application.ports.rag_retrieval import RetrievalPort
from app.application.ports.tokenization import ContextWindowPort
from app.application.ports.tokenization import TokenizerPort
from app.application.queries.analysis_queries import GetAnalysisQuery
from app.application.services.analysis_service import AnalysisApplicationService
from app.application.services.context_optimizer import ContextOptimizer
from app.domain.ai.value_objects import ContextWindow
from app.domain.ai.value_objects import TokenCount
from app.domain.analysis.entities import LegalAnalysis
from app.domain.analysis.enums import AnalysisType
from app.domain.matter.entities import Matter
from app.domain.matter.enums import MatterMemberRole
from app.domain.matter.value_objects import MatterName
from app.domain.meeting.entities import Meeting
from app.domain.meeting.entities import TranscriptSegment
from app.domain.meeting.enums import MeetingSource
from app.domain.meeting.value_objects import MeetingTitle
from app.domain.shared.identifiers import AnalysisId
from app.domain.shared.identifiers import MatterId
from app.domain.shared.identifiers import MeetingId
from app.domain.shared.identifiers import OrganizationId
from app.domain.shared.identifiers import UserId


class FakeMatterRepository:
    def __init__(self, matter: Matter) -> None:
        self.matter = matter

    async def get(self, matter_id: MatterId) -> Matter | None:
        return self.matter if matter_id == self.matter.id else None

    async def save(self, matter: Matter) -> None:
        self.matter = matter


class FakeMeetingRepository:
    def __init__(self, meeting: Meeting) -> None:
        self.meeting = meeting

    async def get(self, meeting_id: MeetingId) -> Meeting | None:
        return self.meeting if meeting_id == self.meeting.id else None

    async def get_for_matter(self, matter_id: MatterId, meeting_id: MeetingId) -> Meeting | None:
        return self.meeting if meeting_id == self.meeting.id else None

    async def save(self, meeting: Meeting) -> None:
        self.meeting = meeting


class FakeAnalysisRepository:
    def __init__(self) -> None:
        self.items: dict[AnalysisId, LegalAnalysis] = {}

    async def get(self, analysis_id: AnalysisId) -> LegalAnalysis | None:
        return self.items.get(analysis_id)

    async def get_for_matter(
        self, matter_id: MatterId, analysis_id: AnalysisId
    ) -> LegalAnalysis | None:
        return self.items.get(analysis_id)

    async def save(self, analysis: LegalAnalysis) -> None:
        self.items[analysis.id] = analysis


class FakeAnalysisUnitOfWork:
    def __init__(self, matter: Matter, meeting: Meeting) -> None:
        self.matters = FakeMatterRepository(matter)
        self.meetings = FakeMeetingRepository(meeting)
        self.analyses = FakeAnalysisRepository()
        self.commits = 0

    async def __aenter__(self) -> FakeAnalysisUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


class FakeRetrieval(RetrievalPort):
    async def retrieve(self, matter_id: str, query: str, limit: int) -> tuple[EvidenceInput, ...]:
        return (EvidenceInput("segment-1", "The parties agreed to review liability."),)


class FakeGeneration(AnalysisGenerationPort):
    async def generate(self, request: AnalysisGenerationInput) -> AnalysisGenerationResult:
        evidence = (EvidenceInput("segment-1", "The parties agreed to review liability."),)
        return AnalysisGenerationResult(
            summary="The meeting identified a liability concern.",
            risks=(
                GeneratedRisk(
                    "Liability concern",
                    "Liability wording needs review.",
                    "high",
                    0.9,
                    evidence,
                ),
            ),
            obligations=(
                GeneratedObligation(
                    "Review liability clause",
                    "Counsel must review the liability clause.",
                    "Counsel",
                    0.85,
                    evidence,
                    date(2026, 10, 1),
                ),
            ),
            action_items=(
                GeneratedActionItem(
                    "Prepare revision",
                    "Prepare revised wording.",
                    "Counsel",
                    0.8,
                    evidence,
                ),
            ),
        )


class FakeJobs(AIJobOrchestrationPort):
    def __init__(self) -> None:
        self.running: list[str] = []
        self.completed: list[str] = []
        self.failed: list[str] = []

    async def enqueue(self, request: AIJobRequest) -> AIJobHandle:
        return AIJobHandle()

    async def mark_running(self, job_id: str) -> None:
        self.running.append(job_id)

    async def mark_completed(self, job_id: str) -> None:
        self.completed.append(job_id)

    async def mark_failed(self, job_id: str, reason: str) -> None:
        self.failed.append(job_id)


def _fixture() -> tuple[FakeAnalysisUnitOfWork, ActorContext, Meeting]:
    matter = Matter(MatterName("Matter"))
    actor = ActorContext(user_id=UserId(uuid4()), organization_id=OrganizationId(uuid4()))
    matter.add_member(actor.user_id, MatterMemberRole.OWNER)
    meeting = Meeting(MeetingTitle("Meeting"), datetime.now(UTC), MeetingSource.TEXT)
    meeting.add_transcript_segment(TranscriptSegment(1, "The parties agreed."))
    meeting.complete_transcription()
    return FakeAnalysisUnitOfWork(matter, meeting), actor, meeting


@pytest.mark.anyio
async def test_analysis_request_enqueues_job_and_persists_analysis() -> None:
    uow, actor, meeting = _fixture()
    jobs = FakeJobs()
    handler = AnalysisCommandHandler(
        lambda: uow,
        jobs,
        AnalysisApplicationService(FakeRetrieval(), FakeGeneration()),
    )

    response = await handler.handle(
        RequestAnalysisCommand(
            matter_id=uow.matters.matter.id,
            meeting_id=meeting.id,
            analysis_type=AnalysisType.FULL_MEETING,
            actor=actor,
        )
    )

    assert response.status == "queued"
    assert len(uow.analyses.items) == 1
    assert uow.commits == 1


@pytest.mark.anyio
async def test_analysis_execution_retrieves_generates_and_maps_items() -> None:
    uow, actor, meeting = _fixture()
    analysis = LegalAnalysis(AnalysisType.FULL_MEETING)
    uow.analyses.items[analysis.id] = analysis
    jobs = FakeJobs()
    handler = AnalysisCommandHandler(
        lambda: uow,
        jobs,
        AnalysisApplicationService(FakeRetrieval(), FakeGeneration()),
    )

    response = await handler.handle(
        ExecuteAnalysisCommand(
            matter_id=uow.matters.matter.id,
            meeting_id=meeting.id,
            analysis_id=analysis.id,
            actor=actor,
        )
    )

    assert response.status == "ready_for_review"
    assert len(response.items) == 3
    assert jobs.completed == [str(analysis.id)]


@pytest.mark.anyio
async def test_analysis_can_be_approved_after_execution_and_queried() -> None:
    uow, actor, meeting = _fixture()
    analysis = LegalAnalysis(AnalysisType.FULL_MEETING)
    uow.analyses.items[analysis.id] = analysis
    jobs = FakeJobs()
    service = AnalysisApplicationService(FakeRetrieval(), FakeGeneration())
    handler = AnalysisCommandHandler(lambda: uow, jobs, service)
    await handler.handle(
        ExecuteAnalysisCommand(
            matter_id=uow.matters.matter.id,
            meeting_id=meeting.id,
            analysis_id=analysis.id,
            actor=actor,
        )
    )
    approved = await handler.handle(
        ApproveAnalysisCommand(
            matter_id=uow.matters.matter.id,
            analysis_id=analysis.id,
            actor=actor,
        )
    )
    queried = await AnalysisQueryHandler(lambda: uow).handle(
        GetAnalysisQuery(
            matter_id=uow.matters.matter.id,
            analysis_id=analysis.id,
            actor=actor,
        )
    )

    assert approved.status == "approved"
    assert queried.status == "approved"


@pytest.mark.anyio
async def test_analysis_execution_marks_job_failed_on_generation_error() -> None:
    uow, actor, meeting = _fixture()
    analysis = LegalAnalysis(AnalysisType.FULL_MEETING)
    uow.analyses.items[analysis.id] = analysis
    jobs = FakeJobs()

    class FailingGeneration(FakeGeneration):
        async def generate(self, request: AnalysisGenerationInput) -> AnalysisGenerationResult:
            raise RuntimeError("local generation failed")

    handler = AnalysisCommandHandler(
        lambda: uow,
        jobs,
        AnalysisApplicationService(FakeRetrieval(), FailingGeneration()),
    )

    with pytest.raises(Exception, match="analysis"):
        await handler.handle(
            ExecuteAnalysisCommand(
                matter_id=uow.matters.matter.id,
                meeting_id=meeting.id,
                analysis_id=analysis.id,
                actor=actor,
            )
        )

    assert jobs.failed == [str(analysis.id)]


class _FakeTokenizer(TokenizerPort):
    async def count(self, text: str) -> TokenCount:
        return TokenCount(len(text.split()))

    async def truncate(self, text: str, limit: TokenCount) -> str:
        return " ".join(text.split()[: limit.value])


class _FakeContextWindow(ContextWindowPort):
    def __init__(self, capacity: int = 4096) -> None:
        self._capacity = capacity

    async def capacity(self, model_name: str) -> ContextWindow:
        return ContextWindow(self._capacity)


class _SpyGeneration(AnalysisGenerationPort):
    requests: ClassVar[list[AnalysisGenerationInput]] = []

    async def generate(self, request: AnalysisGenerationInput) -> AnalysisGenerationResult:
        self.requests.append(request)
        evidence = (EvidenceInput("segment-1", "The parties agreed to review liability."),)
        return AnalysisGenerationResult(
            summary="The meeting identified a liability concern.",
            risks=(
                GeneratedRisk(
                    "Liability concern",
                    "Liability wording needs review.",
                    "high",
                    0.9,
                    evidence,
                ),
            ),
            obligations=(
                GeneratedObligation(
                    "Review liability clause",
                    "Counsel must review the liability clause.",
                    "Counsel",
                    0.85,
                    evidence,
                    date(2026, 10, 1),
                ),
            ),
            action_items=(
                GeneratedActionItem(
                    "Prepare revision",
                    "Prepare revised wording.",
                    "Counsel",
                    0.8,
                    evidence,
                ),
            ),
        )


def _optimizer(capacity: int = 4096) -> ContextOptimizer:
    return ContextOptimizer(_FakeTokenizer(), _FakeContextWindow(capacity))


@pytest.mark.anyio
async def test_analysis_with_optimizer_preserves_behavior_when_within_budget() -> None:
    uow, actor, meeting = _fixture()
    analysis = LegalAnalysis(AnalysisType.FULL_MEETING)
    uow.analyses.items[analysis.id] = analysis
    jobs = FakeJobs()
    service = AnalysisApplicationService(
        FakeRetrieval(),
        FakeGeneration(),
        optimizer=_optimizer(),
        model_name="test-model",
        max_input=100,
    )
    handler = AnalysisCommandHandler(lambda: uow, jobs, service)

    response = await handler.handle(
        ExecuteAnalysisCommand(
            matter_id=uow.matters.matter.id,
            meeting_id=meeting.id,
            analysis_id=analysis.id,
            actor=actor,
        )
    )

    assert response.status == "ready_for_review"
    assert len(response.items) == 3


@pytest.mark.anyio
async def test_analysis_with_optimizer_excludes_evidence_when_over_budget() -> None:
    _SpyGeneration.requests.clear()
    uow, actor, meeting = _fixture()
    analysis = LegalAnalysis(AnalysisType.FULL_MEETING)
    uow.analyses.items[analysis.id] = analysis
    jobs = FakeJobs()
    service = AnalysisApplicationService(
        FakeRetrieval(),
        _SpyGeneration(),
        optimizer=_optimizer(),
        model_name="test-model",
        max_input=4,
    )
    handler = AnalysisCommandHandler(lambda: uow, jobs, service)

    await handler.handle(
        ExecuteAnalysisCommand(
            matter_id=uow.matters.matter.id,
            meeting_id=meeting.id,
            analysis_id=analysis.id,
            actor=actor,
        )
    )

    request = _SpyGeneration.requests[0]
    assert request.transcript == "The parties agreed."
    assert len(request.evidence) == 0


@pytest.mark.anyio
async def test_analysis_with_optimizer_rejects_when_transcript_exceeds_budget() -> None:
    _SpyGeneration.requests.clear()
    uow, actor, meeting = _fixture()
    analysis = LegalAnalysis(AnalysisType.FULL_MEETING)
    uow.analyses.items[analysis.id] = analysis
    jobs = FakeJobs()
    service = AnalysisApplicationService(
        FakeRetrieval(),
        _SpyGeneration(),
        optimizer=_optimizer(),
        model_name="test-model",
        max_input=1,
    )
    handler = AnalysisCommandHandler(lambda: uow, jobs, service)

    await handler.handle(
        ExecuteAnalysisCommand(
            matter_id=uow.matters.matter.id,
            meeting_id=meeting.id,
            analysis_id=analysis.id,
            actor=actor,
        )
    )

    request = _SpyGeneration.requests[0]
    assert request.transcript == ""
    assert len(request.evidence) == 0


@pytest.mark.anyio
async def test_analysis_with_optimizer_invokes_tokenizer() -> None:
    class SpyTokenizer(TokenizerPort):
        calls: ClassVar[list[str]] = []

        async def count(self, text: str) -> TokenCount:
            self.calls.append(text)
            return TokenCount(len(text.split()))

        async def truncate(self, text: str, limit: TokenCount) -> str:
            return text

    SpyTokenizer.calls.clear()
    uow, actor, meeting = _fixture()
    analysis = LegalAnalysis(AnalysisType.FULL_MEETING)
    uow.analyses.items[analysis.id] = analysis
    jobs = FakeJobs()
    opt = ContextOptimizer(SpyTokenizer(), _FakeContextWindow())
    service = AnalysisApplicationService(
        FakeRetrieval(),
        FakeGeneration(),
        optimizer=opt,
        model_name="m",
        max_input=100,
    )
    handler = AnalysisCommandHandler(lambda: uow, jobs, service)

    await handler.handle(
        ExecuteAnalysisCommand(
            matter_id=uow.matters.matter.id,
            meeting_id=meeting.id,
            analysis_id=analysis.id,
            actor=actor,
        )
    )

    assert "The parties agreed." in SpyTokenizer.calls


@pytest.mark.anyio
async def test_analysis_with_optimizer_invokes_context_window_port() -> None:
    class SpyWindow(ContextWindowPort):
        calls: ClassVar[list[str]] = []

        async def capacity(self, model_name: str) -> ContextWindow:
            self.calls.append(model_name)
            return ContextWindow(100)

    SpyWindow.calls.clear()
    uow, actor, meeting = _fixture()
    analysis = LegalAnalysis(AnalysisType.FULL_MEETING)
    uow.analyses.items[analysis.id] = analysis
    jobs = FakeJobs()
    opt = ContextOptimizer(_FakeTokenizer(), SpyWindow())
    service = AnalysisApplicationService(
        FakeRetrieval(),
        FakeGeneration(),
        optimizer=opt,
        model_name="llama3.2",
        max_input=50,
    )
    handler = AnalysisCommandHandler(lambda: uow, jobs, service)

    await handler.handle(
        ExecuteAnalysisCommand(
            matter_id=uow.matters.matter.id,
            meeting_id=meeting.id,
            analysis_id=analysis.id,
            actor=actor,
        )
    )

    assert SpyWindow.calls == ["llama3.2"]


@pytest.mark.anyio
async def test_analysis_with_optimizer_passes_reduced_context_to_generation() -> None:
    _SpyGeneration.requests.clear()
    uow, actor, meeting = _fixture()
    analysis = LegalAnalysis(AnalysisType.FULL_MEETING)
    uow.analyses.items[analysis.id] = analysis
    jobs = FakeJobs()
    service = AnalysisApplicationService(
        FakeRetrieval(),
        _SpyGeneration(),
        optimizer=_optimizer(),
        model_name="test-model",
        max_input=4,
    )
    handler = AnalysisCommandHandler(lambda: uow, jobs, service)

    await handler.handle(
        ExecuteAnalysisCommand(
            matter_id=uow.matters.matter.id,
            meeting_id=meeting.id,
            analysis_id=analysis.id,
            actor=actor,
        )
    )

    request = _SpyGeneration.requests[0]
    assert request.transcript == "The parties agreed."
    assert len(request.evidence) == 0
    assert request.analysis_type == "full_meeting"
