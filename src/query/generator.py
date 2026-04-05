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

        prompt = (
            f"Context:\n{context.context_text}\n\n"
            f"Question: {user_query}"
        )

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
