"""
Generator — LLM generation with graduated confidence and citations.

Confidence levels (required in every response):
  - HIGH: Answer is directly stated in sources
  - PARTIAL: Some information found, gaps exist
  - NOT_FOUND: Sources do not contain this information

Slice 0.3: basic generation. Sprint 1+ adds streaming (SSE).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from src.llm.client import LLMClient, LLMResponse
from src.query.context_builder import GeneratorContext


SYSTEM_PROMPT = """You are a technical document assistant for IGS/NEXION military systems.
Answer based ONLY on the provided context.

CONFIDENCE LEVELS (required in every response):
- HIGH: Answer is directly stated in sources. Quote relevant text.
- PARTIAL: Some information found, gaps exist. State what you found AND what is missing.
- NOT_FOUND: Sources do not contain this information. Say so clearly. Do NOT guess.

RULES:
- Every claim must cite a source [Source: filename, section]
- Numbers must come from sources, never estimated
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
        start = time.time()

        extra_requirements: list[str] = []
        q_lower = user_query.lower()
        if "## structured data" in context.context_text.lower():
            extra_requirements.append(
                "Carry forward the key fields from matching structured rows instead of summarizing them away."
            )
        if "general condition" in q_lower or "condition of the equipment" in q_lower:
            extra_requirements.append(
                "Summarize both maintenance performed and repairs performed or still needed. "
                "Use the word 'repair' when the context describes repair activity."
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
        latency_ms = int((time.time() - start) * 1000)

        return QueryResponse(
            answer=llm_response.text,
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
        upper = text[:100].upper()
        if "[HIGH]" in upper:
            return "HIGH"
        if "[PARTIAL]" in upper:
            return "PARTIAL"
        if "[NOT_FOUND]" in upper or "[NOT FOUND]" in upper:
            return "NOT_FOUND"
        return "UNKNOWN"
