from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from datetime import datetime


class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current timezone-aware instant."""
