from __future__ import annotations

from typing import Protocol
from typing import Self


class UnitOfWork(Protocol):
    """Transaction boundary for command handlers.

    Concrete repository attributes will be added by feature-specific Unit of Work
    contracts in later increments. This base protocol intentionally exposes no
    persistence technology.
    """

    async def __aenter__(self) -> Self: ...

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
