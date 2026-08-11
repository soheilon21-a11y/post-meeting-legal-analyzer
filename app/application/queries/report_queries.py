from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.queries.base import Query

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext
    from app.domain.shared.identifiers import MatterId
    from app.domain.shared.identifiers import ReportId


@dataclass(frozen=True, slots=True, kw_only=True)
class GetReportQuery(Query):
    matter_id: MatterId
    report_id: ReportId
    actor: ActorContext
