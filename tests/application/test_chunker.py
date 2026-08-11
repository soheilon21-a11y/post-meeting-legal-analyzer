from __future__ import annotations

from typing import ClassVar

import pytest

from app.application.ports.tokenization import TokenizerPort
from app.application.services.chunker import Chunker
from app.domain.ai.value_objects import TokenCount
from app.domain.document.entities import DocumentSegment
from app.domain.document.value_objects import ContentHash
from app.domain.document.value_objects import SectionPath
from app.domain.meeting.entities import TranscriptSegment
from app.domain.meeting.value_objects import Speaker
from app.infrastructure.ai.tokenizers.simple_tokenizer import SimpleTokenizer


class SpyTokenizer(TokenizerPort):
    """Spy tokenizer that records every *count* call."""

    calls: ClassVar[list[str]] = []

    async def count(self, text: str) -> TokenCount:
        self.calls.append(text)
        return TokenCount(len(text.split()))

    async def truncate(self, text: str, limit: TokenCount) -> str:
        return text


@pytest.fixture
def chunker() -> Chunker:
    return Chunker(SimpleTokenizer())


@pytest.fixture
def limited_chunker() -> Chunker:
    return Chunker(SimpleTokenizer(), max_tokens_per_chunk=3)


@pytest.mark.anyio
async def test_empty_transcript(chunker: Chunker) -> None:
    result = await chunker.chunk_transcript([], source_id="m1")
    assert result == []


@pytest.mark.anyio
async def test_single_transcript_segment(chunker: Chunker) -> None:
    seg = TranscriptSegment(sequence_number=1, text="Hello world.")
    result = await chunker.chunk_transcript([seg], source_id="m1")
    assert len(result) == 1
    assert result[0].text == "Hello world."
    assert result[0].metadata.source_type == "transcript"
    assert result[0].metadata.source_id == "m1"
    assert result[0].metadata.sequence_start == 1
    assert result[0].metadata.sequence_end == 1


@pytest.mark.anyio
async def test_same_speaker_grouping(chunker: Chunker) -> None:
    seg1 = TranscriptSegment(sequence_number=1, text="Hello.", speaker=Speaker("Alice"))
    seg2 = TranscriptSegment(sequence_number=2, text="How are you?", speaker=Speaker("Alice"))
    result = await chunker.chunk_transcript([seg1, seg2], source_id="m1")
    assert len(result) == 1
    assert result[0].text == "Hello.\nHow are you?"
    assert result[0].metadata.speaker == "Alice"
    assert result[0].metadata.sequence_start == 1
    assert result[0].metadata.sequence_end == 2


@pytest.mark.anyio
async def test_speaker_change_splitting(chunker: Chunker) -> None:
    seg1 = TranscriptSegment(sequence_number=1, text="Hello.", speaker=Speaker("Alice"))
    seg2 = TranscriptSegment(sequence_number=2, text="Hi there.", speaker=Speaker("Bob"))
    result = await chunker.chunk_transcript([seg1, seg2], source_id="m1")
    assert len(result) == 2
    assert result[0].text == "Hello."
    assert result[0].metadata.speaker == "Alice"
    assert result[1].text == "Hi there."
    assert result[1].metadata.speaker == "Bob"


@pytest.mark.anyio
async def test_document_paragraph_grouping(chunker: Chunker) -> None:
    hash_val = ContentHash("a" * 64)
    seg1 = DocumentSegment(text="First para.", content_hash=hash_val, paragraph_number=1)
    seg2 = DocumentSegment(text="Still first.", content_hash=hash_val, paragraph_number=1)
    seg3 = DocumentSegment(text="Second para.", content_hash=hash_val, paragraph_number=2)
    result = await chunker.chunk_document([seg1, seg2, seg3], source_id="d1")
    assert len(result) == 2
    assert result[0].text == "First para.\nStill first."
    assert result[0].metadata.paragraph_number == 1
    assert result[1].text == "Second para."
    assert result[1].metadata.paragraph_number == 2


@pytest.mark.anyio
async def test_document_section_grouping(chunker: Chunker) -> None:
    hash_val = ContentHash("a" * 64)
    seg1 = DocumentSegment(text="Sec A.", content_hash=hash_val, section_path=SectionPath("A"))
    seg2 = DocumentSegment(text="Sec B.", content_hash=hash_val, section_path=SectionPath("B"))
    result = await chunker.chunk_document([seg1, seg2], source_id="d1")
    assert len(result) == 2
    assert result[0].metadata.section_path == "A"
    assert result[1].metadata.section_path == "B"


@pytest.mark.anyio
async def test_token_limit_splitting(limited_chunker: Chunker) -> None:
    # Each sentence is 1 token with SimpleTokenizer. max_tokens=3
    seg = TranscriptSegment(sequence_number=1, text="One. Two. Three. Four. Five.")
    result = await limited_chunker.chunk_transcript([seg], source_id="m1")
    assert len(result) == 2
    # Chunk value object strips trailing whitespace via ensure_not_blank
    assert result[0].text == "One. Two. Three."
    assert result[1].text == "Four. Five."


@pytest.mark.anyio
async def test_exact_token_boundary() -> None:
    # 3 sentences, max=3 -> exactly 1 chunk
    chunker = Chunker(SimpleTokenizer(), max_tokens_per_chunk=3)
    seg = TranscriptSegment(sequence_number=1, text="One. Two. Three.")
    result = await chunker.chunk_transcript([seg], source_id="m1")
    assert len(result) == 1
    assert result[0].text == "One. Two. Three."


@pytest.mark.anyio
async def test_under_limit_context(chunker: Chunker) -> None:
    # No max_tokens configured -> one chunk regardless of size
    seg = TranscriptSegment(sequence_number=1, text="This is a longer sentence with many words.")
    result = await chunker.chunk_transcript([seg], source_id="m1")
    assert len(result) == 1


@pytest.mark.anyio
async def test_oversized_single_sentence_preserved() -> None:
    chunker = Chunker(SimpleTokenizer(), max_tokens_per_chunk=1)
    # "One two." is 2 tokens, exceeding limit of 1
    seg = TranscriptSegment(sequence_number=1, text="One two.")
    result = await chunker.chunk_transcript([seg], source_id="m1")
    assert len(result) == 1
    assert result[0].text == "One two."


@pytest.mark.anyio
async def test_tokenizer_delegation() -> None:
    class FixedTokenizer(TokenizerPort):
        async def count(self, text: str) -> TokenCount:
            return TokenCount(99)

        async def truncate(self, text: str, limit: TokenCount) -> str:
            return text

    chunker = Chunker(FixedTokenizer(), max_tokens_per_chunk=50)
    seg = TranscriptSegment(sequence_number=1, text="Short.")
    # FixedTokenizer says 99 tokens for everything, so "Short." is oversized
    # It should be preserved as its own chunk
    result = await chunker.chunk_transcript([seg], source_id="m1")
    assert len(result) == 1
    assert result[0].text == "Short."


@pytest.mark.anyio
async def test_zero_tokenizer_calls_when_no_limit() -> None:
    spy = SpyTokenizer()
    spy.calls.clear()
    chunker = Chunker(spy)
    seg = TranscriptSegment(sequence_number=1, text="Hello world.")
    await chunker.chunk_transcript([seg], source_id="m1")
    assert spy.calls == []


@pytest.mark.anyio
async def test_sequence_metadata_preserved(chunker: Chunker) -> None:
    seg1 = TranscriptSegment(sequence_number=1, text="A.")
    seg2 = TranscriptSegment(sequence_number=2, text="B.")
    seg3 = TranscriptSegment(sequence_number=3, text="C.")
    result = await chunker.chunk_transcript([seg1, seg2, seg3], source_id="m1")
    # All same speaker (None), so grouped together
    assert len(result) == 1
    assert result[0].metadata.sequence_start == 1
    assert result[0].metadata.sequence_end == 3


@pytest.mark.anyio
async def test_speaker_metadata_preserved(chunker: Chunker) -> None:
    seg = TranscriptSegment(sequence_number=1, text="Hello.", speaker=Speaker("Alice"))
    result = await chunker.chunk_transcript([seg], source_id="m1")
    assert result[0].metadata.speaker == "Alice"


@pytest.mark.anyio
async def test_document_section_metadata_preserved(chunker: Chunker) -> None:
    hash_val = ContentHash("a" * 64)
    seg = DocumentSegment(text="Content.", content_hash=hash_val, section_path=SectionPath("1.2.3"))
    result = await chunker.chunk_document([seg], source_id="d1")
    assert result[0].metadata.section_path == "1.2.3"


@pytest.mark.anyio
async def test_deterministic_idempotent_output(chunker: Chunker) -> None:
    seg1 = TranscriptSegment(sequence_number=1, text="Hello.", speaker=Speaker("Alice"))
    seg2 = TranscriptSegment(sequence_number=2, text="World.", speaker=Speaker("Alice"))
    result1 = await chunker.chunk_transcript([seg1, seg2], source_id="m1")
    result2 = await chunker.chunk_transcript([seg1, seg2], source_id="m1")
    assert result1 == result2


@pytest.mark.anyio
async def test_compatibility_with_context_optimizer() -> None:
    from app.application.ports.tokenization import ContextWindowPort
    from app.application.services.context_optimizer import ContextOptimizer
    from app.domain.ai.value_objects import ContextWindow

    class FakeWindow(ContextWindowPort):
        async def capacity(self, model_name: str) -> ContextWindow:
            return ContextWindow(1000)

    chunker = Chunker(SimpleTokenizer(), max_tokens_per_chunk=10)
    segs = [
        TranscriptSegment(sequence_number=1, text="One. Two. Three."),
        TranscriptSegment(sequence_number=2, text="Four. Five. Six."),
    ]
    chunks = await chunker.chunk_transcript(segs, source_id="m1")
    texts = [c.text for c in chunks]

    optimizer = ContextOptimizer(SimpleTokenizer(), FakeWindow())
    result = await optimizer.optimize(texts, model_name="test", max_input=100)
    assert result.items == tuple(texts)
