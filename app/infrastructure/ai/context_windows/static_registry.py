from __future__ import annotations

from typing import ClassVar

from app.application.ports.tokenization import ContextWindowPort
from app.domain.ai.value_objects import ContextWindow


class StaticContextWindowRegistry(ContextWindowPort):
    """Static, in-memory registry of known model context-window capacities.

    Safe for local-only deployments; unknown models default to a
    conservative capacity rather than raising an error.
    """

    _DEFAULT_CAPACITY = 4096

    _REGISTRY: ClassVar[dict[str, int]] = {
        "llama3.2": 128_000,
        "llama3.1": 128_000,
        "llama3": 8_192,
        "mistral": 32_000,
        "mistral-nemo": 128_000,
        "mixtral": 32_000,
        "gemma2": 8_192,
        "gemma": 8_192,
        "qwen2.5": 128_000,
        "phi3": 128_000,
        "nomic-embed-text": 2_048,
        "mxbai-embed-large": 512,
    }

    def __init__(self, default_capacity: int | None = None) -> None:
        if default_capacity is not None and default_capacity <= 0:
            raise ValueError("default_capacity must be positive")
        self._default = default_capacity or self._DEFAULT_CAPACITY

    async def capacity(self, model_name: str) -> ContextWindow:
        resolved = self._REGISTRY.get(model_name, self._default)
        return ContextWindow(resolved)

    @classmethod
    def register(cls, model_name: str, capacity: int) -> None:
        """Extend the registry with a new model at runtime."""
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        cls._REGISTRY[model_name] = capacity
