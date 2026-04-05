"""
Context builder — assembles retrieved chunks into a context string for the LLM.

Slice 0.3: simple assembly of top-K chunks with source citations.
Sprint 2+ adds: deduplication, parent chunk expansion, quality weighting,
structured results (SQL, entity cards, table rows).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.store.lance_store import ChunkResult


@dataclass
class GeneratorContext:
    """Context package passed to the generator."""

    context_text: str
    sources: list[str]
    chunk_count: int
    query_text: str


class ContextBuilder:
    """Assembles retrieved chunks into LLM context."""

    def __init__(self, top_k: int = 10):
        self.top_k = top_k

    def build(self, results: list[ChunkResult], query: str) -> GeneratorContext:
        """
        Build context from retrieval results.

        Each chunk is formatted with its source path for citation.
        """
        chunks = results[:self.top_k]
        sources = list(dict.fromkeys(r.source_path for r in chunks))

        parts = []
        for i, chunk in enumerate(chunks, 1):
            source_name = chunk.source_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            parts.append(
                f"[Source {i}: {source_name}]\n{chunk.text}\n"
            )

        context_text = "\n---\n".join(parts)

        return GeneratorContext(
            context_text=context_text,
            sources=sources,
            chunk_count=len(chunks),
            query_text=query,
        )
