from __future__ import annotations

import re
from typing import Any
from typing import ClassVar

from app.application.dtos.internal.analysis_generation import AnalysisGenerationInput
from app.application.dtos.internal.analysis_generation import AnalysisGenerationResult
from app.application.dtos.internal.analysis_generation import EvidenceInput
from app.application.dtos.internal.analysis_generation import GeneratedActionItem
from app.application.dtos.internal.analysis_generation import GeneratedObligation
from app.application.dtos.internal.analysis_generation import GeneratedRisk
from app.application.ports.llm_generation import AnalysisGenerationPort


class RuleBasedAnalysisGeneration(AnalysisGenerationPort):
    """Minimal fallback adapter that extracts legal items via keyword heuristics.

    Used when the local LLM is unreachable or disabled.
    """

    _RISK_PATTERNS: ClassVar[list[tuple[str, str, str]]] = [
        (
            r"\bliability\b",
            "Liability exposure",
            "The text mentions liability, which may create legal exposure.",
        ),
        (
            r"\bdamages\b",
            "Damages risk",
            "The text references damages, indicating potential financial exposure.",
        ),
        (
            r"\bbreach\b",
            "Breach risk",
            "The text refers to a breach, which may trigger contractual consequences.",
        ),
        (
            r"\bpenalt(?:y|ies)\b",
            "Penalty risk",
            "The text mentions penalties, indicating potential fines or sanctions.",
        ),
    ]

    _OBLIGATION_PATTERNS: ClassVar[list[tuple[str, str, str]]] = [
        (
            r"\b(?:must|shall)\b",
            "Mandatory obligation",
            "The text contains a mandatory obligation.",
        ),
        (r"\bobligated\b", "Obligation", "The text indicates an obligation."),
        (r"\brequired to\b", "Requirement", "The text states a requirement."),
        (
            r"\bresponsible for\b",
            "Responsibility",
            "The text assigns responsibility.",
        ),
    ]

    _ACTION_PATTERNS: ClassVar[list[tuple[str, str, str]]] = [
        (
            r"\bagreed to\b",
            "Agreement to act",
            "The parties agreed to take action.",
        ),
        (
            r"\bwill (?:prepare|review|draft|send|deliver)\b",
            "Planned action",
            "A future action is planned.",
        ),
        (r"\bdeadline\b", "Deadline", "A deadline is mentioned."),
        (r"\bdue (?:by|on|before)\b", "Due date", "A due date is referenced."),
    ]

    async def generate(self, request: AnalysisGenerationInput) -> AnalysisGenerationResult:
        text = request.transcript.lower()

        risks = self._scan(text, self._RISK_PATTERNS, "high")
        obligations = self._scan(text, self._OBLIGATION_PATTERNS, "medium")
        action_items = self._scan(text, self._ACTION_PATTERNS, "medium")

        summary = self._build_summary(risks, obligations, action_items)

        return AnalysisGenerationResult(
            summary=summary,
            risks=risks,
            obligations=obligations,
            action_items=action_items,
        )

    @classmethod
    def _scan(
        cls,
        text: str,
        patterns: list[tuple[str, str, str]],
        default_level: str,
    ) -> tuple[Any, ...]:
        results: list[Any] = []
        seen_titles: set[str] = set()
        for pattern, title, description in patterns:
            if re.search(pattern, text) and title not in seen_titles:
                seen_titles.add(title)
                evidence = (
                    EvidenceInput(
                        source_id="rule_based",
                        quote=f"Matched pattern: {pattern}",
                    ),
                )
                if default_level == "high":
                    results.append(
                        GeneratedRisk(
                            title=title,
                            description=description,
                            level=default_level,
                            confidence=0.6,
                            evidence=evidence,
                        )
                    )
                elif (
                    "action" in title.lower()
                    or "deadline" in title.lower()
                    or "due" in title.lower()
                ):
                    results.append(
                        GeneratedActionItem(
                            title=title,
                            description=description,
                            responsible_party="TBD",
                            confidence=0.6,
                            evidence=evidence,
                        )
                    )
                else:
                    results.append(
                        GeneratedObligation(
                            title=title,
                            description=description,
                            responsible_party="TBD",
                            confidence=0.6,
                            evidence=evidence,
                        )
                    )
        return tuple(results)

    @staticmethod
    def _build_summary(
        risks: tuple[Any, ...],
        obligations: tuple[Any, ...],
        action_items: tuple[Any, ...],
    ) -> str:
        parts: list[str] = []
        if risks:
            parts.append(f"Identified {len(risks)} risk(s).")
        if obligations:
            parts.append(f"Identified {len(obligations)} obligation(s).")
        if action_items:
            parts.append(f"Identified {len(action_items)} action item(s).")
        if not parts:
            return "No significant legal items were identified by rule-based scanning."
        return " ".join(parts)
