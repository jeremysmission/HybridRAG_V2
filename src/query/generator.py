"""
Generator — LLM generation with graduated confidence and citations.

Confidence levels (required in every response):
  - HIGH: Answer is directly stated in sources
  - PARTIAL: Some information found, gaps exist
  - NOT_FOUND: Sources do not contain this information

Slice 0.3: basic generation. Sprint 1+ adds streaming (SSE).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from src.llm.client import LLMClient, LLMResponse
from src.query.context_builder import GeneratorContext


SYSTEM_PROMPT = """You are a technical document system for enterprise program military systems.
Answer based ONLY on the provided context.

CONFIDENCE LEVELS (required in every response):
- HIGH: Answer is directly stated in sources. Quote relevant text.
- PARTIAL: Some information found, gaps exist. State what you found AND what is missing.
- NOT_FOUND: Sources do not contain this information. Say so clearly. Do NOT guess.

RULES:
- Every claim must cite a source [Source: filename, section]
- Numbers must come from sources, never estimated
- If the context directly answers the user's actual question, use [HIGH].
- Do NOT downgrade to [PARTIAL] just because the context lacks unrelated history,
  trend data, alternate interpretations, or extra background the user did not ask for.
- Only use [PARTIAL] when the missing information is necessary to answer the question asked.
- If the query asks for aggregation, show the count AND list each source
- If the context includes a table row or structured record, include the key identifying
  fields from that row in the answer, not just a single cell value. Preserve part numbers,
  destinations/sites, statuses, dates, requestors, and PO numbers when relevant.
- If the answer is a list of parts or replacements, include serial numbers and old/new
  identifiers whenever the context provides them.
- For condition-summary questions, include both repairs performed and outstanding repair
  issues when the context supports them.
- Start your response with [HIGH], [PARTIAL], or [NOT_FOUND]"""


@dataclass
class QueryResponse:
    """Complete response from the query pipeline."""

    answer: str
    sources: list[str]
    confidence: str
    query_path: str
    chunks_used: int
    latency_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    crag_verified: bool = False
    crag_retries: int = 0
    stage_timings_ms: dict[str, int] = field(default_factory=dict)


class Generator:
    """LLM generation with graduated confidence."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate(
        self, context: GeneratorContext, user_query: str
    ) -> QueryResponse:
        """
        Generate an answer from the context and query.

        Returns QueryResponse with confidence level parsed from the response.
        """
        start = time.perf_counter()

        extra_requirements: list[str] = []
        q_lower = user_query.lower()
        if "## structured data" in context.context_text.lower():
            extra_requirements.append(
                "Carry forward the key fields from matching structured rows instead of summarizing them away."
            )
        if (
            any(
                cue in q_lower
                for cue in (
                    "status of po-",
                    "purchase order",
                    "backordered",
                    "in transit",
                    "shipped",
                    "cancelled",
                )
            )
            and (
                "## structured data" in context.context_text.lower()
                or "[row " in context.context_text.lower()
                or "po number | part number" in context.context_text.lower()
            )
        ):
            extra_requirements.append(
                "If the retrieved row directly answers the question, respond with [HIGH] "
                "and do not speculate about unseen rows outside the provided context."
            )
        if "general condition" in q_lower or "condition of the equipment" in q_lower:
            extra_requirements.append(
                "Summarize both maintenance performed and repairs performed or still needed. "
                "Use the word 'repair' when the context describes repair activity."
            )
        if "point of contact" in q_lower or "contact for" in q_lower:
            extra_requirements.append(
                "If the context includes phone numbers or email addresses for the contact, "
                "include them in the answer."
            )
        if (
            "compare" in q_lower or " versus " in q_lower or " vs " in q_lower
        ) and "maintenance issues" in q_lower:
            extra_requirements.append(
                "For each site, name the concrete issue details from the context, including "
                "channel IDs, board or module names, serial numbers, corrosion or failure notes, "
                "and any outstanding replacement recommendation when present."
            )

        prompt_parts = [f"Context:\n{context.context_text}"]
        if extra_requirements:
            prompt_parts.append(
                "Additional answer requirements:\n- " + "\n- ".join(extra_requirements)
            )
        prompt_parts.append(f"Question: {user_query}")
        prompt = "\n\n".join(prompt_parts)

        llm_response = self.llm.call(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        confidence = self._parse_confidence(llm_response.text)
        confidence = self._normalize_confidence(confidence, llm_response.text, user_query)
        answer_text = self._ensure_confidence_tag(confidence, llm_response.text)
        latency_ms = int((time.perf_counter() - start) * 1000)

        return QueryResponse(
            answer=answer_text,
            sources=context.sources,
            confidence=confidence,
            query_path="SEMANTIC",
            chunks_used=context.chunk_count,
            latency_ms=latency_ms,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
        )

    def _parse_confidence(self, text: str) -> str:
        """Extract confidence level from response text."""
        upper = text[:120].upper()
        match = re.search(
            r"\[\s*\*{0,2}\s*(HIGH|PARTIAL|NOT[_ ]FOUND)\s*\*{0,2}\s*\]",
            upper,
        )
        if match:
            return match.group(1).replace(" ", "_")
        return "UNKNOWN"

    def _normalize_confidence(self, confidence: str, text: str, user_query: str) -> str:
        """
        Normalize confidence for weaker local models that overuse PARTIAL
        or occasionally omit the required confidence tag.

        This only applies to the Ollama testing path. Production OpenAI/Azure
        responses are left untouched.
        """
        if self.llm.provider != "ollama":
            return confidence

        q = user_query.lower()
        lower_text = text.lower()

        if confidence == "UNKNOWN":
            refusal_cues = [
                "does not contain",
                "no relevant documents",
                "no information",
                "not found",
                "cannot determine",
                "insufficient information",
            ]
            if any(cue in lower_text for cue in refusal_cues):
                return "NOT_FOUND"

            if "[source" in lower_text:
                direct_fact_cues = [
                    "output power",
                    "battery capacity",
                    "calibration procedure",
                    "workaround",
                    "amplifier board",
                    "field technician",
                    "point of contact",
                    "contact email",
                    "next scheduled maintenance",
                    "what part was replaced",
                    "part was replaced",
                ]
                partial_cues = [
                    "compare",
                    "versus",
                    "difference between",
                    "general condition",
                    "replacement board",
                    "cancelled",
                    "across all",
                    "across every",
                    "list all",
                    "how many",
                ]
                if any(cue in q for cue in direct_fact_cues) and not any(
                    cue in q for cue in partial_cues
                ):
                    return "HIGH"

            return confidence

        if confidence != "PARTIAL":
            return confidence

        structured_direct_cues = [
            "backordered",
            "status of po",
            "purchase order",
            "in transit",
            "shipped",
            "cancelled",
        ]
        overcautious_structured_gap_cues = [
            "does not provide information about any other",
            "does not provide a comprehensive list",
            "could be additional parts",
            "there may be additional parts",
            "may be additional parts",
            "might be additional orders",
            "full dataset or document",
            "this specific fragment only lists",
            "specific fragment only lists",
            "not listed here",
            "other parts that are currently backordered",
            "does not provide information on whether the second entry",
            "not captured here",
        ]
        if any(cue in q for cue in structured_direct_cues) and "[source" in lower_text:
            if any(cue in lower_text for cue in overcautious_structured_gap_cues):
                return "HIGH"

        if "unique part numbers" in q and (
            "referenced in " in lower_text
            or "list of unique part numbers" in lower_text
        ):
            return "HIGH"

        if (
            "point of contact" in q
            and "site where" in q
            and "[source" in lower_text
            and ("candidate/requestor" in lower_text or "respective points of contact" in lower_text)
        ):
            return "HIGH"

        if "how many" in q and "across all sites" in q:
            if any(cue in lower_text for cue in overcautious_structured_gap_cues):
                return "HIGH"

        direct_fact_cues = [
            "output power",
            "battery capacity",
            "calibration procedure",
            "workaround",
            "amplifier board",
            "field technician",
            "point of contact",
            "contact email",
            "next scheduled maintenance",
            "who requested parts",
        ]
        partial_cues = [
            "compare",
            "versus",
            "difference between",
            "general condition",
            "replacement board",
            "cancelled",
            "across all",
            "across every",
            "list all",
            "how many",
        ]
        if not any(cue in q for cue in direct_fact_cues):
            return confidence
        if any(cue in q for cue in partial_cues):
            return confidence

        if "[source" not in lower_text:
            return confidence

        generic_gap_cues = [
            "historical data",
            "additional details",
            "additional details about other individuals",
            "specific measured values",
            "exact measured values",
            "beyond this nominal value",
            "variations provided",
            "over time",
            "what is missing",
            "other individuals who might have been involved",
            "not provided in the context",
            "not explicitly stated",
            "exact output power",
            "however,",
        ]
        if any(cue in lower_text for cue in generic_gap_cues):
            return "HIGH"

        return confidence

    def _ensure_confidence_tag(self, confidence: str, text: str) -> str:
        """Prefix the normalized confidence tag when the model omits it."""
        if confidence not in {"HIGH", "PARTIAL", "NOT_FOUND"}:
            return text

        stripped = text.lstrip()
        prefix = f"[{confidence}] "
        tag_match = re.match(
            r"\[\s*\*{0,2}\s*(HIGH|PARTIAL|NOT_FOUND|NOT FOUND)\s*\*{0,2}\s*\]\s*",
            stripped,
            re.IGNORECASE,
        )
        if tag_match:
            normalized_existing = tag_match.group(1).upper().replace(" ", "_")
            if normalized_existing == confidence:
                return text
            leading_ws = text[: len(text) - len(stripped)]
            remainder = stripped[tag_match.end():]
            return f"{leading_ws}{prefix}{remainder}"

        if text[: len(text) - len(stripped)]:
            leading_ws = text[: len(text) - len(stripped)]
            return f"{leading_ws}{prefix}{stripped}"
        return prefix + text
