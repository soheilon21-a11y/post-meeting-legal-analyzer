from __future__ import annotations

from typing import NewType
from uuid import UUID
from uuid import uuid4

EntityId = NewType("EntityId", UUID)
OrganizationId = NewType("OrganizationId", UUID)
UserId = NewType("UserId", UUID)
MatterId = NewType("MatterId", UUID)
MeetingId = NewType("MeetingId", UUID)
DocumentId = NewType("DocumentId", UUID)
AnalysisId = NewType("AnalysisId", UUID)
RedlineJobId = NewType("RedlineJobId", UUID)
ReportId = NewType("ReportId", UUID)


def new_entity_id() -> EntityId:
    return EntityId(uuid4())
