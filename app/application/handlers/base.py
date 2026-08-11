from __future__ import annotations

from typing import Protocol
from typing import TypeVar

CommandT_contra = TypeVar("CommandT_contra", contravariant=True)
QueryT_contra = TypeVar("QueryT_contra", contravariant=True)
ResultT_co = TypeVar("ResultT_co", covariant=True)


class CommandHandler(Protocol[CommandT_contra, ResultT_co]):
    async def handle(self, command: CommandT_contra) -> ResultT_co:
        """Execute one state-changing application operation."""


class QueryHandler(Protocol[QueryT_contra, ResultT_co]):
    async def handle(self, query: QueryT_contra) -> ResultT_co:
        """Execute one read-only application operation."""
