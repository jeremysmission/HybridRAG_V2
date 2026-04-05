"""
Context builder — assembles retrieved chunks into a context string for the LLM.

Sprint 1: FlashRank reranking integrated.
Sprint 2+ adds: parent chunk expansion, quality weighting,
structured results (SQL, entity cards, table rows).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.store.lance_store import ChunkResult
from src.query.reranker import FlashReranker


@dataclass
class GeneratorContext:
    """Context package passed to the generator."""

    context_text: str
    sources: list[str]
    chunk_count: int
    query_text: str


class ContextBuilder:
    """Assembles retrieved chunks into LLM context."""

    def __init__(self, top_k: int = 10, reranker_enabled: bool = True):
        self.top_k = top_k
        self._reranker = None
        if reranker_enabled:
            try:
                self._reranker = FlashReranker()
            except Exception:
                pass  # FlashRank not available — skip reranking

    def build(self, results: list[ChunkResult], query: str) -> GeneratorContext:
        """
        Build context from retrieval results.

        If reranker is enabled, reranks candidates before selecting top-K.
        Each chunk is formatted with its source path for citation.
        """
        if self._reranker and len(results) > self.top_k:
            chunks = self._reranker.rerank(query, results, top_n=self.top_k)
        else:
            chunks = results[:self.top_k]
        sources = list(dict.fromkeys(r.source_path for r in chunks))

        parts = []
        for i, chunk in enumerate(chunks, 1):
            source_name = chunk.source_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            text = chunk.enriched_text if chunk.enriched_text else chunk.text
            parts.append(
                f"[Source {i}: {source_name}]\n{text}\n"
            )

        context_text = "\n---\n".join(parts)

        return GeneratorContext(
            context_text=context_text,
            sources=sources,
            chunk_count=len(chunks),
            query_text=query,
        )
