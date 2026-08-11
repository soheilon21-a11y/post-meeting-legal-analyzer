from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.exceptions.invariant import InvariantViolation
from app.domain.exceptions.lifecycle import InvalidStateTransition
from app.domain.reporting.enums import ReportFormat
from app.domain.reporting.enums import ReportStatus
from app.domain.reporting.rules import ensure_report_can_be_ready
from app.domain.reporting.rules import ensure_report_can_export
from app.domain.shared.aggregate_root import AggregateRoot
from app.domain.shared.entity import Entity
from app.domain.shared.identifiers import EntityId
from app.domain.shared.identifiers import ReportId

if TYPE_CHECKING:
    from app.domain.reporting.value_objects import ReportTitle


class ReportSection(Entity[EntityId]):
    def __init__(self, heading: str, content: str, sequence_number: int) -> None:
        if not heading.strip() or not content.strip():
            raise InvariantViolation("Report sections require heading and content")
        if sequence_number < 1:
            raise InvariantViolation(
                "sequence_number must be positive", field_name="sequence_number"
            )
        super().__init__()
        self._heading = heading.strip()
        self._content = content.strip()
        self._sequence_number = sequence_number

    @property
    def heading(self) -> str:
        return self._heading

    @property
    def content(self) -> str:
        return self._content

    @property
    def sequence_number(self) -> int:
        return self._sequence_number


class LegalReport(AggregateRoot[ReportId]):
    def __init__(self, title: ReportTitle, report_id: ReportId | None = None) -> None:
        super().__init__(report_id)
        self._title = title
        self._status = ReportStatus.DRAFT
        self._sections: list[ReportSection] = []
        self._exported_formats: set[ReportFormat] = set()

    @property
    def title(self) -> ReportTitle:
        return self._title

    @property
    def status(self) -> ReportStatus:
        return self._status

    @property
    def sections(self) -> tuple[ReportSection, ...]:
        return tuple(self._sections)

    @property
    def exported_formats(self) -> frozenset[ReportFormat]:
        return frozenset(self._exported_formats)

    def begin_generation(self) -> None:
        if self._status is not ReportStatus.DRAFT:
            raise InvalidStateTransition("LegalReport", self._status, ReportStatus.GENERATING)
        self._status = ReportStatus.GENERATING

    def add_section(self, section: ReportSection) -> None:
        if self._status is not ReportStatus.GENERATING:
            raise InvalidStateTransition("LegalReport", self._status, ReportStatus.GENERATING)
        if section.sequence_number != len(self._sections) + 1:
            raise InvariantViolation("Report sections must have contiguous sequence numbers")
        self._sections.append(section)

    def mark_ready(self) -> None:
        ensure_report_can_be_ready(self._status, len(self._sections))
        self._status = ReportStatus.READY

    def approve(self) -> None:
        if self._status is not ReportStatus.READY:
            raise InvalidStateTransition("LegalReport", self._status, ReportStatus.APPROVED)
        self._status = ReportStatus.APPROVED

    def export(self, report_format: ReportFormat) -> None:
        ensure_report_can_export(self._status, report_format)
        self._exported_formats.add(report_format)
        self._status = ReportStatus.EXPORTED
