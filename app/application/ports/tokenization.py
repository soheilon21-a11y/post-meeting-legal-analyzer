from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol
from typing import runtime_checkable

if TYPE_CHECKING:
    from app.domain.ai.value_objects import ContextWindow
    from app.domain.ai.value_objects import TokenCount


@runtime_checkable
class TokenizerPort(Protocol):
    """Abstract tokenizer for counting and truncating text outside the domain."""

    async def count(self, text: str) -> TokenCount:
        """Return the token count for the supplied text."""

    async def truncate(self, text: str, limit: TokenCount) -> str:
        """Return text truncated to fit within the supplied token limit."""


@runtime_checkable
class ContextWindowPort(Protocol):
    """Abstract provider of model context-window capacities."""

    async def capacity(self, model_name: str) -> ContextWindow:
        """Return the context-window capacity for the named model."""
