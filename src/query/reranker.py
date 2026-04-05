"""
FlashRank reranker — ultra-fast CPU reranking for retrieval precision.

4MB quantized model, sub-20ms for 30 candidates.
Replaces V1's phi4:14B reranker (130 seconds per query — unusable).

Wired into query pipeline: retrieve top-30 → rerank → top-10.
"""

from __future__ import annotations

import logging

from flashrank import Ranker, RerankRequest

from src.store.lance_store import ChunkResult

logger = logging.getLogger(__name__)


class FlashReranker:
    """Rerank retrieval candidates using FlashRank."""

    def __init__(self, model_name: str = "ms-marco-MiniLM-L-12-v2"):
        self._ranker = Ranker(model_name=model_name)
        logger.info("FlashRank reranker loaded: %s", model_name)

    def rerank(
        self,
        query: str,
        results: list[ChunkResult],
        top_n: int = 10,
    ) -> list[ChunkResult]:
        """
        Rerank retrieval results using FlashRank.

        Takes candidate list, returns top_n reranked by relevance.
        """
        if not results:
            return []

        # Build passages for FlashRank
        passages = [
            {"id": r.chunk_id, "text": r.text}
            for r in results
        ]

        request = RerankRequest(query=query, passages=passages)
        ranked = self._ranker.rerank(request)

        # Map back to ChunkResult objects
        id_to_result = {r.chunk_id: r for r in results}
        reranked = []
        for item in ranked[:top_n]:
            chunk_id = item["id"]
            if chunk_id in id_to_result:
                result = id_to_result[chunk_id]
                result.score = float(item.get("score", 0.0))
                reranked.append(result)

        return reranked
