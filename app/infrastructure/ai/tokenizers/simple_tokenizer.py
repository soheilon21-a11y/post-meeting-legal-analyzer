from __future__ import annotations

from app.application.ports.tokenization import TokenizerPort
from app.domain.ai.value_objects import TokenCount


class SimpleTokenizer(TokenizerPort):
    """Lightweight deterministic tokenizer using whitespace splitting.

    Suitable for unit tests, fallback scenarios, and environments where
    downloading a full HuggingFace tokenizer is undesirable.
    """

    async def count(self, text: str) -> TokenCount:
        if not text.strip():
            return TokenCount(0)
        return TokenCount(len(text.split()))

    async def truncate(self, text: str, limit: TokenCount) -> str:
        words = text.split()
        if limit.value >= len(words):
            return text
        return " ".join(words[: limit.value])
