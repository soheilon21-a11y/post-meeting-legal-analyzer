from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Generic
from typing import TypeVar

if TYPE_CHECKING:
    from app.application.dtos.base import PageInfo

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PageResponse(Generic[T]):
    items: tuple[T, ...]
    page: PageInfo
