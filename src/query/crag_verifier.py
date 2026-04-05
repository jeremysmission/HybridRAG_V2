"""
CRAG (Corrective RAG) verification loop — post-generation quality gate.

After the generator produces an answer, CRAG grades whether the answer
is actually supported by the retrieved context. Three outcomes:

  - CORRECT (score >= 0.7): Return answer as-is
  - AMBIGUOUS (0.3 <= score < 0.7): Refine via knowledge strip decomposition,
    then re-generate. If still ambiguous, rewrite query and re-retrieve.
  - INCORRECT (score < 0.3): Return NOT_FOUND response

Only applies to SEMANTIC and COMPLEX query types. ENTITY, AGGREGATE, and
TABULAR responses come from structured stores and are already high-confidence
factual lookups — CRAG is skipped for those.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum

from src.config.schema import CRAGConfig
from src.llm.client import LLMClient
from src.query.context_builder import ContextBuilder, GeneratorContext
from src.query.generator import Generator, QueryResponse
from src.query.vector_retriever import VectorRetriever

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Query types that bypass CRAG (structured store lookups)
_SKIP_QUERY_TYPES = {"ENTITY", "AGGREGATE", "TABULAR"}

GRADING_SYSTEM_PROMPT = """You are a strict relevance grader for a RAG system.
Given a QUESTION, CONTEXT (retrieved documents), and ANSWER (generated response),
evaluate whether the ANSWER is factually supported by the CONTEXT.

You MUST respond with valid JSON matching this exact schema:
{
  "relevance_score": <float 0.0 to 1.0>,
  "supported_claims": ["claim that IS backed by context", ...],
  "unsupported_claims": ["claim NOT backed by context", ...],
  "reasoning": "brief explanation of your grading"
}

Scoring guide:
  1.0 = Every claim in the answer is directly stated in the context
  0.7 = Most claims supported, minor gaps
  0.5 = Roughly half supported, half unsupported
  0.3 = Few claims supported, mostly unsupported
  0.0 = Answer is completely unsupported or contradicts the context

Be strict. If the answer hedges or fabricates details not in the context,
score lower. If the answer says NOT_FOUND and the context truly lacks info,
score 1.0 (correct behavior)."""

STRIP_SCORING_SYSTEM_PROMPT = """You are a relevance scorer for individual text strips.
Given a QUESTION and a list of TEXT STRIPS (sentences from retrieved documents),
score each strip for relevance to answering the question.

You MUST respond with valid JSON: a list of objects, one per strip, in order:
[
  {"index": 0, "score": 0.0-1.0, "reason": "brief"},
  {"index": 1, "score": 0.0-1.0, "reason": "brief"},
  ...
]

Score 1.0 = directly answers the question.
Score 0.0 = completely irrelevant."""

QUERY_REWRITE_SYSTEM_PROMPT = """You are a search query optimizer.
Given an original question that failed to retrieve good results, rewrite it
to improve retrieval. Make it more specific, use different terminology,
or decompose it.

Respond with ONLY the rewritten query text, nothing else."""


class CRAGOutcome(str, Enum):
    """Result of CRAG grading."""
    CORRECT = "CORRECT"
    AMBIGUOUS = "AMBIGUOUS"
    INCORRECT = "INCORRECT"


@dataclass
class GradingResult:
    """Structured output from the CRAG grading step."""
    relevance_score: float
    supported_claims: list[str]
    unsupported_claims: list[str]
    reasoning: str
    outcome: CRAGOutcome


# ---------------------------------------------------------------------------
# CRAG Verifier
# ---------------------------------------------------------------------------

class CRAGVerifier:
    """
    Post-generation quality gate using Corrective RAG.

    Grades the generator's answer against the retrieved context,
    and triggers re-generation or re-retrieval when the answer
    is not well-supported.
    """

    def __init__(
        self,
        config: CRAGConfig,
        llm_client: LLMClient,
        vector_retriever: VectorRetriever,
        context_builder: ContextBuilder,
        generator: Generator,
    ):
        self.config = config
        self.llm = llm_client
        self.vector_retriever = vector_retriever
        self.context_builder = context_builder
        self.generator = generator

    def should_verify(self, query_type: str) -> bool:
        """Check if this query type should go through CRAG."""
        if not self.config.enabled:
            return False
        if query_type in _SKIP_QUERY_TYPES:
            logger.debug(
                "CRAG skipped for %s query type (structured store lookup)",
                query_type,
            )
            return False
        return True

    def verify_and_correct(
        self,
        response: QueryResponse,
        context: GeneratorContext,
        query_text: str,
        top_k: int = 10,
    ) -> QueryResponse:
        """
        Run the full CRAG verification loop on a generated response.

        Returns the original or corrected QueryResponse with crag_verified
        and crag_retries fields set.
        """
        try:
            return self._verify_loop(response, context, query_text, top_k)
        except Exception as e:
            # Graceful degradation: if anything fails, return original
            logger.warning("CRAG verification failed, returning original: %s", e)
            response.crag_verified = False
            response.crag_retries = 0
            return response

    def _verify_loop(
        self,
        response: QueryResponse,
        context: GeneratorContext,
        query_text: str,
        top_k: int,
    ) -> QueryResponse:
        """Core CRAG loop with retry logic."""
        retries = 0

        # First grading pass
        grade = self._grade_response(response.answer, context.context_text, query_text)
        logger.info(
            "CRAG grade: score=%.2f, outcome=%s, reasoning=%s",
            grade.relevance_score, grade.outcome.value, grade.reasoning,
        )

        if grade.outcome == CRAGOutcome.CORRECT:
            response.crag_verified = True
            response.crag_retries = 0
            logger.info("CRAG: answer verified as CORRECT (score=%.2f)", grade.relevance_score)
            return response

        if grade.outcome == CRAGOutcome.INCORRECT:
            response.crag_verified = True
            response.crag_retries = 0
            logger.info("CRAG: answer graded INCORRECT (score=%.2f), returning NOT_FOUND", grade.relevance_score)
            return self._not_found_response(response, query_text)

        # AMBIGUOUS path: try knowledge strip refinement, then re-retrieval
        while retries < self.config.max_retries and grade.outcome == CRAGOutcome.AMBIGUOUS:
            retries += 1
            logger.info("CRAG retry %d/%d: AMBIGUOUS (score=%.2f)", retries, self.config.max_retries, grade.relevance_score)

            # Step 1: Knowledge strip refinement
            refined_context = self._refine_via_strips(context, query_text)
            if refined_context is not None:
                new_response = self.generator.generate(refined_context, query_text)
                new_grade = self._grade_response(new_response.answer, refined_context.context_text, query_text)
                logger.info(
                    "CRAG post-strip-refinement: score=%.2f, outcome=%s",
                    new_grade.relevance_score, new_grade.outcome.value,
                )

                if new_grade.outcome == CRAGOutcome.CORRECT:
                    new_response.crag_verified = True
                    new_response.crag_retries = retries
                    new_response.sources = response.sources
                    new_response.query_path = response.query_path
                    return new_response

                if new_grade.outcome == CRAGOutcome.INCORRECT:
                    return self._not_found_response(response, query_text, retries)

            # Step 2: Query rewrite + re-retrieval
            rewritten_query = self._rewrite_query(query_text)
            if rewritten_query and rewritten_query != query_text:
                logger.info("CRAG query rewrite: '%s' -> '%s'", query_text, rewritten_query)
                new_results = self.vector_retriever.search(rewritten_query, top_k=top_k)
                if new_results:
                    context = self.context_builder.build(new_results, query_text)
                    new_response = self.generator.generate(context, query_text)
                    grade = self._grade_response(new_response.answer, context.context_text, query_text)
                    logger.info(
                        "CRAG post-re-retrieval: score=%.2f, outcome=%s",
                        grade.relevance_score, grade.outcome.value,
                    )

                    if grade.outcome == CRAGOutcome.CORRECT:
                        new_response.crag_verified = True
                        new_response.crag_retries = retries
                        new_response.query_path = response.query_path
                        return new_response

                    if grade.outcome == CRAGOutcome.INCORRECT:
                        return self._not_found_response(response, query_text, retries)

                    # Still AMBIGUOUS — continue loop
                    response = new_response
                else:
                    logger.info("CRAG re-retrieval returned no results")

        # Exhausted retries while still AMBIGUOUS — return best effort
        logger.info("CRAG: exhausted %d retries, returning last response", retries)
        response.crag_verified = True
        response.crag_retries = retries
        return response

    def _grade_response(
        self, answer: str, context_text: str, query_text: str
    ) -> GradingResult:
        """
        Grade the answer against the context using structured LLM output.

        Returns GradingResult with score and outcome classification.
        """
        prompt = (
            f"QUESTION:\n{query_text}\n\n"
            f"CONTEXT:\n{context_text}\n\n"
            f"ANSWER:\n{answer}"
        )

        response_format = {
            "type": "json_object",
        }

        llm_response = self.llm.call(
            prompt=prompt,
            system_prompt=GRADING_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=2048,
            response_format=response_format,
        )

        parsed = self._parse_grading_json(llm_response.text)
        return parsed

    def _parse_grading_json(self, text: str) -> GradingResult:
        """Parse the JSON grading response, with fallback for malformed output."""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
            else:
                logger.warning("CRAG grading returned non-JSON, defaulting to CORRECT")
                return GradingResult(
                    relevance_score=1.0,
                    supported_claims=[],
                    unsupported_claims=[],
                    reasoning="Grading parse failure — defaulting to pass-through",
                    outcome=CRAGOutcome.CORRECT,
                )

        score = float(data.get("relevance_score", 1.0))
        score = max(0.0, min(1.0, score))

        if score >= 0.7:
            outcome = CRAGOutcome.CORRECT
        elif score >= 0.3:
            outcome = CRAGOutcome.AMBIGUOUS
        else:
            outcome = CRAGOutcome.INCORRECT

        return GradingResult(
            relevance_score=score,
            supported_claims=data.get("supported_claims", []),
            unsupported_claims=data.get("unsupported_claims", []),
            reasoning=data.get("reasoning", ""),
            outcome=outcome,
        )

    def _refine_via_strips(
        self, context: GeneratorContext, query_text: str
    ) -> GeneratorContext | None:
        """
        Knowledge strip decomposition and scoring.

        Splits context into individual sentences, scores each for relevance,
        discards low-scoring strips, and rebuilds context from survivors.
        Returns None if no strips survive filtering.
        """
        # Split context into sentence-level strips
        strips = self._split_into_strips(context.context_text)
        if not strips:
            return None

        # Score strips in a single batch LLM call
        scores = self._score_strips(strips, query_text)
        if scores is None:
            return None

        # Filter strips scoring >= 0.5
        surviving = [
            (strip, score)
            for strip, score in zip(strips, scores)
            if score >= 0.5
        ]

        if not surviving:
            logger.info("CRAG strip refinement: no strips survived (all < 0.5)")
            return None

        logger.info(
            "CRAG strip refinement: %d/%d strips survived",
            len(surviving), len(strips),
        )

        refined_text = "\n\n".join(strip for strip, _ in surviving)
        return GeneratorContext(
            context_text=refined_text,
            sources=context.sources,
            chunk_count=context.chunk_count,
            query_text=context.query_text,
        )

    def _split_into_strips(self, context_text: str) -> list[str]:
        """Split context text into sentence-level strips."""
        # Split on sentence boundaries while preserving source markers
        raw_sentences = re.split(r'(?<=[.!?])\s+', context_text)
        strips = []
        for s in raw_sentences:
            s = s.strip()
            if len(s) > 10:  # Skip tiny fragments
                strips.append(s)
        return strips

    def _score_strips(
        self, strips: list[str], query_text: str
    ) -> list[float] | None:
        """
        Score each strip for relevance to the query via batch LLM call.

        Returns list of float scores aligned with input strips, or None on failure.
        """
        # Build numbered strip list
        strip_list = "\n".join(
            f"[Strip {i}]: {strip}"
            for i, strip in enumerate(strips)
        )

        prompt = (
            f"QUESTION:\n{query_text}\n\n"
            f"TEXT STRIPS:\n{strip_list}"
        )

        response_format = {
            "type": "json_object",
        }

        try:
            llm_response = self.llm.call(
                prompt=prompt,
                system_prompt=STRIP_SCORING_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=4096,
                response_format=response_format,
            )
        except Exception as e:
            logger.warning("CRAG strip scoring LLM call failed: %s", e)
            return None

        return self._parse_strip_scores(llm_response.text, len(strips))

    def _parse_strip_scores(self, text: str, expected_count: int) -> list[float] | None:
        """Parse strip scoring JSON response."""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
            else:
                logger.warning("CRAG strip scoring returned non-JSON")
                return None

        # Handle both list and dict-with-list formats
        if isinstance(data, dict):
            # Try common wrapper keys
            for key in ("scores", "strips", "results"):
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
            else:
                # Dict of index->score
                if all(k.isdigit() for k in data.keys()):
                    scores = [0.0] * expected_count
                    for k, v in data.items():
                        idx = int(k)
                        if 0 <= idx < expected_count:
                            scores[idx] = float(v) if isinstance(v, (int, float)) else 0.0
                    return scores
                logger.warning("CRAG strip scoring: unexpected dict format")
                return None

        if not isinstance(data, list):
            return None

        scores = [0.0] * expected_count
        for item in data:
            if isinstance(item, dict):
                idx = item.get("index", -1)
                score = item.get("score", 0.0)
                if 0 <= idx < expected_count:
                    scores[idx] = float(score)
            elif isinstance(item, (int, float)):
                # Plain list of scores
                idx = data.index(item)
                if idx < expected_count:
                    scores[idx] = float(item)

        return scores

    def _rewrite_query(self, query_text: str) -> str | None:
        """Ask the LLM to rewrite the query for better retrieval."""
        try:
            llm_response = self.llm.call(
                prompt=f"Original question: {query_text}",
                system_prompt=QUERY_REWRITE_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=256,
            )
            rewritten = llm_response.text.strip()
            if rewritten:
                return rewritten
        except Exception as e:
            logger.warning("CRAG query rewrite failed: %s", e)
        return None

    def _not_found_response(
        self, original: QueryResponse, query_text: str, retries: int = 0
    ) -> QueryResponse:
        """Build a NOT_FOUND response preserving metadata from original."""
        return QueryResponse(
            answer=(
                "[NOT_FOUND] The retrieved documents do not contain sufficient "
                "information to answer this question reliably. The answer could "
                "not be verified against the source context."
            ),
            confidence="NOT_FOUND",
            query_path=original.query_path,
            sources=original.sources,
            chunks_used=original.chunks_used,
            latency_ms=original.latency_ms,
            input_tokens=original.input_tokens,
            output_tokens=original.output_tokens,
            crag_verified=True,
            crag_retries=retries,
        )
