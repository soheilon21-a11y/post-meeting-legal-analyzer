from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.commands.base import Command

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext
    from app.domain.shared.identifiers import DocumentId
    from app.domain.shared.identifiers import MatterId
    from app.domain.shared.identifiers import RedlineJobId


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateRedlineCommand(Command):
    matter_id: MatterId
    base_document_id: DocumentId
    comparison_document_id: DocumentId
    deterministic_seed: int
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerateRedlineCommand(Command):
    matter_id: MatterId
    redline_job_id: RedlineJobId
    base_document_id: DocumentId
    comparison_document_id: DocumentId
    deterministic_seed: int
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewRedlineChangeCommand(Command):
    matter_id: MatterId
    redline_job_id: RedlineJobId
    change_id: str
    approve: bool
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class MarkRedlineReviewedCommand(Command):
    matter_id: MatterId
    redline_job_id: RedlineJobId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportRedlineCommand(Command):
    matter_id: MatterId
    redline_job_id: RedlineJobId
    actor: ActorContext
