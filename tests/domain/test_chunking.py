from __future__ import annotations

import pytest

from app.domain.chunking.value_objects import Chunk
from app.domain.chunking.value_objects import ChunkMetadata
from app.domain.exceptions.invariant import InvariantViolation


class TestChunkMetadata:
    def test_valid(self) -> None:
        meta = ChunkMetadata(source_type="transcript", source_id="abc")
        assert meta.source_type == "transcript"
        assert meta.source_id == "abc"
        assert meta.speaker is None
        assert meta.sequence_start is None

    def test_equality(self) -> None:
        a = ChunkMetadata(source_type="doc", source_id="1", speaker="Alice")
        b = ChunkMetadata(source_type="doc", source_id="1", speaker="Alice")
        c = ChunkMetadata(source_type="doc", source_id="1", speaker="Bob")
        assert a == b
        assert a != c

    def test_optional_fields(self) -> None:
        meta = ChunkMetadata(
            source_type="document",
            source_id="x",
            speaker="Alice",
            sequence_start=1,
            sequence_end=5,
            section_path="1.2",
            page_number=3,
            paragraph_number=4,
        )
        assert meta.speaker == "Alice"
        assert meta.sequence_start == 1
        assert meta.sequence_end == 5
        assert meta.section_path == "1.2"
        assert meta.page_number == 3
        assert meta.paragraph_number == 4

    def test_blank_source_type_rejected(self) -> None:
        with pytest.raises(InvariantViolation):
            ChunkMetadata(source_type="  ", source_id="abc")

    def test_blank_source_id_rejected(self) -> None:
        with pytest.raises(InvariantViolation):
            ChunkMetadata(source_type="doc", source_id="  ")

    def test_negative_sequence_start_rejected(self) -> None:
        with pytest.raises(InvariantViolation):
            ChunkMetadata(source_type="doc", source_id="x", sequence_start=0)

    def test_negative_sequence_end_rejected(self) -> None:
        with pytest.raises(InvariantViolation):
            ChunkMetadata(source_type="doc", source_id="x", sequence_end=-1)

    def test_negative_page_number_rejected(self) -> None:
        with pytest.raises(InvariantViolation):
            ChunkMetadata(source_type="doc", source_id="x", page_number=0)

    def test_negative_paragraph_number_rejected(self) -> None:
        with pytest.raises(InvariantViolation):
            ChunkMetadata(source_type="doc", source_id="x", paragraph_number=-1)


class TestChunk:
    def test_valid(self) -> None:
        meta = ChunkMetadata(source_type="transcript", source_id="m1")
        chunk = Chunk(text="Hello world.", metadata=meta)
        assert chunk.text == "Hello world."
        assert chunk.metadata == meta

    def test_blank_text_rejected(self) -> None:
        meta = ChunkMetadata(source_type="transcript", source_id="m1")
        with pytest.raises(InvariantViolation):
            Chunk(text="   ", metadata=meta)

    def test_equality(self) -> None:
        meta = ChunkMetadata(source_type="doc", source_id="1")
        a = Chunk(text="Hello.", metadata=meta)
        b = Chunk(text="Hello.", metadata=meta)
        c = Chunk(text="World.", metadata=meta)
        assert a == b
        assert a != c
