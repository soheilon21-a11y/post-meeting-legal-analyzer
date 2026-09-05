from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol
from typing import runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence


@runtime_checkable
class EmbeddingPort(Protocol):
    """Abstract local embedding model for converting text into vectors."""

    async def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        """Return one embedding vector per supplied text, in order."""
