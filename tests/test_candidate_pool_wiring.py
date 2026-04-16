"""Test module for the candidate pool wiring behavior. The checks here explain what the repository expects to keep working."""
from __future__ import annotations

from types import SimpleNamespace

from src.query.pipeline import QueryPipeline
from src.query.query_router import QueryClassification, QueryRouter
from src.query.vector_retriever import VectorRetriever
from src.store.lance_store import ChunkResult


class _FakeEmbedder:
    """Small helper object used to keep test setup or expected results organized."""
    def embed_query(self, query: str):
        return [0.1, 0.2, 0.3]


class _FakeStore:
    """Small helper object used to keep test setup or expected results organized."""
    def __init__(self):
        self.calls = []
        self.path_calls = []
        self.source_head_calls = []
        self.metadata_store = None

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

    def metadata_path_search(self, path_terms, limit=10, allow_tail_fallback=True):
        self.path_calls.append({
            "path_terms": list(path_terms),
            "limit": limit,
            "allow_tail_fallback": allow_tail_fallback,
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

    def fetch_source_head_chunks(self, source_paths, limit=10):
        self.source_head_calls.append({
            "source_paths": list(source_paths),
            "limit": limit,
        })
        hits = []
        for index, source_path in enumerate(source_paths[:limit]):
            hits.append(
                ChunkResult(
                    chunk_id=f"typed-{index}",
                    text=f"typed result {index}",
                    enriched_text=None,
                    source_path=source_path,
                    score=-2.0,
                )
            )
        return hits


class _FakeMetadataStore:
    """Small helper object used to keep test setup or expected results organized."""
    def __init__(self):
        self.calls = []

    def find_source_paths(self, limit=10, **filters):
        self.calls.append({
            "limit": limit,
            "filters": filters,
        })
        if (
            filters.get("cdrl_code") == "A001"
            and filters.get("incident_id") == "igsi-1811"
            and filters.get("is_filed_deliverable") is True
        ):
            return [
                r"D:\CorpusTransfr\verified\IGS\1.5 enterprise program CDRLS\A001 - Corrective Action Plan\Fairford\Deliverables Report IGSI-1811 Corrective Action Plan (A001)\Deliverables Report IGSI-1811 Fairford CAP 2024-09.docx"
            ]
        return []


class _FakeRetriever:
    """Small helper object used to keep test setup or expected results organized."""
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
    """Small helper object used to keep test setup or expected results organized."""
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
    """Small helper object used to keep test setup or expected results organized."""
    pass


def test_vector_retriever_fetches_candidate_pool_without_truncating_callers():
    """Verify that vector retriever fetches candidate pool without truncating callers behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    results = retriever.search("find me something", top_k=10, candidate_pool=30)

    assert len(results) == 30
    assert store.calls[-1]["top_k"] == 30


def test_vector_retriever_defaults_to_requested_top_k_when_pool_not_requested():
    """Verify that vector retriever defaults to requested top k when pool not requested behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    results = retriever.search("find me something", top_k=10)

    assert len(results) == 10
    assert store.calls[-1]["top_k"] == 10


def test_pipeline_uses_candidate_pool_when_reranker_is_active():
    """Verify that pipeline uses candidate pool when reranker is active behaves the way the team expects."""
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
    """Verify that pipeline stays at top k when reranker is disabled behaves the way the team expects."""
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
    """Verify that vector retriever merges metadata path hits ahead of hybrid results behaves the way the team expects."""
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
    assert all(call["allow_tail_fallback"] is False for call in store.path_calls)


def test_vector_retriever_prefers_typed_metadata_hits_for_cap_lookup():
    """Verify that vector retriever prefers typed metadata hits for cap lookup behaves the way the team expects."""
    store = _FakeStore()
    store.metadata_store = _FakeMetadataStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    results = retriever.search(
        "What is the Corrective Action Plan for Fairford monitoring system incident IGSI-1811?",
        top_k=10,
        candidate_pool=30,
    )

    assert store.metadata_store.calls
    assert results[0].chunk_id == "typed-0"
    assert store.metadata_store.calls[0]["filters"]["cdrl_code"] == "A001"
    assert store.metadata_store.calls[0]["filters"]["incident_id"] == "igsi-1811"
    assert store.metadata_store.calls[0]["filters"]["is_filed_deliverable"] is True
    assert store.path_calls
    assert all(call["allow_tail_fallback"] is False for call in store.path_calls)


def test_vector_retriever_keeps_path_tail_for_breadth_queries():
    """Verify that vector retriever keeps path tail for breadth queries behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    retriever.search(
        "Which sites appear in both CDRL A009 and A025 deliverables?",
        top_k=10,
        candidate_pool=30,
    )

    assert store.path_calls
    assert all(call["allow_tail_fallback"] is True for call in store.path_calls)


def test_vector_retriever_builds_typed_reference_did_filters():
    """Verify that vector retriever builds typed reference did filters behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    groups = retriever._metadata_filter_groups(
        "Show me the reference DID for CDRL A002 Maintenance Service Report."
    )

    assert {"cdrl_code": "A002", "is_reference_did": True} in groups


def test_vector_retriever_builds_typed_filed_deliverable_filters():
    """Verify that vector retriever builds typed filed deliverable filters behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    groups = retriever._metadata_filter_groups(
        "Which CDRL is A002 and what maintenance service reports have been submitted under it?"
    )

    assert {"cdrl_code": "A002", "is_filed_deliverable": True} in groups


def test_vector_retriever_builds_cdrl_deliverable_hints_for_submitted_reports():
    """Verify that vector retriever builds cdrl deliverable hints for submitted reports behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    groups = retriever._path_hint_groups(
        "Which CDRL is A002 and what maintenance service reports have been submitted under it?"
    )

    assert ["a002", "maintenance service report"] in groups
    assert ["a002", "msr"] in groups
    assert ["a002", "deliverables report"] in groups


def test_vector_retriever_builds_exact_deliverable_id_hints_for_cdrl_subtypes():
    """Verify that vector retriever builds exact deliverable id hints for cdrl subtypes behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    groups = retriever._path_hint_groups(
        "What was the monitoring system ACAS scan deliverable for July 2025 (IGSI-2553)?"
    )

    assert ["igsi-2553", "acas scan"] in groups
    assert ["igsi-2553"] in groups


def test_vector_retriever_builds_cdrl_deliverable_hints_for_com_sum_queries():
    """Verify that vector retriever builds cdrl deliverable hints for com sum queries behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    groups = retriever._path_hint_groups(
        "What has been delivered under CDRL A025 Computer Operation Manual and Software User Manual?"
    )

    assert ["a025", "computer operation manual"] in groups
    assert ["a025", "software user manual"] in groups
    assert ["a025", "com-sum"] in groups
    assert ["a025", "deliverables report"] in groups


def test_vector_retriever_builds_cap_path_hints_for_explicit_corrective_action_plan():
    """Verify that vector retriever builds cap path hints for explicit corrective action plan behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    groups = retriever._path_hint_groups(
        "What is the Corrective Action Plan for Fairford monitoring system incident IGSI-1811?"
    )

    assert ["a001", "corrective action plan"] in groups
    assert ["igsi-1811", "corrective action plan"] in groups
    assert ["igsi-1811", "fairford", "corrective action plan"] in groups
    assert ["fairford", "a001"] in groups


def test_vector_retriever_builds_cap_path_hints_for_bare_cap_token():
    """Verify that vector retriever builds cap path hints for bare cap token behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    groups = retriever._path_hint_groups(
        "What were the Misawa 2024 CAP findings under incident IGSI-2234?"
    )

    assert ["a001", "corrective action plan"] in groups
    assert ["igsi-2234", "corrective action plan"] in groups
    assert ["misawa", "a001"] in groups


def test_vector_retriever_builds_a027_path_hints_for_acas_scan_query():
    """Verify that vector retriever builds a027 path hints for acas scan query behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    groups = retriever._path_hint_groups(
        "What was the Learmonth ACAS scan results deliverable for July 2025 (IGSI-2553)?"
    )

    assert ["a027", "acas scan results"] in groups
    assert ["igsi-2553", "acas scan results"] in groups
    assert ["learmonth", "acas scan results"] in groups


def test_vector_retriever_uses_known_site_for_dated_packing_list_queries():
    """Verify that vector retriever uses known site for dated packing list queries behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    groups = retriever._path_hint_groups(
        "Show me the monitoring system packing list for the 2026-03-09 Ascension Mil-Air return shipment."
    )

    assert ["ascension", "2026_03_09", "packing list"] in groups
    assert not any(group[0] == "show" for group in groups)


def test_vector_retriever_builds_po_hints_for_numeric_purchase_order_queries():
    """Verify that vector retriever builds po hints for numeric purchase order queries behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    groups = retriever._path_hint_groups(
        "What part was received on PO 5000585586 for Lualualei?"
    )

    assert ["5000585586"] in groups
    assert ["5000585586", "lualualei"] in groups


def test_vector_retriever_builds_procurement_item_and_vendor_hints():
    """Verify that vector retriever builds procurement item and vendor hints behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    groups = retriever._path_hint_groups(
        "Show me the purchase order for the DMEA coax crimp kit bought from PBJ for the monitoring system installation."
    )

    assert ["coax crimp"] in groups
    assert ["pbj"] in groups
    assert ["coax crimp", "pbj"] in groups


def test_vector_retriever_builds_contract_and_temporal_a027_hints():
    """Verify that vector retriever builds contract and temporal a027 hints behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    groups = retriever._path_hint_groups(
        "What ACAS scan deliverables have been filed under the new FA881525FB002 contract?"
    )

    assert ["a027", "acas scan results", "fa881525fb002"] in groups
    assert ["fa881525fb002", "acas scan results"] in groups


def test_vector_retriever_builds_temporal_a027_hints_for_month_named_queries():
    """Verify that vector retriever builds temporal a027 hints for month named queries behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    groups = retriever._path_hint_groups(
        "What deliverable corresponds to the monitoring system October 2025 ACAS scan?"
    )

    assert ["a027", "acas scan results", "october-2025"] in groups
    assert ["a027", "acas scan results", "monitoring system"] in groups


def test_vector_retriever_builds_cross_tree_cdrl_groups_for_dual_cdrl_query():
    """Verify that vector retriever builds cross tree cdrl groups for dual cdrl query behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    groups = retriever._path_hint_groups(
        "Which sites appear in both the CDRL A001 Corrective Action Plan folder AND the CDRL A002 Maintenance Service Report folder?"
    )

    assert ["a001", "corrective action plan"] in groups
    assert ["a002", "maintenance service report"] in groups
    assert ["a002", "msr"] in groups


def test_pipeline_prioritizes_curated_field_visit_results():
    """Verify that pipeline prioritizes curated field visit results behaves the way the team expects."""
    pipeline = QueryPipeline(
        router=SimpleNamespace(),
        vector_retriever=_FakeRetriever(candidate_pool=30),
        entity_retriever=None,
        context_builder=_FakeContextBuilder(reranker_active=False),
        generator=_FakeGenerator(),
    )
    results = [
        ChunkResult(
            chunk_id="bad",
            text="manual",
            enriched_text=None,
            source_path=r"C:\test_corpus\manual.pdf",
            score=0.1,
        ),
        ChunkResult(
            chunk_id="good",
            text="visit",
            enriched_text=None,
            source_path=r"C:\field_engineer\maintenance_report.docx",
            score=0.1,
        ),
    ]

    prioritized = pipeline._prioritize_visit_condition_results(results)

    assert prioritized[0].chunk_id == "good"


def test_router_routes_show_me_purchase_order_as_entity():
    """Verify that router routes show me purchase order as entity behaves the way the team expects."""
    router = QueryRouter(SimpleNamespace(available=False))

    classification = router.classify(
        "Show me the purchase order for the DMEA coax crimp kit bought from PBJ for the monitoring system installation."
    )

    assert classification.query_type == "ENTITY"


def test_router_routes_a027_document_location_queries_as_semantic():
    """Verify that router routes a027 document location queries as semantic behaves the way the team expects."""
    router = QueryRouter(SimpleNamespace(available=False))

    classification = router.classify(
        "Where are the A027 Plan and Controls Security Awareness Training documents stored?"
    )

    assert classification.query_type == "SEMANTIC"


def test_router_routes_narrow_temporal_shipment_lookups_as_entity():
    """Verify that router routes narrow temporal shipment lookups as entity behaves the way the team expects."""
    router = QueryRouter(SimpleNamespace(available=False))

    classification = router.classify(
        "What hand-carry shipments were sent to Guam in October 2024?"
    )

    assert classification.query_type == "ENTITY"


def test_vector_retriever_does_not_trigger_cap_hint_on_unrelated_cap_usage():
    """Verify that vector retriever does not trigger cap hint on unrelated cap usage behaves the way the team expects."""
    store = _FakeStore()
    retriever = VectorRetriever(store, _FakeEmbedder(), top_k=10, candidate_pool=30)

    groups = retriever._path_hint_groups(
        "What is the maximum cap on monthly deliverables?"
    )

    assert ["a001", "corrective action plan"] not in groups
