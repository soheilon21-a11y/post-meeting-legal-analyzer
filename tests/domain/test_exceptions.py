from __future__ import annotations

from app.domain.exceptions import DomainAccessViolation
from app.domain.exceptions import DomainError
from app.domain.exceptions import InvalidStateTransition
from app.domain.exceptions import MissingEvidence
from app.domain.exceptions import UnsafeRedlineOperation


def test_domain_exceptions_expose_stable_codes_and_context() -> None:
    exceptions = (
        DomainAccessViolation("user", "matter", "read"),
        InvalidStateTransition("Analysis", "pending", "approved"),
        MissingEvidence("risk assessment", ["meeting transcript"]),
        UnsafeRedlineOperation("approve", "high-risk changes require review"),
    )

    assert all(isinstance(error, DomainError) for error in exceptions)
    assert all(error.code for error in exceptions)
    assert all(error.context for error in exceptions)
