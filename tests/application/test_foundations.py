from __future__ import annotations

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from app.application.commands.base import Command
from app.application.dtos.base import ApplicationResult
from app.application.dtos.base import PageInfo
from app.application.dtos.base import PageRequest
from app.application.exceptions import ApplicationError
from app.application.exceptions import ApplicationValidationError
from app.application.exceptions import AuthorizationError
from app.application.exceptions import ConflictError
from app.application.exceptions import IntegrationBoundaryError
from app.application.exceptions import ProcessingError
from app.application.exceptions import ResourceNotFound
from app.application.queries.base import Query


def test_command_and_query_metadata_is_generated_and_immutable() -> None:
    command = Command()
    query = Query()

    assert command.message_id != uuid4()
    assert query.query_id != uuid4()

    with pytest.raises(FrozenInstanceError):
        command.message_id = uuid4()  # type: ignore[misc]


def test_pagination_dtos_validate_bounds_and_are_immutable() -> None:
    request = PageRequest(offset=10, limit=25)
    page = PageInfo(offset=request.offset, limit=request.limit, total=50)

    assert page.offset == 10
    assert page.total == 50

    with pytest.raises(ValueError, match="offset"):
        PageRequest(offset=-1)
    with pytest.raises(ValueError, match="limit"):
        PageRequest(limit=1001)
    with pytest.raises(FrozenInstanceError):
        page.total = 5  # type: ignore[misc]


def test_application_result_is_immutable() -> None:
    result = ApplicationResult(value="completed")

    assert result.value == "completed"
    with pytest.raises(FrozenInstanceError):
        result.value = "failed"  # type: ignore[misc]


def test_application_exceptions_are_stable_and_contextual() -> None:
    errors = (
        ResourceNotFound("Matter", "matter-1"),
        ApplicationValidationError("Invalid title", field="title"),
        AuthorizationError("read", "matter"),
        ConflictError("matter", "already exists"),
        ProcessingError("analysis", "failed"),
        IntegrationBoundaryError("retrieval", "unavailable"),
    )

    assert all(isinstance(error, ApplicationError) for error in errors)
    assert all(error.code for error in errors)
    assert all(error.context for error in errors)
