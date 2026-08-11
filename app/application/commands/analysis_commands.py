from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.commands.base import Command

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext
    from app.domain.analysis.enums import AnalysisType
    from app.domain.shared.identifiers import AnalysisId
    from app.domain.shared.identifiers import MatterId
    from app.domain.shared.identifiers import MeetingId


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestAnalysisCommand(Command):
    matter_id: MatterId
    meeting_id: MeetingId
    analysis_type: AnalysisType
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecuteAnalysisCommand(Command):
    matter_id: MatterId
    meeting_id: MeetingId
    analysis_id: AnalysisId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ApproveAnalysisCommand(Command):
    matter_id: MatterId
    analysis_id: AnalysisId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class RejectAnalysisCommand(Command):
    matter_id: MatterId
    analysis_id: AnalysisId
    actor: ActorContext
