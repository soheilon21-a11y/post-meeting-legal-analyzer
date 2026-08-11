from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.authorization import ApplicationAuthorizationService
from app.application.authorization import MatterAction
from app.application.commands.analysis_commands import ApproveAnalysisCommand
from app.application.commands.analysis_commands import ExecuteAnalysisCommand
from app.application.commands.analysis_commands import RejectAnalysisCommand
from app.application.commands.analysis_commands import RequestAnalysisCommand
from app.application.dtos.internal.ai_jobs import AIJobRequest
from app.application.dtos.responses.analysis_responses import AnalysisJobResponse
from app.application.dtos.responses.analysis_responses import AnalysisResponse
from app.application.exceptions.processing import ProcessingError
from app.application.lookup import ResourceLookupService
from app.application.mappers.analysis import DefaultAnalysisMapper

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.mappers.analysis import AnalysisMapper
    from app.application.ports.ai_job_orchestration import AIJobOrchestrationPort
    from app.application.ports.analysis_uow import AnalysisUnitOfWork
    from app.application.queries.analysis_queries import GetAnalysisItemsQuery
    from app.application.queries.analysis_queries import GetAnalysisQuery
    from app.application.services.analysis_service import AnalysisApplicationService


class AnalysisCommandHandler:
    def __init__(
        self,
        uow_factory: Callable[[], AnalysisUnitOfWork],
        jobs: AIJobOrchestrationPort,
        analysis_service: AnalysisApplicationService,
        mapper: AnalysisMapper | None = None,
        authorization: ApplicationAuthorizationService | None = None,
        lookup: ResourceLookupService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._jobs = jobs
        self._analysis_service = analysis_service
        self._mapper = mapper or DefaultAnalysisMapper()
        self._authorization = authorization or ApplicationAuthorizationService()
        self._lookup = lookup or ResourceLookupService()

    async def handle(
        self,
        command: (
            RequestAnalysisCommand
            | ExecuteAnalysisCommand
            | ApproveAnalysisCommand
            | RejectAnalysisCommand
        ),
    ) -> AnalysisResponse | AnalysisJobResponse:
        if isinstance(command, RequestAnalysisCommand):
            return await self._request(command)
        if isinstance(command, ExecuteAnalysisCommand):
            return await self._execute(command)
        async with self._uow_factory() as uow:
            matter = await self._lookup.matter(uow.matters, command.matter_id)
            self._authorization.require_matter_access(command.actor, matter, MatterAction.EDIT)
            analysis = await self._lookup.analysis(
                uow.analyses, command.matter_id, command.analysis_id
            )
            if isinstance(command, ApproveAnalysisCommand):
                analysis.approve()
            else:
                analysis.reject()
            await uow.analyses.save(analysis)
            await uow.commit()
            return self._mapper.to_response(analysis)

    async def _request(self, command: RequestAnalysisCommand) -> AnalysisJobResponse:
        async with self._uow_factory() as uow:
            matter = await self._lookup.matter(uow.matters, command.matter_id)
            self._authorization.require_matter_access(command.actor, matter, MatterAction.EDIT)
            meeting = await self._lookup.meeting(
                uow.meetings, command.matter_id, command.meeting_id
            )
            from app.domain.analysis.entities import LegalAnalysis

            analysis = LegalAnalysis(command.analysis_type)
            await uow.analyses.save(analysis)
            job = await self._jobs.enqueue(
                AIJobRequest(
                    job_type="analysis",
                    matter_id=matter.id,
                    target_id=analysis.id,
                    payload={"meeting_id": str(meeting.id)},
                    idempotency_key=f"analysis:{analysis.id}",
                )
            )
            await uow.commit()
            return AnalysisJobResponse(analysis.id, job.job_id, "queued")

    async def _execute(self, command: ExecuteAnalysisCommand) -> AnalysisResponse:
        job_id = str(command.analysis_id)
        async with self._uow_factory() as uow:
            matter = await self._lookup.matter(uow.matters, command.matter_id)
            self._authorization.require_matter_access(command.actor, matter, MatterAction.EDIT)
            meeting = await self._lookup.meeting(
                uow.meetings, command.matter_id, command.meeting_id
            )
            analysis = await self._lookup.analysis(
                uow.analyses, command.matter_id, command.analysis_id
            )
            try:
                await self._jobs.mark_running(job_id)
                await self._analysis_service.execute(analysis, meeting)
                await uow.analyses.save(analysis)
                await uow.commit()
                await self._jobs.mark_completed(job_id)
            except Exception as exc:
                await self._jobs.mark_failed(job_id, str(exc))
                raise ProcessingError("analysis", str(exc)) from exc
            return self._mapper.to_response(analysis)


class AnalysisQueryHandler:
    def __init__(
        self,
        uow_factory: Callable[[], AnalysisUnitOfWork],
        mapper: AnalysisMapper | None = None,
        authorization: ApplicationAuthorizationService | None = None,
        lookup: ResourceLookupService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._mapper = mapper or DefaultAnalysisMapper()
        self._authorization = authorization or ApplicationAuthorizationService()
        self._lookup = lookup or ResourceLookupService()

    async def handle(self, query: GetAnalysisQuery | GetAnalysisItemsQuery) -> AnalysisResponse:
        async with self._uow_factory() as uow:
            matter = await self._lookup.matter(uow.matters, query.matter_id)
            self._authorization.require_matter_access(query.actor, matter, MatterAction.READ)
            analysis = await self._lookup.analysis(uow.analyses, query.matter_id, query.analysis_id)
            return self._mapper.to_response(analysis)
