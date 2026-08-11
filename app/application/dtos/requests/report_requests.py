from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.exceptions.validation import ApplicationValidationError

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext
    from app.domain.reporting.enums import ReportFormat


@dataclass(frozen=True, slots=True)
class CreateReportRequest:
    matter_id: str
    analysis_id: str
    title: str
    actor: ActorContext

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ApplicationValidationError("Report title must not be blank", field="title")


@dataclass(frozen=True, slots=True)
class ExportReportRequest:
    matter_id: str
    report_id: str
    report_format: ReportFormat
    actor: ActorContext
