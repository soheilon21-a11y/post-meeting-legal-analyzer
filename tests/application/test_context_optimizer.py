from __future__ import annotations

from typing import ClassVar

import pytest

from app.application.ports.tokenization import ContextWindowPort
from app.application.ports.tokenization import TokenizerPort
from app.application.services.context_optimizer import ContextOptimizer
from app.domain.ai.services.token_optimizer import OptimizationDecision
from app.domain.ai.value_objects import ContextWindow
from app.domain.ai.value_objects import TokenCount
from app.domain.exceptions.invariant import InvariantViolation


class FakeTokenizer(TokenizerPort):
    """Fake tokenizer that counts words as tokens for deterministic tests."""

    async def count(self, text: str) -> TokenCount:
        return TokenCount(len(text.split()))

    async def truncate(self, text: str, limit: TokenCount) -> str:
        words = text.split()
        return " ".join(words[: limit.value])


class FakeContextWindow(ContextWindowPort):
    def __init__(self, capacity: int = 4096) -> None:
        self._capacity = capacity

    async def capacity(self, model_name: str) -> ContextWindow:
        return ContextWindow(self._capacity)


@pytest.fixture
def optimizer() -> ContextOptimizer:
    return ContextOptimizer(FakeTokenizer(), FakeContextWindow())


@pytest.mark.anyio
async def test_context_within_budget_remains_unchanged(optimizer: ContextOptimizer) -> None:
    result = await optimizer.optimize(
        ["one two", "three four five"],
        model_name="test-model",
        max_input=100,
    )

    assert result.decision is OptimizationDecision.KEEP
    assert result.items == ("one two", "three four five")
    assert result.original_token_count == TokenCount(5)
    assert result.optimized_token_count == TokenCount(5)


@pytest.mark.anyio
async def test_token_counts_obtained_through_tokenizer_port() -> None:
    class SpyTokenizer(TokenizerPort):
        calls: ClassVar[list[str]] = []

        async def count(self, text: str) -> TokenCount:
            self.calls.append(text)
            return TokenCount(1)

        async def truncate(self, text: str, limit: TokenCount) -> str:
            return text

    spy = SpyTokenizer()
    opt = ContextOptimizer(spy, FakeContextWindow())
    await opt.optimize(["a", "b"], model_name="m")

    assert spy.calls == ["a", "b"]


@pytest.mark.anyio
async def test_context_window_obtained_through_port() -> None:
    class SpyWindow(ContextWindowPort):
        calls: ClassVar[list[str]] = []

        async def capacity(self, model_name: str) -> ContextWindow:
            self.calls.append(model_name)
            return ContextWindow(100)

    spy = SpyWindow()
    opt = ContextOptimizer(FakeTokenizer(), spy)
    await opt.optimize(["x"], model_name="model-a")

    assert spy.calls == ["model-a"]


@pytest.mark.anyio
async def test_reserved_output_respected(optimizer: ContextOptimizer) -> None:
    result = await optimizer.optimize(
        ["one two three", "four five"],
        model_name="test-model",
        max_input=10,
        reserved_output=7,
    )

    # available_for_input is 3, so only first item fits
    assert result.decision is OptimizationDecision.EXCLUDE
    assert result.items == ("one two three",)
    assert result.optimized_token_count == TokenCount(3)


@pytest.mark.anyio
async def test_lower_priority_excluded_when_necessary(optimizer: ContextOptimizer) -> None:
    result = await optimizer.optimize(
        [
            "one two three",
            "four five six",
            "seven eight nine",
        ],
        model_name="test-model",
        max_input=8,
    )

    assert result.decision is OptimizationDecision.EXCLUDE
    assert result.items == ("one two three", "four five six")
    assert result.original_token_count == TokenCount(9)
    assert result.optimized_token_count == TokenCount(6)


@pytest.mark.anyio
async def test_oversized_first_item_rejected(optimizer: ContextOptimizer) -> None:
    result = await optimizer.optimize(
        ["a b c d e f g h i j k"],
        model_name="test-model",
        max_input=5,
    )

    assert result.decision is OptimizationDecision.REJECT
    assert result.items == ()
    assert result.optimized_token_count == TokenCount(0)


@pytest.mark.anyio
async def test_service_does_not_count_tokens_itself() -> None:
    class FixedTokenizer(TokenizerPort):
        async def count(self, text: str) -> TokenCount:
            return TokenCount(99)

        async def truncate(self, text: str, limit: TokenCount) -> str:
            return text

    opt = ContextOptimizer(FixedTokenizer(), FakeContextWindow())
    result = await opt.optimize(["short"], model_name="m", max_input=200)

    assert result.original_token_count == TokenCount(99)
    assert result.optimized_token_count == TokenCount(99)


@pytest.mark.anyio
async def test_result_is_immutable(optimizer: ContextOptimizer) -> None:
    result = await optimizer.optimize(["x"], model_name="m", max_input=100)

    with pytest.raises(TypeError):
        result.items[0] = "y"  # type: ignore[index]


@pytest.mark.anyio
async def test_model_name_passed_through(optimizer: ContextOptimizer) -> None:
    result = await optimizer.optimize(["x"], model_name="llama3.2", max_input=100)

    assert result.model_name == "llama3.2"


@pytest.mark.anyio
async def test_context_window_capacity_in_result(optimizer: ContextOptimizer) -> None:
    opt = ContextOptimizer(FakeTokenizer(), FakeContextWindow(capacity=2048))
    result = await opt.optimize(["x"], model_name="m", max_input=100)

    assert result.context_window_capacity == 2048


@pytest.mark.anyio
async def test_max_input_override_smaller_than_window() -> None:
    opt = ContextOptimizer(FakeTokenizer(), FakeContextWindow(capacity=100))
    result = await opt.optimize(
        ["one two three four five"],
        model_name="m",
        max_input=50,
    )

    assert result.decision is OptimizationDecision.KEEP
    assert result.optimized_token_count == TokenCount(5)


@pytest.mark.anyio
async def test_max_input_exceeds_window_raises() -> None:
    opt = ContextOptimizer(FakeTokenizer(), FakeContextWindow(capacity=50))

    with pytest.raises(InvariantViolation, match="exceeds context window"):
        await opt.optimize(["x"], model_name="m", max_input=100)
