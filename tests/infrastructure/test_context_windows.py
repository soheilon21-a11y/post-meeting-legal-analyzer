from __future__ import annotations

import pytest

from app.domain.ai.value_objects import ContextWindow
from app.infrastructure.ai.context_windows.static_registry import StaticContextWindowRegistry


@pytest.mark.anyio
class TestStaticContextWindowRegistry:
    async def test_known_model_llama32(self) -> None:
        registry = StaticContextWindowRegistry()
        result = await registry.capacity("llama3.2")
        assert result == ContextWindow(128_000)

    async def test_known_model_mistral(self) -> None:
        registry = StaticContextWindowRegistry()
        result = await registry.capacity("mistral")
        assert result == ContextWindow(32_000)

    async def test_known_model_nomic(self) -> None:
        registry = StaticContextWindowRegistry()
        result = await registry.capacity("nomic-embed-text")
        assert result == ContextWindow(2_048)

    async def test_unknown_model_returns_default(self) -> None:
        registry = StaticContextWindowRegistry()
        result = await registry.capacity("unknown-model-v99")
        assert result == ContextWindow(4_096)

    async def test_custom_default(self) -> None:
        registry = StaticContextWindowRegistry(default_capacity=8_192)
        result = await registry.capacity("unknown-model")
        assert result == ContextWindow(8_192)

    async def test_implements_context_window_port(self) -> None:
        from app.application.ports.tokenization import ContextWindowPort

        assert isinstance(StaticContextWindowRegistry(), ContextWindowPort)

    def test_register_new_model(self) -> None:
        StaticContextWindowRegistry.register("custom-model", 16_384)
        # Async test wrapper

    @pytest.mark.anyio
    async def test_registered_model_is_resolved(self) -> None:
        # Use a unique name to avoid collisions with other tests
        StaticContextWindowRegistry.register("test-custom-42", 16_384)
        registry = StaticContextWindowRegistry()
        result = await registry.capacity("test-custom-42")
        assert result == ContextWindow(16_384)

    def test_register_zero_capacity_rejected(self) -> None:
        with pytest.raises(ValueError, match="capacity must be positive"):
            StaticContextWindowRegistry.register("bad", 0)

    def test_register_negative_capacity_rejected(self) -> None:
        with pytest.raises(ValueError, match="capacity must be positive"):
            StaticContextWindowRegistry.register("bad", -1)

    def test_default_zero_capacity_rejected(self) -> None:
        with pytest.raises(ValueError, match="default_capacity must be positive"):
            StaticContextWindowRegistry(default_capacity=0)

    async def test_context_window_is_positive(self) -> None:
        registry = StaticContextWindowRegistry()
        result = await registry.capacity("llama3.2")
        assert result.capacity > 0
