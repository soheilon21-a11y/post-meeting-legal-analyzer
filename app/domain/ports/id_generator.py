from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from app.domain.shared.identifiers import AnalysisId
    from app.domain.shared.identifiers import DocumentId
    from app.domain.shared.identifiers import EntityId
    from app.domain.shared.identifiers import MatterId
    from app.domain.shared.identifiers import MeetingId
    from app.domain.shared.identifiers import OrganizationId
    from app.domain.shared.identifiers import RedlineJobId
    from app.domain.shared.identifiers import ReportId
    from app.domain.shared.identifiers import UserId


class IdGenerator(Protocol):
    def new_entity_id(self) -> EntityId: ...

    def new_organization_id(self) -> OrganizationId: ...

    def new_user_id(self) -> UserId: ...

    def new_matter_id(self) -> MatterId: ...

    def new_meeting_id(self) -> MeetingId: ...

    def new_document_id(self) -> DocumentId: ...

    def new_analysis_id(self) -> AnalysisId: ...

    def new_redline_job_id(self) -> RedlineJobId: ...

    def new_report_id(self) -> ReportId: ...
