from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.commands.base import Command

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext
    from app.domain.reporting.enums import ReportFormat
    from app.domain.shared.identifiers import AnalysisId
    from app.domain.shared.identifiers import MatterId
    from app.domain.shared.identifiers import ReportId


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateReportCommand(Command):
    matter_id: MatterId
    analysis_id: AnalysisId
    title: str
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerateReportCommand(Command):
    matter_id: MatterId
    report_id: ReportId
    analysis_id: AnalysisId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ApproveReportCommand(Command):
    matter_id: MatterId
    report_id: ReportId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportReportCommand(Command):
    matter_id: MatterId
    report_id: ReportId
    report_format: ReportFormat
    actor: ActorContext
