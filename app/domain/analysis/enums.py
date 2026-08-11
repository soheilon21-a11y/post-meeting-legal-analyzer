from enum import StrEnum


class AnalysisType(StrEnum):
    FULL_MEETING = "full_meeting"
    EXECUTIVE_SUMMARY = "executive_summary"
    LEGAL_SUMMARY = "legal_summary"
    RISK_ASSESSMENT = "risk_assessment"
    OBLIGATION_EXTRACTION = "obligation_extraction"


class AnalysisStatus(StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ItemStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
