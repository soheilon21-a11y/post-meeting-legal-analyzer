from __future__ import annotations

import asyncio
import json
from typing import Any

from app.application.dtos.internal.redline_generation import GeneratedRedlineChange
from app.application.dtos.internal.redline_generation import GeneratedRedlineCitation
from app.application.dtos.internal.redline_generation import RedlineGenerationInput
from app.application.dtos.internal.redline_generation import RedlineGenerationResult
from app.application.exceptions.processing import ProcessingError
from app.core.config import get_settings

OLLAMA_JSON_FORMAT = "json"


class OllamaRedlineGeneration:
    """Local Ollama adapter implementing RedlineGenerationPort.

    Generates structured redline changes through a local Ollama server.
    Consumes bounded RAG context via RedlineGenerationInput.context_items.

    Architecture:
    PostgreSQL/Qdrant → RAG retrieval → bounded context_items → Ollama →
    structured redline result → existing domain validation → human review.
    """

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._model_name = model_name or get_settings().ollama.legal_model
        self._base_url = base_url or get_settings().ollama.base_url
        self._timeout = get_settings().ollama.timeout_seconds
        self._max_retries = get_settings().ollama.max_retries
        self._client: Any | None = None

    async def generate(self, request: RedlineGenerationInput) -> RedlineGenerationResult:
        """Generate redline changes through local Ollama.

        Args:
            request: RedlineGenerationInput containing job ID, document IDs,
                deterministic seed, and bounded RAG context items.

        Returns:
            RedlineGenerationResult with generated changes and citations.

        Raises:
            ProcessingError: If Ollama is unavailable, times out, returns
                invalid JSON, or produces unusable output.
        """
        try:
            import ollama
        except ImportError as exc:
            raise ProcessingError(
                "redline_generation",
                "ollama package is not installed",
            ) from exc

        client = self._client or ollama.Client(
            host=self._base_url, timeout=self._timeout
        )

        # Build the prompt from bounded RAG context
        prompt = self._build_prompt(request)

        # Use structured JSON output if supported by the Ollama client
        generation_kwargs: dict[str, Any] = {
            "model": self._model_name,
            "messages": [{"role": "user", "content": prompt}],
            "format": OLLAMA_JSON_FORMAT,
            "options": {
                "temperature": 0.0,
                "num_predict": 512,
            },
        }

        # Use asyncio.to_thread for the blocking Ollama client call
        try:
            response = await asyncio.to_thread(
                client.chat, **generation_kwargs  # type: ignore[call-overload]
            )
        except Exception as exc:
            raise ProcessingError(
                "redline_generation",
                f"Ollama chat call failed: {exc}",
            ) from exc

        # Parse the structured JSON response
        try:
            content = response.get("message", {}).get("content", "")
            if not content:
                raise ProcessingError(
                    "redline_generation",
                    "Ollama returned empty content",
                )
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProcessingError(
                "redline_generation",
                f"Model output is not valid JSON: {exc}",
            ) from exc

        return self._parse_result(result, request.context_items)

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_prompt(self, request: RedlineGenerationInput) -> str:
        """Build a compact prompt from the bounded RAG context items.

        Does NOT send entire documents. Uses only context_items supplied
        by the application layer (RAG retrieval output).
        """
        # Build context segment from provided items
        context_parts: list[str] = []
        for i, item in enumerate(request.context_items):
            # Each item is a string segment from the context optimizer / RAG
            context_parts.append(f"CONTEXT {i + 1}: {item}")

        context_block = "\n".join(context_parts) if context_parts else ""

        prompt = "You are a legal redline analyst.\n\n"
        if context_block:
            prompt += f"Context segments:\n{context_block}\n\n"
        prompt += """Return only valid JSON: a single object with a "changes" array
containing exactly one change.
Generate exactly one "substitution" for the most legally significant clause
difference in the supplied context.
Required fields: clause_path, change_type, original_text, proposed_text,
rationale (max 1 sentence), risk_level (low|medium|high), confidence (0.0-1.0),
and citations.
original_text MUST be a non-empty full sentence copied exactly and verbatim
from one supplied CONTEXT segment.
proposed_text MUST be non-empty, materially revise that exact sentence, and
differ from original_text by at least one word.
proposed_text MUST NOT be copied verbatim from any supplied CONTEXT segment.
citations MUST contain exactly one citation.
citation.quote MUST equal original_text exactly, character-for-character.
citation.source_id MUST be the label of the CONTEXT segment containing original_text.
Never leave original_text, proposed_text, or citation.quote empty; never paraphrase original_text.
If these requirements cannot all be satisfied, return {"changes":[]}.
Return only the JSON object, with no markdown or explanatory text.
"""
        return prompt

# ------------------------------------------------------------------
# Result parsing
# ------------------------------------------------------------------

    def _parse_result(
        self, data: Any, context_items: tuple[str, ...] = ()
    ) -> RedlineGenerationResult:
        """Parse the LLM JSON response into RedlineGenerationResult.

        Validates the structure and preserves citation fidelity to the
        RAG context. Raises ProcessingError if the output is invalid or
        contains citations not grounded in the supplied context.

        Args:
            data: Parsed JSON dict from the LLM response.
            context_items: Bounded RAG context items for citation validation.

        Returns:
            RedlineGenerationResult with validated changes and citations.

        Raises:
            ProcessingError: If the output is invalid or citations are not
                grounded in the RAG context.
        """
        if not isinstance(data, dict):
            raise ProcessingError(
                "redline_generation",
                f"Expected JSON object, got {type(data).__name__}",
            )

        changes_data = data.get("changes", [])
        if not isinstance(changes_data, list):
            raise ProcessingError(
                "redline_generation",
                "JSON 'changes' field must be an array",
            )

        changes: list[GeneratedRedlineChange] = []

        for idx, change_data in enumerate(changes_data):
            if not isinstance(change_data, dict):
                raise ProcessingError(
                    "redline_generation",
                    f"Changes item at index {idx} is not a JSON object",
                )

            # Extract and validate fields
            clause_path = change_data.get("clause_path")
            change_type = change_data.get("change_type")
            original_text = change_data.get("original_text")
            proposed_text = change_data.get("proposed_text")
            rationale = change_data.get("rationale")
            risk_level = change_data.get("risk_level")
            confidence = change_data.get("confidence", 0.5)
            citations_data = change_data.get("citations", [])

            # Validate required fields are present and non-blank
            if not clause_path or not clause_path.strip():
                raise ProcessingError(
                    "redline_generation",
                    f"Changes item at index {idx}: clause_path is required and must not be blank",
                )
            if not proposed_text or not proposed_text.strip():
                raise ProcessingError(
                    "redline_generation",
                    f"Changes item at index {idx}: proposed_text is required and must not be blank",
                )
            if not rationale or not rationale.strip():
                raise ProcessingError(
                    "redline_generation",
                    f"Changes item at index {idx}: rationale is required and must not be blank",
                )
            if not original_text or not original_text.strip():
                raise ProcessingError(
                    "redline_generation",
                    f"Changes item at index {idx}: original_text is required and must not be blank",
                )

            # Validate original_text differs from proposed_text
            if original_text.strip() == proposed_text.strip():
                raise ProcessingError(
                    "redline_generation",
                    f"Changes item at index {idx}: "
                    "original_text must differ from proposed_text",
                )

            # Validate risk_level
            if risk_level not in {"low", "medium", "high"}:
                raise ProcessingError(
                    "redline_generation",
                    f"Changes item at index {idx}: risk_level must be one of "
                    f"low, medium, high, got '{risk_level}'",
                )

            # Validate confidence range
            try:
                confidence_val = float(confidence)
                if confidence_val < 0.0 or confidence_val > 1.0:
                    raise ProcessingError(
                        "redline_generation",
                        f"Changes item at index {idx}: confidence must be between "
                        f"0.0 and 1.0, got {confidence_val}",
                    )
            except (TypeError, ValueError) as exc:
                raise ProcessingError(
                    "redline_generation",
                    f"Changes item at index {idx}: confidence must be a float, got {confidence}",
                ) from exc

            # Validate citations - quotes must be grounded in the supplied context
            # Do NOT fabricate source IDs via hashing; instead verify that each
            # citation's quote appears in one of the provided context items.
            citations: list[GeneratedRedlineCitation] = []
            for cit_idx, cit_data in enumerate(citations_data):
                if not isinstance(cit_data, dict):
                    raise ProcessingError(
                        "redline_generation",
                        f"Citation at index {cit_idx} in change {idx} is not a JSON object",
                    )

                source_id = cit_data.get("source_id", "").strip()
                quote = cit_data.get("quote", "").strip()
                page_number = cit_data.get("page_number")
                start_offset = cit_data.get("start_offset")
                end_offset = cit_data.get("end_offset")

                # Validate that quote text appears in the supplied context items
                quote_grounded = False
                for item in context_items:
                    if quote and quote in item:
                        quote_grounded = True
                        break

                if not quote_grounded:
                    raise ProcessingError(
                        "redline_generation",
                        f"Changes item at index {idx}: citation quote is not "
                        "grounded in the supplied RAG context",
                    )

                citations.append(
                    GeneratedRedlineCitation(
                        source_id=source_id or f"context_{cit_idx + 1}",
                        quote=quote or "(derived from context)",
                        page_number=page_number,
                        start_offset=start_offset,
                        end_offset=end_offset,
                    )
                )

            # Build the GeneratedRedlineChange
            changes.append(
                GeneratedRedlineChange(
                    clause_path=clause_path.strip(),
                    change_type=change_type or "SUBSTITUTION",
                    original_text=original_text.strip(),
                    proposed_text=proposed_text.strip(),
                    rationale=rationale.strip(),
                    risk_level=risk_level,
                    confidence=confidence_val,
                    citations=tuple(citations),
                )
            )

        return RedlineGenerationResult(changes=tuple(changes))


# ------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------
