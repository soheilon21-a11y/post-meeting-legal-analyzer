from app.domain.analysis.entities import LegalAnalysis
from app.domain.analysis.enums import AnalysisStatus
from app.domain.matter.entities import Matter
from app.domain.matter.enums import MatterStatus
from app.domain.meeting.entities import Meeting
from app.domain.meeting.enums import MeetingStatus
from app.domain.redlining.entities import RedlineJob
from app.domain.redlining.enums import RedlineStatus
from app.domain.reporting.entities import LegalReport
from app.domain.reporting.enums import ReportStatus
from app.domain.specifications.base import Specification


class MatterIsActive(Specification[Matter]):
    def is_satisfied_by(self, candidate: Matter) -> bool:
        return candidate.status is MatterStatus.ACTIVE


class MatterHasLegalHold(Specification[Matter]):
    def is_satisfied_by(self, candidate: Matter) -> bool:
        return candidate.legal_hold


class MeetingIsReady(Specification[Meeting]):
    def is_satisfied_by(self, candidate: Meeting) -> bool:
        return candidate.status is MeetingStatus.READY


class AnalysisIsReadyForReview(Specification[LegalAnalysis]):
    def is_satisfied_by(self, candidate: LegalAnalysis) -> bool:
        return candidate.status is AnalysisStatus.READY_FOR_REVIEW


class AnalysisIsApproved(Specification[LegalAnalysis]):
    def is_satisfied_by(self, candidate: LegalAnalysis) -> bool:
        return candidate.status is AnalysisStatus.APPROVED


class RedlineIsReviewed(Specification[RedlineJob]):
    def is_satisfied_by(self, candidate: RedlineJob) -> bool:
        return candidate.status is RedlineStatus.REVIEWED


class ReportIsReady(Specification[LegalReport]):
    def is_satisfied_by(self, candidate: LegalReport) -> bool:
        return candidate.status in (ReportStatus.READY, ReportStatus.APPROVED)
