from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.queries.base import Query

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext
    from app.domain.shared.identifiers import MatterId
    from app.domain.shared.identifiers import MeetingId


@dataclass(frozen=True, slots=True, kw_only=True)
class GetMeetingQuery(Query):
    matter_id: MatterId
    meeting_id: MeetingId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class GetMeetingTranscriptQuery(Query):
    matter_id: MatterId
    meeting_id: MeetingId
    actor: ActorContext
