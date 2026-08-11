from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import TypeVar

from app.domain.chunking.value_objects import Chunk
from app.domain.chunking.value_objects import ChunkMetadata

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence

    from app.application.ports.tokenization import TokenizerPort
    from app.domain.document.entities import DocumentSegment
    from app.domain.meeting.entities import TranscriptSegment

_T = TypeVar("_T")
_K = TypeVar("_K")


def _group_consecutive(items: Sequence[_T], key: Callable[[_T], _K]) -> list[list[_T]]:
    """Group consecutive items that share the same key value."""
    if not items:
        return []
    groups: list[list[_T]] = []
    current: list[_T] = [items[0]]
    current_key = key(items[0])
    for item in items[1:]:
        item_key = key(item)
        if item_key == current_key:
            current.append(item)
        else:
            groups.append(current)
            current = [item]
            current_key = item_key
    groups.append(current)
    return groups


class Chunker:
    """Deterministic application service for splitting transcript and document
    segments into semantically meaningful chunks.

    When *max_tokens_per_chunk* is configured, the service delegates token
    counting to the injected ``TokenizerPort`` and splits at sentence
    boundaries.  It never truncates text inside the chunker; oversized
    sentences are preserved as single chunks.
    """

    def __init__(
        self,
        tokenizer: TokenizerPort,
        *,
        max_tokens_per_chunk: int | None = None,
    ) -> None:
        self._tokenizer = tokenizer
        self._max_tokens = max_tokens_per_chunk

    async def chunk_transcript(
        self,
        segments: Sequence[TranscriptSegment],
        source_id: str,
    ) -> list[Chunk]:
        """Group consecutive transcript segments by speaker and split at
        sentence boundaries when a token limit is configured."""
        if not segments:
            return []

        groups = _group_consecutive(segments, key=lambda s: s.speaker)
        chunks: list[Chunk] = []

        for group in groups:
            text = "\n".join(seg.text for seg in group)
            speaker_str = group[0].speaker.value if group[0].speaker else None

            metadata = ChunkMetadata(
                source_type="transcript",
                source_id=source_id,
                speaker=speaker_str,
                sequence_start=group[0].sequence_number,
                sequence_end=group[-1].sequence_number,
            )

            if self._max_tokens is not None:
                chunk_texts = await self._split_at_sentence_boundaries(text, self._max_tokens)
            else:
                chunk_texts = [text]

            for chunk_text in chunk_texts:
                chunks.append(Chunk(text=chunk_text, metadata=metadata))

        return chunks

    async def chunk_document(
        self,
        segments: Sequence[DocumentSegment],
        source_id: str,
    ) -> list[Chunk]:
        """Group consecutive document segments by paragraph/section structure
        and split at sentence boundaries when a token limit is configured."""
        if not segments:
            return []

        groups = _group_consecutive(
            segments,
            key=lambda s: (s.paragraph_number, s.section_path),
        )
        chunks: list[Chunk] = []

        for group in groups:
            text = "\n".join(seg.text for seg in group)
            section_path_str = group[0].section_path.value if group[0].section_path else None

            metadata = ChunkMetadata(
                source_type="document",
                source_id=source_id,
                section_path=section_path_str,
                page_number=group[0].page_number,
                paragraph_number=group[0].paragraph_number,
            )

            if self._max_tokens is not None:
                chunk_texts = await self._split_at_sentence_boundaries(text, self._max_tokens)
            else:
                chunk_texts = [text]

            for chunk_text in chunk_texts:
                chunks.append(Chunk(text=chunk_text, metadata=metadata))

        return chunks

    async def _split_at_sentence_boundaries(
        self,
        text: str,
        max_tokens: int,
    ) -> list[str]:
        """Split *text* into chunks that each fit within *max_tokens*.

        Splits occur at sentence boundaries (after ``.!?``).  If a single
        sentence exceeds the limit it is preserved as one oversized chunk.
        """
        if not text:
            return [text]

        # Identify sentence boundaries, consuming trailing whitespace.
        ends = [m.end() for m in re.finditer(r"[.!?]\s*", text)]
        if not ends:
            return [text]
        if ends[-1] < len(text):
            ends.append(len(text))

        sentences: list[str] = []
        start = 0
        for end in ends:
            sentences.append(text[start:end])
            start = end

        chunks: list[str] = []
        current_sentences: list[str] = []
        current_token_count = 0

        for sentence in sentences:
            sentence_tokens = await self._tokenizer.count(sentence)

            if sentence_tokens.value > max_tokens:
                if current_sentences:
                    chunks.append("".join(current_sentences))
                    current_sentences = []
                    current_token_count = 0
                chunks.append(sentence)
                continue

            if current_token_count + sentence_tokens.value > max_tokens and current_sentences:
                chunks.append("".join(current_sentences))
                current_sentences = [sentence]
                current_token_count = sentence_tokens.value
            else:
                current_sentences.append(sentence)
                current_token_count += sentence_tokens.value

        if current_sentences:
            chunks.append("".join(current_sentences))

        return chunks
