from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from app.domain.analysis.entities import LegalAnalysis
    from app.domain.document.entities import Document
    from app.domain.matter.entities import Matter
    from app.domain.meeting.entities import Meeting
    from app.domain.organization.entities import Organization
    from app.domain.redlining.entities import RedlineJob
    from app.domain.reporting.entities import LegalReport
    from app.domain.shared.identifiers import AnalysisId
    from app.domain.shared.identifiers import DocumentId
    from app.domain.shared.identifiers import MatterId
    from app.domain.shared.identifiers import MeetingId
    from app.domain.shared.identifiers import OrganizationId
    from app.domain.shared.identifiers import RedlineJobId
    from app.domain.shared.identifiers import ReportId


class OrganizationRepository(Protocol):
    async def get(self, organization_id: OrganizationId) -> Organization | None: ...

    async def save(self, organization: Organization) -> None: ...


class MatterRepository(Protocol):
    async def get(self, matter_id: MatterId) -> Matter | None: ...

    async def save(self, matter: Matter) -> None: ...


class MeetingRepository(Protocol):
    async def get(self, meeting_id: MeetingId) -> Meeting | None: ...

    async def save(self, meeting: Meeting) -> None: ...


class DocumentRepository(Protocol):
    async def get(self, document_id: DocumentId) -> Document | None: ...

    async def save(self, document: Document) -> None: ...


class AnalysisRepository(Protocol):
    async def get(self, analysis_id: AnalysisId) -> LegalAnalysis | None: ...

    async def save(self, analysis: LegalAnalysis) -> None: ...


class RedlineRepository(Protocol):
    async def get(self, redline_job_id: RedlineJobId) -> RedlineJob | None: ...

    async def save(self, redline_job: RedlineJob) -> None: ...


class ReportRepository(Protocol):
    async def get(self, report_id: ReportId) -> LegalReport | None: ...

    async def save(self, report: LegalReport) -> None: ...
