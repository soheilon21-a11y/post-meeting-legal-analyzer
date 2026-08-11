from app.domain.specifications.base import AndSpecification
from app.domain.specifications.base import NotSpecification
from app.domain.specifications.base import OrSpecification
from app.domain.specifications.base import PredicateSpecification
from app.domain.specifications.base import Specification
from app.domain.specifications.legal import AnalysisIsApproved
from app.domain.specifications.legal import AnalysisIsReadyForReview
from app.domain.specifications.legal import MatterHasLegalHold
from app.domain.specifications.legal import MatterIsActive
from app.domain.specifications.legal import MeetingIsReady
from app.domain.specifications.legal import RedlineIsReviewed
from app.domain.specifications.legal import ReportIsReady

__all__ = [
    "AnalysisIsApproved",
    "AnalysisIsReadyForReview",
    "AndSpecification",
    "MatterHasLegalHold",
    "MatterIsActive",
    "MeetingIsReady",
    "NotSpecification",
    "OrSpecification",
    "PredicateSpecification",
    "RedlineIsReviewed",
    "ReportIsReady",
    "Specification",
]
