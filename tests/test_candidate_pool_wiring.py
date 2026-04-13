from __future__ import annotations

from types import SimpleNamespace

from src.query.pipeline import QueryPipeline
from src.query.query_router import QueryClassification
from src.query.vector_retriever import VectorRetriever
from src.store.lance_store import ChunkResult


class _FakeEmbedder:
    def embed_query(self, query: str):
        return [0.1, 0.2, 0.3]


class _FakeStore:
    def __init__(self):
        self.calls = []
        self.path_calls = []

    def hybrid_search(self, query_vector, query_text="", top_k=10, nprobes=None, refine_factor=None):
        self.calls.append({
            "query_text": query_text,
            "top_k": top_k,
            "nprobes": nprobes,
            "refine_factor": refine_factor,
        })
        return [
            ChunkResult(
                chunk_id=f"c{i}",
                text=f"result {i}",
                enriched_text="",
                source_path=f"path{i}.txt",
                score=float(i),
                chunk_index=i,
                parse_quality=1.0,
            )
            for i in range(top_k)
        ]

    def metadata_path_search(self, path_terms, limit=10):
        self.path_calls.append({
            "path_terms": list(path_terms),
            "limit": limit,
        })
        if "learmonth" in path_terms and "2024_08" in path_terms:
            return [
                ChunkResult(
                    chunk_id="path-hit",
                    text="metadata hit",
                    enriched_text=None,
                    source_path=r"D:\Corpus\5.0 Logistics\Shipments\2024 - Shipments\Learmonth\2024_08_26 - Learmonth (Comm)\NG Packing List - Learmonth 2024.xlsx",
                    score=-1.0,
                )
            ]
        return []


class _FakeRetriever:
    def __init__(self, candidate_pool: int):
        self.candidate_pool = candidate_pool
        self.calls = []

    def search(self, query: str, top_k: int | None = None, candidate_pool: int | None = None):
        self.calls.append({
            "query": query,
            "top_k": top_k,
            "candidate_pool": candidate_pool,
        })
        count = candidate_pool or top_k or 0
        return [
            ChunkResult(
                chunk_id=f"c{i}",
                text=f"chunk {i}",
                enriched_text=None,
                source_path=f"doc{i}.txt",
                score=1.0 / (i + 1),
            )
            for i in range(count)
        ]


class _FakeContextBuilder:
    def __init__(self, reranker_active: bool):
        self._reranker = object() if reranker_active else None

    def build(self, results, query):
        return SimpleNamespace(
            context_text="ctx",
            sources=[r.source_path for r in results[:3]],
            chunk_count=len(results),
            query_text=query,
        )


class _FakeGenerator:
    pass


def test_vector_retriever_fetches_candidate_pool_without_truncating_callers():
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    results = retriever.search("find me something", top_k=10, candidate_pool=30)

    assert len(results) == 30
    assert store.calls[-1]["top_k"] == 30


def test_vector_retriever_defaults_to_requested_top_k_when_pool_not_requested():
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    results = retriever.search("find me something", top_k=10)

    assert len(results) == 10
    assert store.calls[-1]["top_k"] == 10


def test_pipeline_uses_candidate_pool_when_reranker_is_active():
    retriever = _FakeRetriever(candidate_pool=30)
    pipeline = QueryPipeline(
        router=SimpleNamespace(),
        vector_retriever=retriever,
        entity_retriever=None,
        context_builder=_FakeContextBuilder(reranker_active=True),
        generator=_FakeGenerator(),
    )
    classification = QueryClassification(
        query_type="SEMANTIC",
        original_query="find the right cdrl",
        expanded_query="find the right cdrl",
    )

    pipeline._handle_semantic(classification, top_k=10)

    assert retriever.calls[-1]["top_k"] == 10
    assert retriever.calls[-1]["candidate_pool"] == 30


def test_pipeline_stays_at_top_k_when_reranker_is_disabled():
    retriever = _FakeRetriever(candidate_pool=30)
    pipeline = QueryPipeline(
        router=SimpleNamespace(),
        vector_retriever=retriever,
        entity_retriever=None,
        context_builder=_FakeContextBuilder(reranker_active=False),
        generator=_FakeGenerator(),
    )
    classification = QueryClassification(
        query_type="SEMANTIC",
        original_query="find the right cdrl",
        expanded_query="find the right cdrl",
    )

    pipeline._handle_semantic(classification, top_k=10)

    assert retriever.calls[-1]["top_k"] == 10
    assert retriever.calls[-1]["candidate_pool"] == 10


def test_vector_retriever_merges_metadata_path_hits_ahead_of_hybrid_results():
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    results = retriever.search(
        "What was shipped to Learmonth in August 2024? packing list 2024_08",
        top_k=10,
        candidate_pool=30,
    )

    assert store.path_calls
    assert results[0].chunk_id == "path-hit"
    assert any(call["path_terms"] == ["learmonth", "2024_08"] for call in store.path_calls)
