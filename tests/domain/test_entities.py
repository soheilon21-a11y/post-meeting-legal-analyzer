from __future__ import annotations

from datetime import UTC
from datetime import date
from datetime import datetime
from uuid import uuid4

import pytest

from app.domain.analysis import ActionItem
from app.domain.analysis import AnalysisType
from app.domain.analysis import Citation
from app.domain.analysis import ConfidenceScore
from app.domain.analysis import Deadline
from app.domain.analysis import EvidenceQuote
from app.domain.analysis import LegalAnalysis
from app.domain.analysis import Obligation
from app.domain.analysis import ResponsibleParty
from app.domain.analysis import Risk
from app.domain.analysis import RiskLevel
from app.domain.analysis import SourceLocation
from app.domain.document import ContentHash
from app.domain.document import Document
from app.domain.document import DocumentSegment
from app.domain.document import FileName
from app.domain.document import MimeType
from app.domain.document import StorageKey
from app.domain.exceptions import InvariantViolation
from app.domain.exceptions import MissingEvidence
from app.domain.exceptions import UnsafeRedlineOperation
from app.domain.matter import Matter
from app.domain.matter import MatterMemberRole
from app.domain.matter import MatterName
from app.domain.meeting import Meeting
from app.domain.meeting import MeetingSource
from app.domain.meeting import MeetingTitle
from app.domain.meeting import Speaker
from app.domain.meeting import TranscriptSegment
from app.domain.meeting import TranscriptTimestamp
from app.domain.redlining import ChangeType
from app.domain.redlining import ClausePath
from app.domain.redlining import ProposedText
from app.domain.redlining import Rationale
from app.domain.redlining import RedlineChange
from app.domain.redlining import RedlineJob
from app.domain.reporting import LegalReport
from app.domain.reporting import ReportFormat
from app.domain.reporting import ReportSection
from app.domain.reporting import ReportTitle
from app.domain.shared.identifiers import UserId


def _citation() -> Citation:
    return Citation(
        EvidenceQuote("The parties will deliver the notice within five days."),
        SourceLocation("segment-1", start_offset=0, end_offset=60),
    )


def _hash() -> ContentHash:
    return ContentHash("a" * 64)


def test_matter_requires_an_owner_and_protects_legal_hold() -> None:
    matter = Matter(MatterName("Acme acquisition"))
    owner = UserId(uuid4())
    viewer = UserId(uuid4())
    matter.add_member(owner, MatterMemberRole.OWNER)
    matter.add_member(viewer, MatterMemberRole.VIEWER)

    with pytest.raises(ValueError, match="at least one owner"):
        matter.remove_member(owner)

    matter.apply_legal_hold()
    with pytest.raises(ValueError, match="legal hold"):
        matter.rename(MatterName("Renamed matter"))


def test_meeting_enforces_transcript_sequence_and_completion() -> None:
    meeting = Meeting(
        MeetingTitle("Negotiation"),
        datetime.now(UTC),
        MeetingSource.TEXT,
    )
    meeting.begin_transcription()
    meeting.add_transcript_segment(
        TranscriptSegment(
            1,
            "We agree to review the draft.",
            Speaker("Counsel"),
            TranscriptTimestamp(0, 4),
        )
    )

    with pytest.raises(InvariantViolation, match="sequence"):
        meeting.add_transcript_segment(TranscriptSegment(3, "Skipped segment"))

    meeting.complete_transcription()
    assert meeting.status.value == "ready"


def test_document_versions_cannot_change_after_completion_or_legal_hold() -> None:
    document = Document(
        "Agreement",
        FileName("agreement.pdf"),
        MimeType("application/pdf"),
        _hash(),
    )
    version = document.add_version(StorageKey("matter/agreement-v1.pdf"))
    version.start_processing()
    version.add_segment(DocumentSegment("A clause.", _hash(), page_number=1))
    version.complete_processing()

    with pytest.raises(ValueError, match="cannot receive"):
        version.add_segment(DocumentSegment("Another clause.", _hash()))

    document.apply_legal_hold()
    with pytest.raises(ValueError, match="legal hold"):
        document.add_version(StorageKey("matter/agreement-v2.pdf"))


def test_analysis_requires_evidence_for_material_items_and_review_before_approval() -> None:
    analysis = LegalAnalysis(AnalysisType.FULL_MEETING)
    analysis.begin_processing()
    risk = Risk(
        "Indemnity exposure",
        "The proposed wording expands liability.",
        RiskLevel.HIGH,
        ConfidenceScore(0.9),
        (_citation(),),
    )
    analysis.add_item(risk)
    analysis.set_summary("The meeting identified one material legal risk.")
    analysis.mark_ready_for_review()
    analysis.approve()

    assert analysis.status.value == "approved"

    with pytest.raises(MissingEvidence):
        Obligation(
            "Send notice",
            "Send the notice to the counterparty.",
            ResponsibleParty("Legal team"),
            None,
            ConfidenceScore(0.8),
        )


def test_action_item_requires_deadline_to_complete() -> None:
    item = ActionItem(
        "Review draft",
        "Review the revised agreement.",
        ResponsibleParty("Counsel"),
        ConfidenceScore(0.8),
    )
    with pytest.raises(MissingEvidence):
        item.complete()

    item.assign_deadline(Deadline(date(2026, 9, 1), ResponsibleParty("Counsel")))
    item.complete()
    assert item.status.value == "completed"


def test_redline_requires_human_review_before_export() -> None:
    job = RedlineJob()
    job.begin_processing()
    change = RedlineChange(
        ClausePath("4.2 Indemnity"),
        ChangeType.SUBSTITUTION,
        "The supplier is liable.",
        ProposedText("The supplier is liable only for direct losses."),
        Rationale("Limits exposure to direct losses."),
        ConfidenceScore(0.86),
    )
    job.add_change(change)
    job.mark_ready_for_review()

    with pytest.raises(UnsafeRedlineOperation, match="pending"):
        job.mark_reviewed()

    change.approve()
    job.mark_reviewed()
    job.export()
    assert job.status.value == "exported"


def test_report_requires_ordered_sections_and_can_export() -> None:
    report = LegalReport(ReportTitle("Meeting report"))
    report.begin_generation()
    report.add_section(ReportSection("Summary", "The parties agreed to proceed.", 1))
    report.mark_ready()
    report.approve()
    report.export(ReportFormat.PDF)

    assert ReportFormat.PDF in report.exported_formats
    assert report.status.value == "exported"
