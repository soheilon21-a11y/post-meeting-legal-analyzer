from dataclasses import dataclass

from app.domain.shared.domain_event import DomainEvent
from app.domain.shared.identifiers import UserId


@dataclass(frozen=True, slots=True)
class AuthRegistered(DomainEvent):
    """A new user account (with its organization) was registered."""

    aggregate_id: UserId


@dataclass(frozen=True, slots=True)
class AuthLoginSuccess(DomainEvent):
    """A user authenticated successfully with valid credentials."""

    aggregate_id: UserId


@dataclass(frozen=True, slots=True)
class AuthLoginFailed(DomainEvent):
    """An authentication attempt against a known account failed."""

    aggregate_id: UserId
