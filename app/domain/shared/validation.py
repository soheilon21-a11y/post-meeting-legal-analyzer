from __future__ import annotations

from uuid import UUID

from app.domain.exceptions.invariant import InvariantViolation


def ensure_not_blank(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise InvariantViolation(f"{field_name} must not be blank", field_name=field_name)
    return normalized


def ensure_positive(value: int | float, field_name: str) -> int | float:
    if value <= 0:
        raise InvariantViolation(f"{field_name} must be greater than zero", field_name=field_name)
    return value


def ensure_non_negative(value: int | float, field_name: str) -> int | float:
    if value < 0:
        raise InvariantViolation(f"{field_name} must not be negative", field_name=field_name)
    return value


def ensure_in_range(value: float, minimum: float, maximum: float, field_name: str) -> float:
    if not minimum <= value <= maximum:
        raise InvariantViolation(
            f"{field_name} must be between {minimum} and {maximum}",
            field_name=field_name,
        )
    return value


def ensure_uuid(value: UUID, field_name: str) -> UUID:
    if not isinstance(value, UUID):
        raise InvariantViolation(f"{field_name} must be a UUID", field_name=field_name)
    return value
