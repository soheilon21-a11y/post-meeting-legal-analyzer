from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.ports.tokenization import TokenizerPort
from app.domain.ai.value_objects import TokenCount

if TYPE_CHECKING:
    from transformers import AutoTokenizer


class HuggingFaceTokenizer(TokenizerPort):
    """Tokenizer adapter backed by a HuggingFace AutoTokenizer.

    Lazily loads the tokenizer on first use to avoid import-time
    side effects and unnecessary downloads during module import.
    """

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._tokenizer: AutoTokenizer | None = None

    def _load(self) -> AutoTokenizer:
        if self._tokenizer is None:
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
        return self._tokenizer

    async def count(self, text: str) -> TokenCount:
        tokenizer = self._load()
        encoded = tokenizer.encode(text, add_special_tokens=False)
        return TokenCount(len(encoded))

    async def truncate(self, text: str, limit: TokenCount) -> str:
        tokenizer = self._load()
        encoded = tokenizer.encode(text, add_special_tokens=False)
        if limit.value >= len(encoded):
            return text
        truncated = encoded[: limit.value]
        return tokenizer.decode(truncated, skip_special_tokens=True)
