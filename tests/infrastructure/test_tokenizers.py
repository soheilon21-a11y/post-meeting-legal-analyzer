from __future__ import annotations

import pytest

from app.domain.ai.value_objects import TokenCount
from app.infrastructure.ai.tokenizers.hf_tokenizer import HuggingFaceTokenizer
from app.infrastructure.ai.tokenizers.simple_tokenizer import SimpleTokenizer


@pytest.mark.anyio
class TestSimpleTokenizer:
    async def test_empty_text_returns_zero(self) -> None:
        tokenizer = SimpleTokenizer()
        assert await tokenizer.count("") == TokenCount(0)

    async def test_single_word(self) -> None:
        tokenizer = SimpleTokenizer()
        assert await tokenizer.count("hello") == TokenCount(1)

    async def test_multiple_words(self) -> None:
        tokenizer = SimpleTokenizer()
        assert await tokenizer.count("hello world foo bar") == TokenCount(4)

    async def test_whitespace_only(self) -> None:
        tokenizer = SimpleTokenizer()
        assert await tokenizer.count("   \n\t  ") == TokenCount(0)

    async def test_truncate_within_limit(self) -> None:
        tokenizer = SimpleTokenizer()
        result = await tokenizer.truncate("a b c d", TokenCount(10))
        assert result == "a b c d"

    async def test_truncate_at_exact_boundary(self) -> None:
        tokenizer = SimpleTokenizer()
        result = await tokenizer.truncate("a b c d", TokenCount(4))
        assert result == "a b c d"

    async def test_truncate_below_boundary(self) -> None:
        tokenizer = SimpleTokenizer()
        result = await tokenizer.truncate("a b c d", TokenCount(2))
        assert result == "a b"

    async def test_truncate_to_zero(self) -> None:
        tokenizer = SimpleTokenizer()
        result = await tokenizer.truncate("a b c", TokenCount(0))
        assert result == ""

    async def test_truncation_is_idempotent(self) -> None:
        tokenizer = SimpleTokenizer()
        first = await tokenizer.truncate("one two three four", TokenCount(2))
        second = await tokenizer.truncate(first, TokenCount(2))
        assert first == second

    async def test_implements_tokenizer_port(self) -> None:
        from app.application.ports.tokenization import TokenizerPort

        assert isinstance(SimpleTokenizer(), TokenizerPort)


class TestHuggingFaceTokenizer:
    def test_implements_tokenizer_port(self) -> None:
        from app.application.ports.tokenization import TokenizerPort

        tokenizer = HuggingFaceTokenizer("gpt2")
        assert isinstance(tokenizer, TokenizerPort)

    @pytest.mark.anyio
    async def test_counts_real_tokens(self) -> None:
        tokenizer = HuggingFaceTokenizer("gpt2")
        count = await tokenizer.count("hello world")
        # GPT-2 tokenizes "hello world" into 2 tokens
        assert count == TokenCount(2)

    @pytest.mark.anyio
    async def test_truncates_real_tokens(self) -> None:
        tokenizer = HuggingFaceTokenizer("gpt2")
        result = await tokenizer.truncate("hello world foo bar", TokenCount(2))
        # After truncation to 2 tokens, should contain only "hello world"
        count = await tokenizer.count(result)
        assert count == TokenCount(2)

    @pytest.mark.anyio
    async def test_truncate_noop_when_within_limit(self) -> None:
        tokenizer = HuggingFaceTokenizer("gpt2")
        text = "hi"
        result = await tokenizer.truncate(text, TokenCount(10))
        assert result == text

    @pytest.mark.anyio
    async def test_empty_text(self) -> None:
        tokenizer = HuggingFaceTokenizer("gpt2")
        assert await tokenizer.count("") == TokenCount(0)

    @pytest.mark.anyio
    async def test_lazily_loads_tokenizer(self) -> None:
        tokenizer = HuggingFaceTokenizer("gpt2")
        assert tokenizer._tokenizer is None
        await tokenizer.count("test")
        assert tokenizer._tokenizer is not None

    @pytest.mark.anyio
    async def test_handles_long_text(self) -> None:
        tokenizer = HuggingFaceTokenizer("gpt2")
        text = "word " * 1000
        count = await tokenizer.count(text)
        assert count.value > 500
        truncated = await tokenizer.truncate(text, TokenCount(10))
        truncated_count = await tokenizer.count(truncated)
        assert truncated_count == TokenCount(10)
