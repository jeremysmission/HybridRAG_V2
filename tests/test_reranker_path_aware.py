"""Test module for the reranker path aware behavior. The checks here explain what the repository expects to keep working."""
from __future__ import annotations

from src.query import reranker as reranker_mod
from src.query.reranker import FlashReranker
from src.store.lance_store import ChunkResult


class _FakeRerankRequest:
    """Small helper object used to keep test setup or expected results organized."""
    def __init__(self, query, passages):
        self.query = query
        self.passages = passages


class _FakeRanker:
    """Small helper object used to keep test setup or expected results organized."""
    def __init__(self, model_name: str = "fake"):
        self.model_name = model_name
        self.last_request = None

    def rerank(self, request):
        self.last_request = request
        ranked = []
        for passage in request.passages:
            score = 1.0 if "Logistics" in passage["text"] else 0.0
            ranked.append({"id": passage["id"], "score": score})
        return sorted(ranked, key=lambda item: (-item["score"], item["id"]))


def test_reranker_passages_include_source_path(monkeypatch):
    """Verify that reranker passages include source path behaves the way the team expects."""
    fake_ranker = _FakeRanker()
    monkeypatch.setattr(reranker_mod, "Ranker", lambda model_name="fake": fake_ranker)
    monkeypatch.setattr(reranker_mod, "RerankRequest", _FakeRerankRequest)

    reranker = FlashReranker()
    results = [
        ChunkResult(
            chunk_id="a",
            text="shared body",
            enriched_text=None,
            source_path=r"D:\Docs\Program Management\file.txt",
            score=0.0,
        ),
        ChunkResult(
            chunk_id="b",
            text="shared body",
            enriched_text=None,
            source_path=r"D:\Docs\Logistics\file.txt",
            score=0.0,
        ),
    ]

    reranked = reranker.rerank("find the right family", results, top_n=2)

    assert [r.chunk_id for r in reranked] == ["b", "a"]
    assert fake_ranker.last_request is not None
    assert any("Source path: D:\\Docs\\Logistics\\file.txt" in p["text"] for p in fake_ranker.last_request.passages)
    assert all("shared body" in p["text"] for p in fake_ranker.last_request.passages)
