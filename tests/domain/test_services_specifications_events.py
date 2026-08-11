from __future__ import annotations

from datetime import UTC
from datetime import datetime
from uuid import uuid4

import pytest

from app.domain.analysis import AnalysisType
from app.domain.analysis import ConfidenceScore
from app.domain.analysis import LegalAnalysis
from app.domain.events import AnalysisApproved
from app.domain.events import MeetingReady
from app.domain.matter import Matter
from app.domain.matter import MatterName
from app.domain.meeting import Meeting
from app.domain.meeting import MeetingSource
from app.domain.meeting import MeetingTitle
from app.domain.meeting import TranscriptSegment
from app.domain.redlining import ChangeType
from app.domain.redlining import ClausePath
from app.domain.redlining import ProposedText
from app.domain.redlining import Rationale
from app.domain.redlining import RedlineChange
from app.domain.redlining import RedlineJob
from app.domain.redlining import ReviewStatus
from app.domain.reporting import LegalReport
from app.domain.reporting import ReportTitle
from app.domain.services import AnalysisDomainService
from app.domain.services import RedlineDomainService
from app.domain.services import ReportDomainService
from app.domain.shared.identifiers import AnalysisId
from app.domain.shared.identifiers import EntityId
from app.domain.shared.identifiers import MeetingId
from app.domain.specifications import MatterIsActive
from app.domain.specifications import MeetingIsReady
from app.domain.specifications import Specification


def _ready_meeting() -> Meeting:
    meeting = Meeting(MeetingTitle("Review"), datetime.now(UTC), MeetingSource.TEXT)
    meeting.add_transcript_segment(TranscriptSegment(1, "The parties agreed."))
    meeting.complete_transcription()
    return meeting


def test_specifications_compose_with_and_or_not() -> None:
    matter = Matter(MatterName("Matter"))
    active = MatterIsActive()
    never = MeetingIsReady()  # Different type is intentionally not evaluated here.
    combined: Specification[Matter] = active & active

    assert combined.is_satisfied_by(matter)
    assert (active | ~active).is_satisfied_by(matter)
    assert never is not None


def test_analysis_service_requires_ready_meeting() -> None:
    meeting = _ready_meeting()
    analysis = LegalAnalysis(AnalysisType.FULL_MEETING)
    analysis.begin_processing()

    result = AnalysisDomainService().prepare_for_review(meeting, analysis, "Summary")

    assert result.aggregate_id == analysis.id
    assert analysis.status.value == "ready_for_review"


def test_redline_service_requires_complete_decisions() -> None:
    job = RedlineJob()
    job.begin_processing()
    change = RedlineChange(
        ClausePath("2.1"),
        ChangeType.SUBSTITUTION,
        "Original clause",
        ProposedText("Revised clause"),
        Rationale("Clarifies scope"),
        ConfidenceScore(0.9),
    )
    job.add_change(change)
    job.mark_ready_for_review()

    result = RedlineDomainService().review_changes(
        job,
        {EntityId(change.id): ReviewStatus.APPROVED},
    )

    assert result.status == "reviewed"


def test_report_service_requires_approved_analysis() -> None:
    analysis = LegalAnalysis(AnalysisType.FULL_MEETING)
    report = LegalReport(ReportTitle("Report"))

    with pytest.raises(ValueError, match="approved"):
        ReportDomainService().begin_from_analysis(analysis, report)


def test_domain_events_are_immutable_and_named() -> None:
    event = MeetingReady(aggregate_id=MeetingId(uuid4()))
    assert event.event_name == "MeetingReady"

    with pytest.raises(AttributeError):
        event.aggregate_id = MeetingId(uuid4())  # type: ignore[assignment]

    approved = AnalysisApproved(aggregate_id=AnalysisId(uuid4()))
    assert approved.event_name == "AnalysisApproved"
