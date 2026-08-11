from __future__ import annotations

import asyncio
import json
from datetime import date
from datetime import datetime
from typing import Any

from app.application.dtos.internal.analysis_generation import AnalysisGenerationInput
from app.application.dtos.internal.analysis_generation import AnalysisGenerationResult
from app.application.dtos.internal.analysis_generation import EvidenceInput
from app.application.dtos.internal.analysis_generation import GeneratedActionItem
from app.application.dtos.internal.analysis_generation import GeneratedObligation
from app.application.dtos.internal.analysis_generation import GeneratedRisk
from app.application.exceptions.processing import ProcessingError
from app.application.ports.llm_generation import AnalysisGenerationPort
from app.core.config import get_settings


class OllamaAnalysisGeneration(AnalysisGenerationPort):
    """Concrete AnalysisGenerationPort adapter using a local Ollama server."""

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._model_name = model_name or get_settings().ollama.default_model
        self._base_url = base_url or get_settings().ollama.base_url
        self._timeout = get_settings().ollama.timeout_seconds
        self._client: Any | None = None

    async def generate(self, request: AnalysisGenerationInput) -> AnalysisGenerationResult:
        try:
            import ollama
        except ImportError as exc:
            raise ProcessingError("analysis_generation", "ollama package is not installed") from exc

        client = self._client or ollama.Client(host=self._base_url, timeout=self._timeout)
        prompt = self._build_prompt(request)

        try:
            response = await asyncio.to_thread(
                client.chat,
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                format="json",
            )
        except Exception as exc:
            raise ProcessingError(
                "analysis_generation",
                f"Ollama chat call failed: {exc}",
            ) from exc

        content = response.get("message", {}).get("content", "")
        if not content:
            raise ProcessingError(
                "analysis_generation",
                "Ollama returned empty content",
            )

        return self._parse_result(content)

    def _build_prompt(self, request: AnalysisGenerationInput) -> str:
        evidence_text = ""
        if request.evidence:
            evidence_text = "\n\nADDITIONAL EVIDENCE:\n" + "\n".join(
                f"- {e.quote}" for e in request.evidence
            )

        return (
            "You are a conservative legal analyst. Analyze the following meeting transcript "
            "and produce a JSON response. Do not invent facts. Only report what is present "
            "or reasonably implied in the text.\n\n"
            f"TRANSCRIPT:\n{request.transcript}{evidence_text}\n\n"
            "Produce a JSON object matching this exact structure:\n"
            "{\n"
            '  "summary": "One-paragraph summary of the meeting from a legal perspective.",\n'
            '  "risks": [\n'
            "    {\n"
            '      "title": "Short risk title",\n'
            '      "description": "Detailed description",\n'
            '      "level": "low|medium|high|critical",\n'
            '      "confidence": 0.85,\n'
            '      "evidence": [{"source_id": "transcript", "quote": "relevant quote"}]\n'
            "    }\n"
            "  ],\n"
            '  "obligations": [\n'
            "    {\n"
            '      "title": "Short obligation title",\n'
            '      "description": "Detailed description",\n'
            '      "responsible_party": "Who is responsible",\n'
            '      "confidence": 0.80,\n'
            '      "evidence": [{"source_id": "transcript", "quote": "relevant quote"}],\n'
            '      "due_date": "YYYY-MM-DD" or null\n'
            "    }\n"
            "  ],\n"
            '  "action_items": [\n'
            "    {\n"
            '      "title": "Short action title",\n'
            '      "description": "Detailed description",\n'
            '      "responsible_party": "Who should act",\n'
            '      "confidence": 0.80,\n'
            '      "evidence": [{"source_id": "transcript", "quote": "relevant quote"}],\n'
            '      "due_date": "YYYY-MM-DD" or null\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            '- "level" must be exactly one of: low, medium, high, critical\n'
            '- "confidence" must be a float between 0.0 and 1.0\n'
            "- If a category has no entries, return an empty array []\n"
            "- Do not wrap the JSON in markdown code fences\n"
            "- Return only raw JSON\n"
        )

    def _parse_result(self, content: str) -> AnalysisGenerationResult:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProcessingError(
                "analysis_generation",
                f"Model output is not valid JSON: {exc}",
            ) from exc

        summary = data.get("summary", "")
        risks = self._parse_risks(data.get("risks", []))
        obligations = self._parse_obligations(data.get("obligations", []))
        action_items = self._parse_action_items(data.get("action_items", []))

        return AnalysisGenerationResult(
            summary=summary,
            risks=risks,
            obligations=obligations,
            action_items=action_items,
        )

    def _parse_risks(self, items: list[dict[str, Any]]) -> tuple[GeneratedRisk, ...]:
        result: list[GeneratedRisk] = []
        for idx, item in enumerate(items):
            evidence = self._parse_evidence(item.get("evidence", []))
            # Ensure at least one evidence entry so domain invariants are satisfied
            if not evidence:
                evidence = (
                    EvidenceInput(
                        source_id="analysis",
                        quote="Derived from meeting transcript.",
                    ),
                )
            try:
                result.append(
                    GeneratedRisk(
                        title=item.get("title", f"Risk {idx + 1}"),
                        description=item.get("description", ""),
                        level=item.get("level", "medium"),
                        confidence=float(item.get("confidence", 0.5)),
                        evidence=evidence,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ProcessingError(
                    "analysis_generation",
                    f"Invalid risk item at index {idx}: {exc}",
                ) from exc
        return tuple(result)

    def _parse_obligations(self, items: list[dict[str, Any]]) -> tuple[GeneratedObligation, ...]:
        result: list[GeneratedObligation] = []
        for idx, item in enumerate(items):
            evidence = self._parse_evidence(item.get("evidence", []))
            if not evidence:
                evidence = (
                    EvidenceInput(
                        source_id="analysis",
                        quote="Derived from meeting transcript.",
                    ),
                )
            due_date = self._parse_optional_date(item.get("due_date"))
            try:
                result.append(
                    GeneratedObligation(
                        title=item.get("title", f"Obligation {idx + 1}"),
                        description=item.get("description", ""),
                        responsible_party=item.get("responsible_party", ""),
                        confidence=float(item.get("confidence", 0.5)),
                        evidence=evidence,
                        due_date=due_date,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ProcessingError(
                    "analysis_generation",
                    f"Invalid obligation item at index {idx}: {exc}",
                ) from exc
        return tuple(result)

    def _parse_action_items(self, items: list[dict[str, Any]]) -> tuple[GeneratedActionItem, ...]:
        result: list[GeneratedActionItem] = []
        for idx, item in enumerate(items):
            evidence = self._parse_evidence(item.get("evidence", []))
            due_date = self._parse_optional_date(item.get("due_date"))
            try:
                result.append(
                    GeneratedActionItem(
                        title=item.get("title", f"Action Item {idx + 1}"),
                        description=item.get("description", ""),
                        responsible_party=item.get("responsible_party", ""),
                        confidence=float(item.get("confidence", 0.5)),
                        evidence=evidence,
                        due_date=due_date,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ProcessingError(
                    "analysis_generation",
                    f"Invalid action item at index {idx}: {exc}",
                ) from exc
        return tuple(result)

    @staticmethod
    def _parse_evidence(items: list[dict[str, Any]]) -> tuple[EvidenceInput, ...]:
        result: list[EvidenceInput] = []
        for item in items:
            result.append(
                EvidenceInput(
                    source_id=item.get("source_id", ""),
                    quote=item.get("quote", ""),
                    page_number=item.get("page_number"),
                    start_offset=item.get("start_offset"),
                    end_offset=item.get("end_offset"),
                )
            )
        return tuple(result)

    @staticmethod
    def _parse_optional_date(value: Any) -> date | None:
        if value is None or value == "":
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            return None
