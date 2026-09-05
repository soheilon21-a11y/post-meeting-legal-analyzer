from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IndexedChunk:
    chunk_id: str
    matter_id: str
    source_id: str
    text: str
    vector: tuple[float, ...]
    page_number: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None


@dataclass(frozen=True, slots=True)
class VectorHit:
    chunk_id: str
    source_id: str
    text: str
    score: float
    page_number: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None
