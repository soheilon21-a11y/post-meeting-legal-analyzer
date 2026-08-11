from __future__ import annotations

import pytest

from app.application.ports.tokenization import ContextWindowPort
from app.application.ports.tokenization import TokenizerPort
from app.domain.ai.value_objects import ContextWindow
from app.domain.ai.value_objects import TokenCount


class FakeTokenizer(TokenizerPort):
    async def count(self, text: str) -> TokenCount:
        return TokenCount(len(text.split()))

    async def truncate(self, text: str, limit: TokenCount) -> str:
        words = text.split()
        return " ".join(words[: limit.value])


class FakeContextWindow(ContextWindowPort):
    async def capacity(self, model_name: str) -> ContextWindow:
        return ContextWindow(4096)


@pytest.mark.anyio
async def test_tokenizer_port_count_contract() -> None:
    tokenizer: TokenizerPort = FakeTokenizer()
    result = await tokenizer.count("hello world")
    assert result == TokenCount(2)


@pytest.mark.anyio
async def test_tokenizer_port_truncate_contract() -> None:
    tokenizer: TokenizerPort = FakeTokenizer()
    result = await tokenizer.truncate("one two three four", TokenCount(2))
    assert result == "one two"


@pytest.mark.anyio
async def test_context_window_port_capacity_contract() -> None:
    window: ContextWindowPort = FakeContextWindow()
    result = await window.capacity("llama3.2")
    assert result == ContextWindow(4096)
