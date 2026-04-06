"""
Vector retriever — searches the store for relevant chunks.

Uses the embedder to convert the query into a vector, then runs
hybrid search (vector kNN + BM25) on the store.

Slice 0.3: basic retrieval. Sprint 1+ adds FlashRank reranking.
"""

from __future__ import annotations

import os

from src.store.lance_store import LanceStore, ChunkResult


class VectorRetriever:
    """Retrieves chunks from the vector store via hybrid search."""

    def __init__(
        self,
        store: LanceStore,
        embedder,
        top_k: int = 10,
        nprobes: int | None = None,
        refine_factor: int | None = None,
    ):
        self.store = store
        self.embedder = embedder
        self.top_k = top_k
        self.nprobes = nprobes if nprobes is not None else self._env_int("HYBRIDRAG_LANCE_NPROBES")
        self.refine_factor = (
            refine_factor
            if refine_factor is not None
            else self._env_int("HYBRIDRAG_LANCE_REFINE_FACTOR")
        )
        if self.nprobes is not None or self.refine_factor is not None:
            self.store.configure_search(
                nprobes=self.nprobes,
                refine_factor=self.refine_factor,
            )

    def search(self, query: str, top_k: int | None = None) -> list[ChunkResult]:
        """
        Search for chunks matching the query.

        Embeds the query, runs hybrid search (vector + BM25).
        """
        k = top_k or self.top_k
        query_vector = self.embedder.embed_query(query)
        results = self.store.hybrid_search(
            query_vector=query_vector,
            query_text=query,
            top_k=k,
            nprobes=self.nprobes,
            refine_factor=self.refine_factor,
        )
        return results

    def _env_int(self, name: str) -> int | None:
        """Parse an optional positive integer from the environment."""
        raw = os.getenv(name, "").strip()
        if not raw:
            return None
        try:
            value = int(raw)
        except ValueError:
            return None
        return value if value > 0 else None
