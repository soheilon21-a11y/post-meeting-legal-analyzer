from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.exceptions.validation import ApplicationValidationError

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext
    from app.domain.analysis.enums import AnalysisType


@dataclass(frozen=True, slots=True)
class RequestAnalysisRequest:
    matter_id: str
    meeting_id: str
    analysis_type: AnalysisType
    actor: ActorContext

    def __post_init__(self) -> None:
        if not self.matter_id.strip():
            raise ApplicationValidationError("Matter id must not be blank", field="matter_id")
        if not self.meeting_id.strip():
            raise ApplicationValidationError("Meeting id must not be blank", field="meeting_id")
