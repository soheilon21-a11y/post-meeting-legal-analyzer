from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.domain.exceptions import InvariantViolation
from app.domain.shared import AggregateRoot
from app.domain.shared import DomainEvent
from app.domain.shared import Entity
from app.domain.shared import ValueObject


class AggregateFixture(AggregateRoot):
    pass


@dataclass(frozen=True, slots=True)
class Email(ValueObject):
    value: str

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value,)


class Created(DomainEvent):
    pass


def test_entities_compare_by_type_and_identity() -> None:
    entity_id = uuid4()
    first = Entity(entity_id)
    second = Entity(entity_id)

    assert first == second
    assert hash(first) == hash(second)


def test_value_objects_compare_by_value() -> None:
    assert Email("law@example.test") == Email("law@example.test")
    assert Email("law@example.test") != Email("other@example.test")


def test_aggregate_records_and_pulls_events() -> None:
    aggregate = AggregateFixture()
    event = Created(aggregate_id=aggregate.id)

    aggregate.record_event(event)

    assert tuple(aggregate.pending_events()) == (event,)
    assert aggregate.pull_events() == (event,)
    assert tuple(aggregate.pending_events()) == ()


def test_aggregate_rejects_events_for_another_aggregate() -> None:
    aggregate = AggregateFixture()
    event = Created(aggregate_id=uuid4())

    with pytest.raises(ValueError, match="aggregate_id"):
        aggregate.record_event(event)


def test_validation_errors_are_domain_errors() -> None:
    from app.domain.shared.validation import ensure_not_blank

    with pytest.raises(InvariantViolation) as error:
        ensure_not_blank("  ", "title")

    assert error.value.code == "invariant_violation"
    assert error.value.context["field_name"] == "title"
