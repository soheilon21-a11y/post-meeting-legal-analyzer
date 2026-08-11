from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.authorization import ApplicationAuthorizationService
from app.application.authorization import MatterAction
from app.application.commands.report_commands import ApproveReportCommand
from app.application.commands.report_commands import CreateReportCommand
from app.application.commands.report_commands import ExportReportCommand
from app.application.commands.report_commands import GenerateReportCommand
from app.application.dtos.internal.report_generation import ReportGenerationInput
from app.application.lookup import ResourceLookupService
from app.application.mappers.report import DefaultReportMapper
from app.domain.reporting.entities import LegalReport
from app.domain.reporting.value_objects import ReportTitle

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.dtos.responses.report_responses import ReportResponse
    from app.application.mappers.report import ReportMapper
    from app.application.ports.report_uow import ReportUnitOfWork
    from app.application.queries.report_queries import GetReportQuery
    from app.application.services.context_optimizer import ContextOptimizer
    from app.application.services.report_service import ReportApplicationService
    from app.domain.analysis.entities import LegalAnalysis


class ReportCommandHandler:
    def __init__(
        self,
        uow_factory: Callable[[], ReportUnitOfWork],
        report_service: ReportApplicationService,
        mapper: ReportMapper | None = None,
        authorization: ApplicationAuthorizationService | None = None,
        lookup: ResourceLookupService | None = None,
        context_optimizer: ContextOptimizer | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._service = report_service
        self._mapper = mapper or DefaultReportMapper()
        self._authorization = authorization or ApplicationAuthorizationService()
        self._lookup = lookup or ResourceLookupService()
        self._context_optimizer = context_optimizer

    async def handle(
        self,
        command: (
            CreateReportCommand | GenerateReportCommand | ApproveReportCommand | ExportReportCommand
        ),
    ) -> ReportResponse:
        async with self._uow_factory() as uow:
            matter = await self._lookup.matter(uow.matters, command.matter_id)
            self._authorization.require_matter_access(command.actor, matter, MatterAction.EDIT)
            if isinstance(command, CreateReportCommand):
                analysis = await self._lookup.analysis(
                    uow.analyses, command.matter_id, command.analysis_id
                )
                if analysis.status.value != "approved":
                    raise ValueError("Reports can only be created from approved analyses")
                report = LegalReport(ReportTitle(command.title))
            else:
                report = await self._lookup.report(
                    uow.reports, command.matter_id, command.report_id
                )
                if isinstance(command, GenerateReportCommand):
                    context_items: tuple[str, ...] = ()
                    if self._context_optimizer is not None:
                        analysis = await self._lookup.analysis(
                            uow.analyses, command.matter_id, command.analysis_id
                        )
                        context_items = self._assemble_context(analysis)
                    await self._service.generate(
                        report,
                        ReportGenerationInput(
                            report_id=report.id,
                            analysis_id=command.analysis_id,
                            title=report.title.value,
                            context_items=context_items,
                        ),
                    )
                elif isinstance(command, ApproveReportCommand):
                    report.approve()
                else:
                    report.export(command.report_format)
            await uow.reports.save(report)
            await uow.commit()
            return self._mapper.to_response(report)

    @staticmethod
    def _assemble_context(analysis: LegalAnalysis) -> tuple[str, ...]:
        items: list[str] = []
        if analysis.summary:
            items.append(analysis.summary)
        for item in analysis.items:
            items.append(f"{item.title}: {item.description}")
        return tuple(items)


class ReportQueryHandler:
    def __init__(
        self,
        uow_factory: Callable[[], ReportUnitOfWork],
        mapper: ReportMapper | None = None,
        authorization: ApplicationAuthorizationService | None = None,
        lookup: ResourceLookupService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._mapper = mapper or DefaultReportMapper()
        self._authorization = authorization or ApplicationAuthorizationService()
        self._lookup = lookup or ResourceLookupService()

    async def handle(self, query: GetReportQuery) -> ReportResponse:
        async with self._uow_factory() as uow:
            matter = await self._lookup.matter(uow.matters, query.matter_id)
            self._authorization.require_matter_access(query.actor, matter, MatterAction.READ)
            report = await self._lookup.report(uow.reports, query.matter_id, query.report_id)
            return self._mapper.to_response(report)
