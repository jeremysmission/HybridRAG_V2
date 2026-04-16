"""
Context builder — assembles retrieved chunks into a context string for the LLM.

Sprint 1: FlashRank reranking integrated.
Sprint 2+ adds: parent chunk expansion, quality weighting,
structured results (SQL, entity cards, table rows).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from src.store.lance_store import ChunkResult
from src.query.reranker import FlashReranker

logger = logging.getLogger(__name__)


@dataclass
class GeneratorContext:
    """Context package passed to the generator."""

    context_text: str
    sources: list[str]
    chunk_count: int
    query_text: str
    stage_timings_ms: dict[str, int] = field(default_factory=dict)


class ContextBuilder:
    """Assembles retrieved chunks into LLM context."""

    def __init__(self, top_k: int = 10, reranker_enabled: bool = True):
        self.top_k = top_k
        self._reranker = None
        self._reranker_requested = bool(reranker_enabled)
        if reranker_enabled:
            try:
                self._reranker = FlashReranker()
            except Exception as exc:
                logger.warning(
                    "FlashRank init failed; reranking disabled: %s", exc
                )

    @property
    def reranker_active(self) -> bool:
        """True iff the reranker was requested AND successfully constructed."""
        return self._reranker is not None

    def build(self, results: list[ChunkResult], query: str) -> GeneratorContext:
        context, _timings = self.build_with_timings(results, query)
        return context

    def build_with_timings(
        self, results: list[ChunkResult], query: str
    ) -> tuple[GeneratorContext, dict[str, int]]:
        """
        Build context from retrieval results.

        If reranker is enabled, reranks candidates before selecting top-K.
        Each chunk is formatted with its source path for citation.
        """
        build_start = time.perf_counter()
        rerank_ms = 0
        if self._reranker and len(results) > self.top_k:
            rerank_start = time.perf_counter()
            chunks = self._reranker.rerank(query, results, top_n=self.top_k)
            rerank_ms = int((time.perf_counter() - rerank_start) * 1000)
        else:
            chunks = results[:self.top_k]
        assemble_start = time.perf_counter()
        sources = list(dict.fromkeys(r.source_path for r in chunks))

        parts = []
        for i, chunk in enumerate(chunks, 1):
            source_name = chunk.source_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            text = chunk.enriched_text if chunk.enriched_text else chunk.text
            parts.append(
                f"[Source {i}: {source_name}]\n{text}\n"
            )

        context_text = "\n---\n".join(parts)
        assemble_ms = int((time.perf_counter() - assemble_start) * 1000)
        total_ms = int((time.perf_counter() - build_start) * 1000)
        timings = {
            "rerank": rerank_ms,
            "context_assemble": assemble_ms,
            "context_build": total_ms,
        }

        return (
            GeneratorContext(
                context_text=context_text,
                sources=sources,
                chunk_count=len(chunks),
                query_text=query,
                stage_timings_ms=timings,
            ),
            timings,
        )
