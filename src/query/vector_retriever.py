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
        candidate_pool: int | None = None,
        nprobes: int | None = None,
        refine_factor: int | None = None,
    ):
        self.store = store
        self.embedder = embedder
        self.top_k = top_k
        self.candidate_pool = max(top_k, candidate_pool or top_k)
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

    def search(
        self,
        query: str,
        top_k: int | None = None,
        candidate_pool: int | None = None,
    ) -> list[ChunkResult]:
        """
        Search for chunks matching the query.

        Embeds the query, runs hybrid search (vector + BM25).

        ``top_k`` is the caller's target result count. ``candidate_pool``
        controls how many candidates we ask the store for before any
        downstream reranking/trimming. Direct callers that do not want a
        wider pool can omit ``candidate_pool`` and will get exactly
        ``top_k`` back.
        """
        k = top_k or self.top_k
        fetch_k = max(k, candidate_pool or k)
        # Sanitize: strip control chars and limit length to prevent tokenizer errors
        query = "".join(ch for ch in query if ch.isprintable() or ch in ("\n", "\t"))
        query = query[:4096]
        if not query.strip():
            return []
        query_vector = self.embedder.embed_query(query)
        results = self.store.hybrid_search(
            query_vector=query_vector,
            query_text=query,
            top_k=fetch_k,
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
