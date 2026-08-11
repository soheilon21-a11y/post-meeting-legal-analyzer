from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.application.authorization import ApplicationAuthorizationService
from app.application.authorization import MatterAction
from app.application.commands.redline_commands import CreateRedlineCommand
from app.application.commands.redline_commands import ExportRedlineCommand
from app.application.commands.redline_commands import GenerateRedlineCommand
from app.application.commands.redline_commands import MarkRedlineReviewedCommand
from app.application.commands.redline_commands import ReviewRedlineChangeCommand
from app.application.dtos.internal.redline_generation import RedlineGenerationInput
from app.application.exceptions.not_found import ResourceNotFound
from app.application.lookup import ResourceLookupService
from app.application.mappers.redline import DefaultRedlineMapper
from app.domain.redlining.entities import RedlineJob

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.dtos.responses.redline_responses import RedlineResponse
    from app.application.mappers.redline import RedlineMapper
    from app.application.ports.redline_uow import RedlineUnitOfWork
    from app.application.queries.redline_queries import GetRedlineQuery
    from app.application.services.context_optimizer import ContextOptimizer
    from app.application.services.redline_service import RedlineApplicationService
    from app.domain.document.entities import Document


class RedlineCommandHandler:
    def __init__(
        self,
        uow_factory: Callable[[], RedlineUnitOfWork],
        redline_service: RedlineApplicationService,
        mapper: RedlineMapper | None = None,
        authorization: ApplicationAuthorizationService | None = None,
        lookup: ResourceLookupService | None = None,
        context_optimizer: ContextOptimizer | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._service = redline_service
        self._mapper = mapper or DefaultRedlineMapper()
        self._authorization = authorization or ApplicationAuthorizationService()
        self._lookup = lookup or ResourceLookupService()
        self._context_optimizer = context_optimizer

    async def handle(
        self,
        command: (
            CreateRedlineCommand
            | GenerateRedlineCommand
            | ReviewRedlineChangeCommand
            | MarkRedlineReviewedCommand
            | ExportRedlineCommand
        ),
    ) -> RedlineResponse:
        async with self._uow_factory() as uow:
            matter = await self._lookup.matter(uow.matters, command.matter_id)
            self._authorization.require_matter_access(command.actor, matter, MatterAction.EDIT)
            if isinstance(command, CreateRedlineCommand):
                await self._lookup.document(
                    uow.documents, command.matter_id, command.base_document_id
                )
                await self._lookup.document(
                    uow.documents, command.matter_id, command.comparison_document_id
                )
                job = RedlineJob()
            else:
                job = await self._lookup.redline(
                    uow.redlines, command.matter_id, command.redline_job_id
                )
                if isinstance(command, GenerateRedlineCommand):
                    context_items: tuple[str, ...] = ()
                    if self._context_optimizer is not None:
                        base_doc = await self._lookup.document(
                            uow.documents, command.matter_id, command.base_document_id
                        )
                        comparison_doc = await self._lookup.document(
                            uow.documents, command.matter_id, command.comparison_document_id
                        )
                        context_items = self._assemble_context(base_doc, comparison_doc)
                    await self._service.generate(
                        job,
                        RedlineGenerationInput(
                            redline_job_id=job.id,
                            base_document_id=command.base_document_id,
                            comparison_document_id=command.comparison_document_id,
                            deterministic_seed=command.deterministic_seed,
                            context_items=context_items,
                        ),
                    )
                elif isinstance(command, ReviewRedlineChangeCommand):
                    self._review_change(job, command.change_id, command.approve)
                elif isinstance(command, MarkRedlineReviewedCommand):
                    job.mark_reviewed()
                else:
                    job.export()
            await uow.redlines.save(job)
            await uow.commit()
            return self._mapper.to_response(job)

    @staticmethod
    def _assemble_context(base: Document, comparison: Document) -> tuple[str, ...]:
        items: list[str] = []
        for version in base.versions:
            for segment in version.segments:
                items.append(segment.text)
        for version in comparison.versions:
            for segment in version.segments:
                items.append(segment.text)
        return tuple(items)

    @staticmethod
    def _review_change(job: RedlineJob, change_id: str, approve: bool) -> None:
        try:
            target_id = UUID(change_id)
        except ValueError as exc:
            raise ResourceNotFound("RedlineChange", change_id) from exc
        change = next((item for item in job.changes if item.id == target_id), None)
        if change is None:
            raise ResourceNotFound("RedlineChange", change_id)
        if approve:
            change.approve()
        else:
            change.reject()


class RedlineQueryHandler:
    def __init__(
        self,
        uow_factory: Callable[[], RedlineUnitOfWork],
        mapper: RedlineMapper | None = None,
        authorization: ApplicationAuthorizationService | None = None,
        lookup: ResourceLookupService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._mapper = mapper or DefaultRedlineMapper()
        self._authorization = authorization or ApplicationAuthorizationService()
        self._lookup = lookup or ResourceLookupService()

    async def handle(self, query: GetRedlineQuery) -> RedlineResponse:
        async with self._uow_factory() as uow:
            matter = await self._lookup.matter(uow.matters, query.matter_id)
            self._authorization.require_matter_access(query.actor, matter, MatterAction.READ)
            job = await self._lookup.redline(uow.redlines, query.matter_id, query.redline_job_id)
            return self._mapper.to_response(job)
