from __future__ import annotations

from typing import TYPE_CHECKING
from typing import ClassVar
from uuid import uuid4

import pytest

from app.application.commands.redline_commands import CreateRedlineCommand
from app.application.commands.redline_commands import ExportRedlineCommand
from app.application.commands.redline_commands import GenerateRedlineCommand
from app.application.commands.redline_commands import MarkRedlineReviewedCommand
from app.application.commands.redline_commands import ReviewRedlineChangeCommand
from app.application.commands.report_commands import ApproveReportCommand
from app.application.commands.report_commands import CreateReportCommand
from app.application.commands.report_commands import ExportReportCommand
from app.application.commands.report_commands import GenerateReportCommand
from app.application.dtos.internal.redline_generation import GeneratedRedlineChange
from app.application.dtos.internal.redline_generation import GeneratedRedlineCitation
from app.application.dtos.internal.redline_generation import RedlineGenerationInput
from app.application.dtos.internal.redline_generation import RedlineGenerationResult
from app.application.dtos.internal.report_generation import GeneratedReportSection
from app.application.dtos.internal.report_generation import ReportGenerationInput
from app.application.dtos.internal.report_generation import ReportGenerationResult
from app.application.dtos.internal.security import ActorContext
from app.application.handlers.redline_handlers import RedlineCommandHandler
from app.application.handlers.redline_handlers import RedlineQueryHandler
from app.application.handlers.report_handlers import ReportCommandHandler
from app.application.handlers.report_handlers import ReportQueryHandler
from app.application.ports.redline_generation import RedlineGenerationPort
from app.application.ports.report_generation import ReportGenerationPort
from app.application.queries.redline_queries import GetRedlineQuery
from app.application.queries.report_queries import GetReportQuery
from app.application.services.context_optimizer import ContextOptimizer
from app.application.services.redline_service import RedlineApplicationService
from app.application.services.report_service import ReportApplicationService
from app.domain.analysis.entities import Citation
from app.domain.analysis.entities import LegalAnalysis
from app.domain.analysis.entities import Risk
from app.domain.analysis.enums import AnalysisType
from app.domain.analysis.enums import RiskLevel
from app.domain.analysis.value_objects import ConfidenceScore
from app.domain.analysis.value_objects import EvidenceQuote
from app.domain.analysis.value_objects import SourceLocation
from app.domain.document.entities import Document
from app.domain.document.entities import DocumentSegment
from app.domain.document.value_objects import ContentHash
from app.domain.document.value_objects import FileName
from app.domain.document.value_objects import MimeType
from app.domain.document.value_objects import StorageKey
from app.domain.exceptions.redlining import UnsafeRedlineOperation
from app.domain.matter.entities import Matter
from app.domain.matter.enums import MatterMemberRole
from app.domain.matter.value_objects import MatterName
from app.domain.reporting.enums import ReportFormat
from app.domain.shared.identifiers import AnalysisId
from app.domain.shared.identifiers import DocumentId
from app.domain.shared.identifiers import MatterId
from app.domain.shared.identifiers import RedlineJobId
from app.domain.shared.identifiers import ReportId
from app.domain.shared.identifiers import UserId
from app.infrastructure.ai.context_windows.static_registry import StaticContextWindowRegistry
from app.infrastructure.ai.tokenizers.simple_tokenizer import SimpleTokenizer

if TYPE_CHECKING:
    from app.domain.ai.value_objects import ContextWindow
    from app.domain.ai.value_objects import TokenCount
    from app.domain.redlining.entities import RedlineJob
    from app.domain.reporting.entities import LegalReport


class FakeMatterRepository:
    def __init__(self, matter: Matter) -> None:
        self.matter = matter

    async def get(self, matter_id: MatterId) -> Matter | None:
        return self.matter if matter_id == self.matter.id else None

    async def save(self, matter: Matter) -> None:
        self.matter = matter


class FakeDocumentRepository:
    def __init__(self, documents: tuple[Document, ...]) -> None:
        self.documents = {document.id: document for document in documents}

    async def get_for_matter(self, matter_id: MatterId, document_id: DocumentId) -> Document | None:
        return self.documents.get(document_id)

    async def get(self, document_id: DocumentId) -> Document | None:
        return self.documents.get(document_id)

    async def save(self, document: Document) -> None:
        self.documents[document.id] = document


class FakeRedlineRepository:
    def __init__(self) -> None:
        self.items: dict[RedlineJobId, RedlineJob] = {}

    async def get_for_matter(
        self, matter_id: MatterId, redline_job_id: RedlineJobId
    ) -> RedlineJob | None:
        return self.items.get(redline_job_id)

    async def save(self, redline_job: RedlineJob) -> None:
        self.items[redline_job.id] = redline_job


class FakeAnalysisRepository:
    def __init__(self, analysis: LegalAnalysis) -> None:
        self.items = {analysis.id: analysis}

    async def get_for_matter(
        self, matter_id: MatterId, analysis_id: AnalysisId
    ) -> LegalAnalysis | None:
        return self.items.get(analysis_id)

    async def get(self, analysis_id: AnalysisId) -> LegalAnalysis | None:
        return self.items.get(analysis_id)

    async def save(self, analysis: LegalAnalysis) -> None:
        self.items[analysis.id] = analysis


class FakeReportRepository:
    def __init__(self) -> None:
        self.items: dict[ReportId, LegalReport] = {}

    async def get_for_matter(self, matter_id: MatterId, report_id: ReportId) -> LegalReport | None:
        return self.items.get(report_id)

    async def save(self, report: LegalReport) -> None:
        self.items[report.id] = report


class FakeRedlineUnitOfWork:
    def __init__(self, matter: Matter, documents: tuple[Document, ...]) -> None:
        self.matters = FakeMatterRepository(matter)
        self.documents = FakeDocumentRepository(documents)
        self.redlines = FakeRedlineRepository()
        self.commits = 0

    async def __aenter__(self) -> FakeRedlineUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


class FakeReportUnitOfWork:
    def __init__(self, matter: Matter, analysis: LegalAnalysis) -> None:
        self.matters = FakeMatterRepository(matter)
        self.analyses = FakeAnalysisRepository(analysis)
        self.reports = FakeReportRepository()
        self.commits = 0

    async def __aenter__(self) -> FakeReportUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


class FakeRedlineGeneration(RedlineGenerationPort):
    async def generate(self, request: RedlineGenerationInput) -> RedlineGenerationResult:
        return RedlineGenerationResult(
            changes=(
                GeneratedRedlineChange(
                    clause_path="4.2 Liability",
                    change_type="substitution",
                    original_text="The supplier is liable.",
                    proposed_text="The supplier is liable for direct losses only.",
                    rationale="Limits exposure to direct losses.",
                    risk_level="high",
                    confidence=0.91,
                    citations=(GeneratedRedlineCitation("contract-v1", "The supplier is liable."),),
                ),
            )
        )


class FakeReportGeneration(ReportGenerationPort):
    async def generate(self, request: ReportGenerationInput) -> ReportGenerationResult:
        return ReportGenerationResult(
            sections=(
                GeneratedReportSection("Executive Summary", "The analysis is complete."),
                GeneratedReportSection("Risks", "One liability risk requires review."),
            )
        )


def _matter_and_actor() -> tuple[Matter, ActorContext]:
    matter = Matter(MatterName("Matter"))
    actor = ActorContext(user_id=UserId(uuid4()))
    matter.add_member(actor.user_id, MatterMemberRole.OWNER)
    return matter, actor


def _document(title: str) -> Document:
    return Document(
        title,
        FileName(f"{title.lower()}.docx"),
        MimeType("application/vnd.test"),
        ContentHash("a" * 64),
    )


def _approved_analysis() -> LegalAnalysis:
    analysis = LegalAnalysis(AnalysisType.FULL_MEETING)
    analysis.begin_processing()
    citation = Citation(EvidenceQuote("A liability clause."), SourceLocation("contract"))
    analysis.add_item(
        Risk("Risk", "A material risk.", RiskLevel.HIGH, ConfidenceScore(0.9), (citation,))
    )
    analysis.set_summary("A complete analysis.")
    analysis.mark_ready_for_review()
    analysis.approve()
    return analysis


@pytest.mark.anyio
async def test_redline_generation_preserves_original_and_requires_review() -> None:
    matter, actor = _matter_and_actor()
    base, comparison = _document("Base"), _document("Comparison")
    uow = FakeRedlineUnitOfWork(matter, (base, comparison))
    handler = RedlineCommandHandler(
        lambda: uow,
        RedlineApplicationService(FakeRedlineGeneration()),
    )
    created = await handler.handle(
        CreateRedlineCommand(
            matter_id=matter.id,
            base_document_id=base.id,
            comparison_document_id=comparison.id,
            deterministic_seed=42,
            actor=actor,
        )
    )
    with pytest.raises(UnsafeRedlineOperation, match="not ready for review"):
        await handler.handle(
            MarkRedlineReviewedCommand(
                matter_id=matter.id,
                redline_job_id=RedlineJobId(created.id),
                actor=actor,
            )
        )

    generated = await handler.handle(
        GenerateRedlineCommand(
            matter_id=matter.id,
            redline_job_id=RedlineJobId(created.id),
            base_document_id=base.id,
            comparison_document_id=comparison.id,
            deterministic_seed=42,
            actor=actor,
        )
    )
    change = generated.changes[0]
    assert change.original_text == "The supplier is liable."
    assert change.risk_level == "high"
    assert change.citations[0].quote == "The supplier is liable."
    assert change.review_status == "pending"


@pytest.mark.anyio
async def test_redline_review_and_export_require_explicit_approval() -> None:
    matter, actor = _matter_and_actor()
    base, comparison = _document("Base"), _document("Comparison")
    uow = FakeRedlineUnitOfWork(matter, (base, comparison))
    handler = RedlineCommandHandler(lambda: uow, RedlineApplicationService(FakeRedlineGeneration()))
    created = await handler.handle(
        CreateRedlineCommand(
            matter_id=matter.id,
            base_document_id=base.id,
            comparison_document_id=comparison.id,
            deterministic_seed=7,
            actor=actor,
        )
    )
    generated = await handler.handle(
        GenerateRedlineCommand(
            matter_id=matter.id,
            redline_job_id=RedlineJobId(created.id),
            base_document_id=base.id,
            comparison_document_id=comparison.id,
            deterministic_seed=7,
            actor=actor,
        )
    )
    job_id = RedlineJobId(created.id)
    await handler.handle(
        ReviewRedlineChangeCommand(
            matter_id=matter.id,
            redline_job_id=job_id,
            change_id=str(generated.changes[0].id),
            approve=True,
            actor=actor,
        )
    )
    reviewed = await handler.handle(
        MarkRedlineReviewedCommand(matter_id=matter.id, redline_job_id=job_id, actor=actor)
    )
    exported = await handler.handle(
        ExportRedlineCommand(matter_id=matter.id, redline_job_id=job_id, actor=actor)
    )
    queried = await RedlineQueryHandler(lambda: uow).handle(
        GetRedlineQuery(matter_id=matter.id, redline_job_id=job_id, actor=actor)
    )

    assert reviewed.status == "reviewed"
    assert exported.status == "exported"
    assert queried.changes[0].review_status == "approved"


@pytest.mark.anyio
async def test_report_generation_approval_and_export() -> None:
    matter, actor = _matter_and_actor()
    analysis = _approved_analysis()
    uow = FakeReportUnitOfWork(matter, analysis)
    handler = ReportCommandHandler(lambda: uow, ReportApplicationService(FakeReportGeneration()))
    created = await handler.handle(
        CreateReportCommand(
            matter_id=matter.id,
            analysis_id=analysis.id,
            title="Legal report",
            actor=actor,
        )
    )
    generated = await handler.handle(
        GenerateReportCommand(
            matter_id=matter.id,
            report_id=ReportId(created.id),
            analysis_id=analysis.id,
            actor=actor,
        )
    )
    approved = await handler.handle(
        ApproveReportCommand(matter_id=matter.id, report_id=ReportId(created.id), actor=actor)
    )
    exported = await handler.handle(
        ExportReportCommand(
            matter_id=matter.id,
            report_id=ReportId(created.id),
            report_format=ReportFormat.PDF,
            actor=actor,
        )
    )
    queried = await ReportQueryHandler(lambda: uow).handle(
        GetReportQuery(matter_id=matter.id, report_id=ReportId(created.id), actor=actor)
    )

    assert generated.status == "ready"
    assert approved.status == "approved"
    assert exported.status == "exported"
    assert "pdf" in queried.exported_formats


def _document_with_text(title: str, text: str) -> Document:
    doc = _document(title)
    version = doc.add_version(StorageKey(f"{title.lower()}/v1"))
    version.start_processing()
    version.add_segment(DocumentSegment(text, ContentHash("a" * 64)))
    version.complete_processing()
    return doc


class _SpyRedlineGeneration(RedlineGenerationPort):
    requests: ClassVar[list[RedlineGenerationInput]] = []

    async def generate(self, request: RedlineGenerationInput) -> RedlineGenerationResult:
        self.requests.append(request)
        return RedlineGenerationResult(
            changes=(
                GeneratedRedlineChange(
                    clause_path="4.2 Liability",
                    change_type="substitution",
                    original_text="The supplier is liable.",
                    proposed_text="The supplier is liable for direct losses only.",
                    rationale="Limits exposure to direct losses.",
                    risk_level="high",
                    confidence=0.91,
                    citations=(GeneratedRedlineCitation("contract-v1", "The supplier is liable."),),
                ),
            )
        )


class _SpyReportGeneration(ReportGenerationPort):
    requests: ClassVar[list[ReportGenerationInput]] = []

    async def generate(self, request: ReportGenerationInput) -> ReportGenerationResult:
        self.requests.append(request)
        return ReportGenerationResult(
            sections=(
                GeneratedReportSection("Executive Summary", "The analysis is complete."),
                GeneratedReportSection("Risks", "One liability risk requires review."),
            )
        )


def _optimizer() -> ContextOptimizer:
    return ContextOptimizer(SimpleTokenizer(), StaticContextWindowRegistry())


@pytest.mark.anyio
async def test_redline_without_optimizer_preserves_existing_behavior() -> None:
    matter, actor = _matter_and_actor()
    base, comparison = _document("Base"), _document("Comparison")
    uow = FakeRedlineUnitOfWork(matter, (base, comparison))
    handler = RedlineCommandHandler(
        lambda: uow,
        RedlineApplicationService(FakeRedlineGeneration()),
    )
    created = await handler.handle(
        CreateRedlineCommand(
            matter_id=matter.id,
            base_document_id=base.id,
            comparison_document_id=comparison.id,
            deterministic_seed=42,
            actor=actor,
        )
    )
    generated = await handler.handle(
        GenerateRedlineCommand(
            matter_id=matter.id,
            redline_job_id=RedlineJobId(created.id),
            base_document_id=base.id,
            comparison_document_id=comparison.id,
            deterministic_seed=42,
            actor=actor,
        )
    )
    assert generated.status == "ready_for_review"
    assert len(generated.changes) == 1


@pytest.mark.anyio
async def test_report_without_optimizer_preserves_existing_behavior() -> None:
    matter, actor = _matter_and_actor()
    analysis = _approved_analysis()
    uow = FakeReportUnitOfWork(matter, analysis)
    handler = ReportCommandHandler(lambda: uow, ReportApplicationService(FakeReportGeneration()))
    created = await handler.handle(
        CreateReportCommand(
            matter_id=matter.id,
            analysis_id=analysis.id,
            title="Legal report",
            actor=actor,
        )
    )
    generated = await handler.handle(
        GenerateReportCommand(
            matter_id=matter.id,
            report_id=ReportId(created.id),
            analysis_id=analysis.id,
            actor=actor,
        )
    )
    assert generated.status == "ready"


@pytest.mark.anyio
async def test_redline_with_optimizer_preserves_context_within_budget() -> None:
    _SpyRedlineGeneration.requests.clear()
    matter, actor = _matter_and_actor()
    base = _document_with_text("Base", "The supplier is liable for all damages.")
    comparison = _document_with_text("Comparison", "The supplier is liable for direct losses only.")
    uow = FakeRedlineUnitOfWork(matter, (base, comparison))
    handler = RedlineCommandHandler(
        lambda: uow,
        RedlineApplicationService(
            _SpyRedlineGeneration(),
            optimizer=_optimizer(),
            model_name="test-model",
            max_input=100,
        ),
        context_optimizer=_optimizer(),
    )
    created = await handler.handle(
        CreateRedlineCommand(
            matter_id=matter.id,
            base_document_id=base.id,
            comparison_document_id=comparison.id,
            deterministic_seed=1,
            actor=actor,
        )
    )
    await handler.handle(
        GenerateRedlineCommand(
            matter_id=matter.id,
            redline_job_id=RedlineJobId(created.id),
            base_document_id=base.id,
            comparison_document_id=comparison.id,
            deterministic_seed=1,
            actor=actor,
        )
    )
    request = _SpyRedlineGeneration.requests[0]
    assert request.context_items == (
        "The supplier is liable for all damages.",
        "The supplier is liable for direct losses only.",
    )


@pytest.mark.anyio
async def test_redline_with_optimizer_excludes_lower_priority_when_over_budget() -> None:
    _SpyRedlineGeneration.requests.clear()
    matter, actor = _matter_and_actor()
    base = _document_with_text("Base", "one two three")
    comparison = _document_with_text("Comparison", "alpha beta gamma delta")
    uow = FakeRedlineUnitOfWork(matter, (base, comparison))
    handler = RedlineCommandHandler(
        lambda: uow,
        RedlineApplicationService(
            _SpyRedlineGeneration(),
            optimizer=_optimizer(),
            model_name="test-model",
            max_input=5,
        ),
        context_optimizer=_optimizer(),
    )
    created = await handler.handle(
        CreateRedlineCommand(
            matter_id=matter.id,
            base_document_id=base.id,
            comparison_document_id=comparison.id,
            deterministic_seed=1,
            actor=actor,
        )
    )
    await handler.handle(
        GenerateRedlineCommand(
            matter_id=matter.id,
            redline_job_id=RedlineJobId(created.id),
            base_document_id=base.id,
            comparison_document_id=comparison.id,
            deterministic_seed=1,
            actor=actor,
        )
    )
    request = _SpyRedlineGeneration.requests[0]
    assert request.context_items == ("one two three",)


@pytest.mark.anyio
async def test_report_with_optimizer_preserves_context_within_budget() -> None:
    _SpyReportGeneration.requests.clear()
    matter, actor = _matter_and_actor()
    analysis = _approved_analysis()
    uow = FakeReportUnitOfWork(matter, analysis)
    handler = ReportCommandHandler(
        lambda: uow,
        ReportApplicationService(
            _SpyReportGeneration(),
            optimizer=_optimizer(),
            model_name="test-model",
            max_input=100,
        ),
        context_optimizer=_optimizer(),
    )
    created = await handler.handle(
        CreateReportCommand(
            matter_id=matter.id,
            analysis_id=analysis.id,
            title="Legal report",
            actor=actor,
        )
    )
    await handler.handle(
        GenerateReportCommand(
            matter_id=matter.id,
            report_id=ReportId(created.id),
            analysis_id=analysis.id,
            actor=actor,
        )
    )
    request = _SpyReportGeneration.requests[0]
    assert "A complete analysis." in request.context_items
    assert "Risk: A material risk." in request.context_items


@pytest.mark.anyio
async def test_report_with_optimizer_excludes_lower_priority_when_over_budget() -> None:
    _SpyReportGeneration.requests.clear()
    matter, actor = _matter_and_actor()
    analysis = _approved_analysis()
    uow = FakeReportUnitOfWork(matter, analysis)
    handler = ReportCommandHandler(
        lambda: uow,
        ReportApplicationService(
            _SpyReportGeneration(),
            optimizer=_optimizer(),
            model_name="test-model",
            max_input=3,
        ),
        context_optimizer=_optimizer(),
    )
    created = await handler.handle(
        CreateReportCommand(
            matter_id=matter.id,
            analysis_id=analysis.id,
            title="Legal report",
            actor=actor,
        )
    )
    await handler.handle(
        GenerateReportCommand(
            matter_id=matter.id,
            report_id=ReportId(created.id),
            analysis_id=analysis.id,
            actor=actor,
        )
    )
    request = _SpyReportGeneration.requests[0]
    assert request.context_items == ("A complete analysis.",)


@pytest.mark.anyio
async def test_redline_optimizer_invokes_tokenizer_and_context_window() -> None:
    class SpyTokenizer(SimpleTokenizer):
        calls: ClassVar[list[str]] = []

        async def count(self, text: str) -> TokenCount:
            self.calls.append(text)
            return await super().count(text)

    class SpyWindow(StaticContextWindowRegistry):
        calls: ClassVar[list[str]] = []

        async def capacity(self, model_name: str) -> ContextWindow:
            self.calls.append(model_name)
            return await super().capacity(model_name)

    SpyTokenizer.calls.clear()
    SpyWindow.calls.clear()

    _SpyRedlineGeneration.requests.clear()
    matter, actor = _matter_and_actor()
    base = _document_with_text("Base", "hello world")
    comparison = _document_with_text("Comparison", "foo bar")
    uow = FakeRedlineUnitOfWork(matter, (base, comparison))
    opt = ContextOptimizer(SpyTokenizer(), SpyWindow())
    handler = RedlineCommandHandler(
        lambda: uow,
        RedlineApplicationService(
            _SpyRedlineGeneration(),
            optimizer=opt,
            model_name="llama3.2",
            max_input=10,
        ),
        context_optimizer=opt,
    )
    created = await handler.handle(
        CreateRedlineCommand(
            matter_id=matter.id,
            base_document_id=base.id,
            comparison_document_id=comparison.id,
            deterministic_seed=1,
            actor=actor,
        )
    )
    await handler.handle(
        GenerateRedlineCommand(
            matter_id=matter.id,
            redline_job_id=RedlineJobId(created.id),
            base_document_id=base.id,
            comparison_document_id=comparison.id,
            deterministic_seed=1,
            actor=actor,
        )
    )

    assert "hello world" in SpyTokenizer.calls
    assert "foo bar" in SpyTokenizer.calls
    assert SpyWindow.calls == ["llama3.2"]


@pytest.mark.anyio
async def test_report_optimizer_invokes_tokenizer_and_context_window() -> None:
    class SpyTokenizer(SimpleTokenizer):
        calls: ClassVar[list[str]] = []

        async def count(self, text: str) -> TokenCount:
            self.calls.append(text)
            return await super().count(text)

    class SpyWindow(StaticContextWindowRegistry):
        calls: ClassVar[list[str]] = []

        async def capacity(self, model_name: str) -> ContextWindow:
            self.calls.append(model_name)
            return await super().capacity(model_name)

    SpyTokenizer.calls.clear()
    SpyWindow.calls.clear()

    _SpyReportGeneration.requests.clear()
    matter, actor = _matter_and_actor()
    analysis = _approved_analysis()
    uow = FakeReportUnitOfWork(matter, analysis)
    opt = ContextOptimizer(SpyTokenizer(), SpyWindow())
    handler = ReportCommandHandler(
        lambda: uow,
        ReportApplicationService(
            _SpyReportGeneration(),
            optimizer=opt,
            model_name="mistral",
            max_input=10,
        ),
        context_optimizer=opt,
    )
    created = await handler.handle(
        CreateReportCommand(
            matter_id=matter.id,
            analysis_id=analysis.id,
            title="Legal report",
            actor=actor,
        )
    )
    await handler.handle(
        GenerateReportCommand(
            matter_id=matter.id,
            report_id=ReportId(created.id),
            analysis_id=analysis.id,
            actor=actor,
        )
    )

    assert "A complete analysis." in SpyTokenizer.calls
    assert SpyWindow.calls == ["mistral"]


@pytest.mark.anyio
async def test_redline_handler_validation_unchanged_with_optimizer() -> None:
    matter, actor = _matter_and_actor()
    base, comparison = _document("Base"), _document("Comparison")
    uow = FakeRedlineUnitOfWork(matter, (base, comparison))
    handler = RedlineCommandHandler(
        lambda: uow,
        RedlineApplicationService(FakeRedlineGeneration(), optimizer=_optimizer()),
        context_optimizer=_optimizer(),
    )
    with pytest.raises(Exception):
        await handler.handle(
            CreateRedlineCommand(
                matter_id=matter.id,
                base_document_id=DocumentId(uuid4()),
                comparison_document_id=comparison.id,
                deterministic_seed=1,
                actor=actor,
            )
        )
