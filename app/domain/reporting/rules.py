from app.domain.exceptions.lifecycle import InvalidStateTransition
from app.domain.reporting.enums import ReportFormat
from app.domain.reporting.enums import ReportStatus


def ensure_report_can_be_ready(status: ReportStatus, section_count: int) -> None:
    if status is not ReportStatus.GENERATING:
        raise InvalidStateTransition("LegalReport", status, ReportStatus.READY)
    if section_count == 0:
        raise ValueError("A report requires at least one section")


def ensure_report_can_export(status: ReportStatus, report_format: ReportFormat) -> None:
    if status not in (ReportStatus.READY, ReportStatus.APPROVED):
        raise InvalidStateTransition("LegalReport", status, ReportStatus.EXPORTED)
    if report_format not in ReportFormat:
        raise ValueError("Unsupported report format")
