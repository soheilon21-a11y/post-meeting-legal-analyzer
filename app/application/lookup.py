from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.exceptions.not_found import ResourceNotFound

if TYPE_CHECKING:
    from app.application.ports.analysis_uow import AnalysisReadRepository
    from app.application.ports.document_uow import DocumentReadRepository
    from app.application.ports.meeting_uow import MeetingReadRepository
    from app.application.ports.redline_uow import RedlineRepository
    from app.application.ports.report_uow import ReportRepository
    from app.domain.analysis.entities import LegalAnalysis
    from app.domain.document.entities import Document
    from app.domain.matter.entities import Matter
    from app.domain.meeting.entities import Meeting
    from app.domain.organization.entities import Organization
    from app.domain.ports.repositories import MatterRepository
    from app.domain.ports.repositories import OrganizationRepository
    from app.domain.redlining.entities import RedlineJob
    from app.domain.reporting.entities import LegalReport
    from app.domain.shared.identifiers import AnalysisId
    from app.domain.shared.identifiers import DocumentId
    from app.domain.shared.identifiers import MatterId
    from app.domain.shared.identifiers import MeetingId
    from app.domain.shared.identifiers import OrganizationId
    from app.domain.shared.identifiers import RedlineJobId
    from app.domain.shared.identifiers import ReportId


class ResourceLookupService:
    """Centralizes aggregate lookup and stable not-found translation."""

    async def organization(
        self,
        repository: OrganizationRepository,
        organization_id: OrganizationId,
    ) -> Organization:
        organization = await repository.get(organization_id)
        if organization is None:
            raise ResourceNotFound("Organization", str(organization_id))
        return organization

    async def matter(
        self,
        repository: MatterRepository,
        matter_id: MatterId,
    ) -> Matter:
        matter = await repository.get(matter_id)
        if matter is None:
            raise ResourceNotFound("Matter", str(matter_id))
        return matter

    async def meeting(
        self,
        repository: MeetingReadRepository,
        matter_id: MatterId,
        meeting_id: MeetingId,
    ) -> Meeting:
        meeting = await repository.get_for_matter(matter_id, meeting_id)
        if meeting is None:
            raise ResourceNotFound("Meeting", str(meeting_id))
        return meeting

    async def document(
        self,
        repository: DocumentReadRepository,
        matter_id: MatterId,
        document_id: DocumentId,
    ) -> Document:
        document = await repository.get_for_matter(matter_id, document_id)
        if document is None:
            raise ResourceNotFound("Document", str(document_id))
        return document

    async def analysis(
        self,
        repository: AnalysisReadRepository,
        matter_id: MatterId,
        analysis_id: AnalysisId,
    ) -> LegalAnalysis:
        analysis = await repository.get_for_matter(matter_id, analysis_id)
        if analysis is None:
            raise ResourceNotFound("Analysis", str(analysis_id))
        return analysis

    async def redline(
        self,
        repository: RedlineRepository,
        matter_id: MatterId,
        redline_job_id: RedlineJobId,
    ) -> RedlineJob:
        redline = await repository.get_for_matter(matter_id, redline_job_id)
        if redline is None:
            raise ResourceNotFound("RedlineJob", str(redline_job_id))
        return redline

    async def report(
        self,
        repository: ReportRepository,
        matter_id: MatterId,
        report_id: ReportId,
    ) -> LegalReport:
        report = await repository.get_for_matter(matter_id, report_id)
        if report is None:
            raise ResourceNotFound("Report", str(report_id))
        return report
