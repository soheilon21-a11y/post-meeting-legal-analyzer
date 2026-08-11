from app.domain.analysis.enums import AnalysisStatus
from app.domain.analysis.enums import ItemStatus
from app.domain.analysis.enums import RiskLevel
from app.domain.exceptions.evidence import MissingEvidence
from app.domain.exceptions.lifecycle import InvalidStateTransition


def ensure_analysis_can_change(status: AnalysisStatus) -> None:
    if status in (AnalysisStatus.APPROVED, AnalysisStatus.REJECTED):
        raise InvalidStateTransition("LegalAnalysis", status, AnalysisStatus.DRAFT)


def ensure_analysis_can_be_approved(status: AnalysisStatus, item_count: int) -> None:
    if status is not AnalysisStatus.READY_FOR_REVIEW:
        raise InvalidStateTransition("LegalAnalysis", status, AnalysisStatus.APPROVED)
    if item_count == 0:
        raise MissingEvidence("analysis", ["meeting transcript or document source"])


def ensure_material_item_has_evidence(risk_level: RiskLevel, citation_count: int) -> None:
    if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL) and citation_count == 0:
        raise MissingEvidence("material legal item", ["source citation"])


def ensure_item_can_complete(status: ItemStatus, deadline_present: bool) -> None:
    if status is ItemStatus.DISMISSED:
        raise InvalidStateTransition("AnalysisItem", status, ItemStatus.COMPLETED)
    if not deadline_present:
        raise MissingEvidence("completed action item", ["deadline"])
