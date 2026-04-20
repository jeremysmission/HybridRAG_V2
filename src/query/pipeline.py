"""
Query pipeline — orchestrates router → retrieval → context → generation.

This is the main entry point for all query types. It:
  1. Classifies the query via QueryRouter
  2. Dispatches to vector and/or structured retrieval
  3. Merges results into a unified context
  4. Passes to Generator for LLM response

For COMPLEX queries, decomposes into sub-queries and fans out.
"""

from __future__ import annotations

import logging
import re
import time
from collections import OrderedDict
from dataclasses import replace

from src.config.schema import CRAGConfig
from src.query.query_router import QueryRouter, QueryClassification
from src.query.vector_retriever import VectorRetriever
from src.query.entity_retriever import EntityRetriever, StructuredResult
from src.query.context_builder import ContextBuilder, GeneratorContext
from src.query.generator import Generator, QueryResponse
from src.query.crag_verifier import CRAGVerifier
from src.query.aggregation_executor import AggregationExecutor, AggregationResult, CrossSubstrateExecutor
from src.store.lance_store import ChunkResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Unsupported logistics/PO aggregation guard (fail-closed)
# ---------------------------------------------------------------------------
# Queries requesting exact counts of POs, orders, receipts, or outstanding
# items don't yet have a deterministic substrate. Without this guard, the
# LLM would generate plausible-sounding but fabricated numbers.

_PO_LOGISTICS_TRIGGERS = re.compile(
    r"\b(?:how\s+many|count\s+(?:of|the)|total\s+(?:number|count|amount)"
    r"|number\s+of|how\s+much|tally|sum\s+of)\b",
    re.IGNORECASE,
)
_PO_LOGISTICS_AXIS = re.compile(
    r"\b(?:purchase\s+orders?|(?:open\s+)?POs?\b|orders?\s+(?:outstanding|received|placed)"
    r"|outstanding\s+(?:orders?|POs?|items?)|not\s+received"
    r"|open\s+PO|receive\s+lag|as[\s-]+of[\s-]+date"
    r"|shipments?\s+(?:received|outstanding|pending))\b",
    re.IGNORECASE,
)

def _detect_unsupported_logistics_count(query: str) -> bool:
    """Return True if query asks for exact counts of PO/logistics items.

    Requires BOTH an explicit counting trigger (how many, count of, total)
    AND a logistics-specific axis term. Pure semantic questions about
    logistics topics (policies, documents, procedures) pass through to RAG.
    """
    return bool(_PO_LOGISTICS_TRIGGERS.search(query) and _PO_LOGISTICS_AXIS.search(query))

# ---------------------------------------------------------------------------
# Adaptive top-k per query type (2026 production pattern)
# ---------------------------------------------------------------------------
# Literature consensus: AGGREGATE queries need wider retrieval to gather
# cross-document evidence; ENTITY queries need narrow, precise hits.
# See RESEARCH_ROOM_2026-04-16.md Assignment (c) for citations.
#
# Keys: (retrieve_top_k, rerank_top_k)
# retrieve_top_k: how many chunks to pull from vector search
# rerank_top_k: how many to keep after FlashRank reranking
ADAPTIVE_TOP_K: dict[str, tuple[int, int]] = {
    "ENTITY":    (10, 5),
    "SEMANTIC":  (30, 8),
    "AGGREGATE": (50, 15),
    "TABULAR":   (10, 5),
    "COMPLEX":   (30, 8),   # sub-queries get their own adaptive top-k
}
_DEFAULT_TOP_K = (10, 5)


def _resolve_adaptive_top_k(query_type: str) -> tuple[int, int]:
    """Return (retrieve_top_k, rerank_top_k) for a given query type."""
    return ADAPTIVE_TOP_K.get(query_type, _DEFAULT_TOP_K)


def _merge_stage_timings(*timing_maps: dict[str, int] | None) -> dict[str, int]:
    """Support the pipeline workflow by handling the merge stage timings step."""
    merged: dict[str, int] = {}
    for timing_map in timing_maps:
        if not timing_map:
            continue
        for key, value in timing_map.items():
            try:
                merged[key] = merged.get(key, 0) + int(value or 0)
            except (TypeError, ValueError):
                continue
    return merged


class QueryPipeline:
    """
    Unified query pipeline with router-based dispatch.

    Supports all five query types via the tri-store architecture.
    Falls back to vector-only search if structured stores are empty
    or if the router is unavailable.
    """

    def __init__(
        self,
        router: QueryRouter,
        vector_retriever: VectorRetriever,
        entity_retriever: EntityRetriever | None,
        context_builder: ContextBuilder,
        generator: Generator | None,
        crag_verifier: CRAGVerifier | None = None,
        aggregation_executor: AggregationExecutor | None = None,
        cross_substrate_executor: CrossSubstrateExecutor | None = None,
    ):
        # generator is Optional to support aggregation-only mode when no LLM is
        # configured. The deterministic aggregation branch (SAG) returns its
        # answer directly from SQL — no LLM required. Non-aggregation queries
        # fall through to a retrieval-only response when generator is None.
        self.router = router
        self.vector_retriever = vector_retriever
        self.entity_retriever = entity_retriever
        self.context_builder = context_builder
        self.generator = generator
        self.crag_verifier = crag_verifier
        self.aggregation_executor = aggregation_executor
        self.cross_substrate_executor = cross_substrate_executor
        self._query_cache: OrderedDict[str, QueryResponse] = OrderedDict()
        self._cache_max = 128

    def query(self, query_text: str, top_k: int = 10) -> QueryResponse:
        """
        Execute a full query pipeline.

        Routes the query, retrieves from appropriate stores,
        builds context, and generates a response.
        """
        # Check cache for exact query match
        cache_key = f"{query_text}:{top_k}"
        if cache_key in self._query_cache:
            cached = self._query_cache[cache_key]
            return replace(
                cached,
                latency_ms=0,
                stage_timings_ms={"cache_hit": 0, "total": 0},
            )

        start = time.perf_counter()

        # Deterministic failure-aggregation branch (SAG pattern).
        # Intercepts "top N / highest / rank" + "failure/failing" queries BEFORE
        # the LLM router. Falls through to normal RAG when no match.
        if self.aggregation_executor is not None:
            agg_start = time.perf_counter()
            agg_result = self.aggregation_executor.try_execute(query_text)
            agg_ms = int((time.perf_counter() - agg_start) * 1000)
            if agg_result is not None and agg_result.tier != "RED":
                elapsed = int((time.perf_counter() - start) * 1000)
                response = QueryResponse(
                    answer=agg_result.context_text,
                    confidence=agg_result.tier,
                    query_path=f"AGGREGATION_{agg_result.tier}",
                    sources=agg_result.sources,
                    chunks_used=len(agg_result.ranked_rows) + sum(
                        len(v) for v in agg_result.evidence_by_part.values()
                    ),
                    latency_ms=elapsed,
                    stage_timings_ms={
                        "aggregation_executor": agg_ms,
                        "total": elapsed,
                    },
                )
                if len(self._query_cache) >= self._cache_max:
                    self._query_cache.popitem(last=False)
                self._query_cache[cache_key] = response
                return response

        # Cross-substrate join queries (cost_per_failure, top_vendors, etc.)
        if self.cross_substrate_executor is not None:
            cs_start = time.perf_counter()
            cs_result = self.cross_substrate_executor.try_execute(query_text)
            cs_ms = int((time.perf_counter() - cs_start) * 1000)
            if cs_result is not None:
                elapsed = int((time.perf_counter() - start) * 1000)
                response = QueryResponse(
                    answer=cs_result.context_text,
                    confidence=cs_result.tier,
                    query_path=f"CROSS_SUBSTRATE_{cs_result.tier}",
                    sources=cs_result.sources,
                    chunks_used=len(cs_result.ranked_rows),
                    latency_ms=elapsed,
                    stage_timings_ms={
                        "cross_substrate": cs_ms,
                        "total": elapsed,
                    },
                )
                return response

        # Fail-closed guard: intercept logistics/PO count queries that
        # don't have a deterministic substrate yet. Prevents the LLM from
        # generating fabricated counts.
        if _detect_unsupported_logistics_count(query_text):
            elapsed = int((time.perf_counter() - start) * 1000)
            response = QueryResponse(
                answer=(
                    "## Logistics / PO Aggregation -- NOT YET SUPPORTED\n\n"
                    "This query requests exact counts for purchase orders, "
                    "receipts, or outstanding items.\n\n"
                    "The deterministic PO-lifecycle substrate has not been "
                    "populated yet. Without it, any numbers would be "
                    "LLM-generated estimates, not exact counts.\n\n"
                    "**Status:** PO-lifecycle substrate is in development.\n\n"
                    "**What you can ask now:**\n"
                    "- Failure-related aggregation (top failing parts, "
                    "failure counts by system/site/year)\n"
                    "- Semantic search about PO-related documents\n"
                    "- Entity lookup for specific PO numbers\n\n"
                    "*This guard ensures the system never presents "
                    "fabricated logistics counts as facts.*"
                ),
                confidence="NOT_SUPPORTED",
                query_path="LOGISTICS_GUARD",
                sources=[],
                chunks_used=0,
                latency_ms=elapsed,
                stage_timings_ms={"logistics_guard": elapsed, "total": elapsed},
            )
            return response

        classification, context, stage_timings = self.retrieve_context(query_text, top_k)

        if context is None:
            elapsed = int((time.perf_counter() - start) * 1000)
            stage_timings["total"] = elapsed
            return QueryResponse(
                answer="[NOT_FOUND] No relevant documents found for this query.",
                confidence="NOT_FOUND",
                query_path=classification.query_type,
                sources=[],
                chunks_used=0,
                latency_ms=elapsed,
                stage_timings_ms=stage_timings,
            )

        # Step 3: Generate
        if self.generator is None:
            # No LLM configured — return retrieval-only response. This path is
            # reached for non-aggregation queries when the system is running in
            # aggregation-only mode. Aggregation queries never reach here
            # because they return early above.
            elapsed = int((time.perf_counter() - start) * 1000)
            stage_timings["total"] = elapsed
            return QueryResponse(
                answer=(
                    "[LLM_UNAVAILABLE] No LLM narration available — showing "
                    "retrieval context only.\n\n" + context.context_text
                ),
                confidence="LLM_UNAVAILABLE",
                query_path=classification.query_type,
                sources=context.sources,
                chunks_used=context.chunk_count,
                latency_ms=elapsed,
                stage_timings_ms=stage_timings,
            )
        step_start = time.perf_counter()
        response = self.generator.generate(context, query_text)
        stage_timings["generation"] = int((time.perf_counter() - step_start) * 1000)
        response.query_path = classification.query_type

        # Step 4: CRAG verification (SEMANTIC and COMPLEX only)
        crag_ms = 0
        if (
            self.crag_verifier
            and getattr(self.crag_verifier.config, "enabled", False)
            and self.crag_verifier.should_verify(classification.query_type)
        ):
            logger.info("CRAG: verifying %s query response", classification.query_type)
            step_start = time.perf_counter()
            response = self.crag_verifier.verify_and_correct(
                response, context, query_text, top_k=top_k,
            )
            crag_ms = int((time.perf_counter() - step_start) * 1000)
        stage_timings["crag"] = crag_ms

        response.latency_ms = int((time.perf_counter() - start) * 1000)
        stage_timings["total"] = response.latency_ms
        response.stage_timings_ms = stage_timings

        # Cache the result (evict oldest if at capacity)
        if len(self._query_cache) >= self._cache_max:
            self._query_cache.popitem(last=False)
        self._query_cache[cache_key] = response

        return response

    def retrieve_context(
        self, query_text: str, top_k: int = 10
    ) -> tuple[QueryClassification, GeneratorContext | None, dict[str, int]]:
        """Classify the query and return the exact context used for generation."""
        stage_timings: dict[str, int] = {}

        step_start = time.perf_counter()
        classification = self.router.classify(query_text)
        stage_timings["router"] = int((time.perf_counter() - step_start) * 1000)

        # Vocab-pack enrichment: tag recognized forms, sites, acronyms
        try:
            from src.vocab.tagging import build_tagging_result
            from pathlib import Path
            vocab_dir = Path(__file__).resolve().parents[2] / "config" / "vocab_packs"
            if vocab_dir.exists():
                vocab_result = build_tagging_result(str(vocab_dir), query_text)
                classification.vocab_tags = {
                    "doc_family": vocab_result.get("doc_family", []),
                    "matched_terms": [
                        {"canonical": t["canonical"], "kind": t["kind"], "domain": t["domain"]}
                        for t in vocab_result.get("matched_terms", [])
                    ],
                }
        except Exception as e:
            logger.debug("Vocab tagging skipped: %s", e)

        # Adaptive top-k: override caller's top_k with query-type-specific value
        retrieve_k, rerank_k = _resolve_adaptive_top_k(classification.query_type)
        effective_top_k = retrieve_k  # retrieve_k used for vector search depth
        logger.info(
            "Query restricted: type=%s, reasoning=%s | adaptive_top_k: retrieve=%d, rerank=%d",
            classification.query_type, classification.reasoning,
            retrieve_k, rerank_k,
        )

        step_start = time.perf_counter()
        if classification.query_type == "COMPLEX":
            context = self._handle_complex(classification, effective_top_k, rerank_k)
        elif classification.query_type in ("ENTITY", "AGGREGATE", "TABULAR"):
            context = self._handle_structured(classification, effective_top_k, rerank_k)
        else:
            context = self._handle_semantic(classification, effective_top_k, rerank_k)
        stage_timings["retrieval"] = int((time.perf_counter() - step_start) * 1000)
        if context is not None:
            stage_timings = _merge_stage_timings(stage_timings, context.stage_timings_ms)

        return classification, context, stage_timings

    def _handle_semantic(
        self, c: QueryClassification, top_k: int, rerank_top_n: int = 5
    ) -> GeneratorContext | None:
        """Pure vector retrieval for semantic queries."""
        guarded_results = self._guarded_semantic_results(c, top_k)
        vector_search_ms = 0
        if guarded_results is not None:
            vector_search_ms = 0
            if not guarded_results:
                return None
            context, build_timings = self.context_builder.build_with_timings(
                guarded_results,
                c.original_query,
                rerank_top_n=rerank_top_n,
            )
            context.stage_timings_ms = _merge_stage_timings(
                {"vector_search": vector_search_ms},
                build_timings,
            )
            return context

        search_query = c.expanded_query or c.original_query
        search_start = time.perf_counter()
        results = self.vector_retriever.search(
            search_query,
            top_k=top_k,
            candidate_pool=self._retrieval_candidate_pool(top_k),
        )
        vector_search_ms = int((time.perf_counter() - search_start) * 1000)
        if not results:
            return None
        context, build_timings = self.context_builder.build_with_timings(
            results, c.original_query, rerank_top_n=rerank_top_n,
        )
        context.stage_timings_ms = _merge_stage_timings(
            {"vector_search": vector_search_ms},
            build_timings,
        )
        return context

    def _handle_structured(
        self, c: QueryClassification, top_k: int, rerank_top_n: int = 5
    ) -> GeneratorContext | None:
        """
        Structured retrieval with vector fallback.

        Tries entity/table stores first. If no structured results,
        falls back to vector search. If both have results, merges them.
        """
        structured_context = None
        structured_timings: dict[str, int] = {}
        if self.entity_retriever:
            structured_start = time.perf_counter()
            structured_result = self.entity_retriever.search(c)
            structured_lookup_ms = int((time.perf_counter() - structured_start) * 1000)
            if structured_result:
                structured_context = structured_result
                structured_timings = _merge_stage_timings(
                    {"structured_lookup": structured_lookup_ms},
                    structured_result.stage_timings_ms,
                )
            else:
                structured_timings = {"structured_lookup": structured_lookup_ms}

        # Always also do vector search for additional context
        search_query = c.expanded_query or c.original_query
        vector_start = time.perf_counter()
        vector_results = self.vector_retriever.search(
            search_query,
            top_k=top_k,
            candidate_pool=self._retrieval_candidate_pool(top_k),
        )
        vector_search_ms = int((time.perf_counter() - vector_start) * 1000)
        vector_context = None
        if vector_results:
            vector_context, build_timings = self.context_builder.build_with_timings(
                vector_results,
                c.original_query,
                rerank_top_n=rerank_top_n,
            )
            vector_context.stage_timings_ms = _merge_stage_timings(
                {"vector_search": vector_search_ms},
                build_timings,
            )

        # Merge contexts
        if structured_context and vector_context:
            merged_text = (
                f"## Structured Data (from entity/table stores)\n\n"
                f"{structured_context.context_text}\n\n"
                f"---\n\n"
                f"## Document Context (from vector search)\n\n"
                f"{vector_context.context_text}"
            )
            merged_sources = list(dict.fromkeys(
                structured_context.sources + vector_context.sources
            ))
            return GeneratorContext(
                context_text=merged_text,
                sources=merged_sources,
                chunk_count=structured_context.result_count + vector_context.chunk_count,
                query_text=c.original_query,
                stage_timings_ms=_merge_stage_timings(
                    structured_timings,
                    vector_context.stage_timings_ms,
                    {"context_merge": 0},
                ),
            )
        elif structured_context:
            return GeneratorContext(
                context_text=structured_context.context_text,
                sources=structured_context.sources,
                chunk_count=structured_context.result_count,
                query_text=c.original_query,
                stage_timings_ms=structured_timings,
            )
        elif vector_context:
            return vector_context
        else:
            return None

    def _handle_complex(
        self, c: QueryClassification, top_k: int, rerank_top_n: int = 8
    ) -> GeneratorContext | None:
        """
        Decompose complex query into sub-queries, fan out, merge results.

        Each sub-query is restricted and routed independently.
        Results are merged into a single context with section headers.
        """
        structured_complex = self._handle_complex_structured(c)
        if structured_complex is not None:
            structured_complex.stage_timings_ms = _merge_stage_timings(
                {"complex_structured": 0},
                structured_complex.stage_timings_ms,
            )
            return structured_complex

        if not c.sub_queries:
            # No decomposition — treat as semantic
            return self._handle_semantic(c, top_k, rerank_top_n)

        parts = []
        all_sources = []
        total_chunks = 0
        merged_timings: dict[str, int] = {}

        for i, sq in enumerate(c.sub_queries, 1):
            sub_classification = QueryClassification(
                query_type=sq.query_type,
                original_query=sq.query_text,
                expanded_query=sq.query_text,
            )

            # Each sub-query gets its own adaptive top-k
            sub_retrieve_k, sub_rerank_k = _resolve_adaptive_top_k(sq.query_type)
            if sq.query_type in ("ENTITY", "AGGREGATE", "TABULAR"):
                ctx = self._handle_structured(sub_classification, sub_retrieve_k, sub_rerank_k)
            else:
                ctx = self._handle_semantic(sub_classification, sub_retrieve_k, sub_rerank_k)

            if ctx:
                parts.append(f"### Sub-query {i}: {sq.query_text}\n\n{ctx.context_text}\n")
                all_sources.extend(ctx.sources)
                total_chunks += ctx.chunk_count
                merged_timings = _merge_stage_timings(merged_timings, ctx.stage_timings_ms)

        if not parts:
            return None

        merged_sources = list(dict.fromkeys(all_sources))
        return GeneratorContext(
            context_text="\n---\n".join(parts),
            sources=merged_sources,
            chunk_count=total_chunks,
            query_text=c.original_query,
            stage_timings_ms=merged_timings,
        )

    def _handle_complex_structured(
        self, c: QueryClassification
    ) -> GeneratorContext | None:
        """Resolve high-signal multi-hop structured queries without LLM fan-out."""
        if not self.entity_retriever:
            return None

        structured = self.entity_retriever.resolve_site_contacts_for_part(c.original_query)
        if not structured:
            return None

        return GeneratorContext(
            context_text=structured.context_text,
            sources=structured.sources,
            chunk_count=structured.result_count,
            query_text=c.original_query,
        )

    def _guarded_semantic_results(
        self, c: QueryClassification, top_k: int
    ) -> list[ChunkResult] | None:
        """
        Apply targeted demo retrieval guards for broad local-Ollama prompts.

        This keeps generic "equipment condition" questions anchored on visit
        reports and logs instead of drifting into unrelated maintenance manuals.
        """
        q = " ".join(c.original_query.lower().split())

        if "general condition" not in q or "recent visit" not in q:
            return None

        search_queries = [
            c.expanded_query or c.original_query,
            "service report maintenance repair status recent visits radar site",
            "maintenance log repair issue recent site visit",
        ]
        merged = self._merge_semantic_searches(search_queries, per_query_top_k=max(top_k, 6))
        prioritized = self._prioritize_visit_condition_results(merged)
        capped = self._cap_results_per_source(prioritized, per_source_limit=3)
        return capped[:top_k]

    def _merge_semantic_searches(
        self, search_queries: list[str], per_query_top_k: int
    ) -> list[ChunkResult]:
        """Run multiple semantic searches and dedupe candidates by chunk id."""
        merged: OrderedDict[str, ChunkResult] = OrderedDict()

        for query in search_queries:
            if not query:
                continue
            for result in self.vector_retriever.search(
                query,
                top_k=per_query_top_k,
                candidate_pool=self._retrieval_candidate_pool(per_query_top_k),
            ):
                if result.chunk_id not in merged:
                    merged[result.chunk_id] = result

        return list(merged.values())

    def _retrieval_candidate_pool(self, top_k: int) -> int:
        """Use a wider retrieval pool only when reranking is actually active."""
        if getattr(self.context_builder, "_reranker", None) is None:
            return top_k
        return max(top_k, getattr(self.vector_retriever, "candidate_pool", top_k))

    def _prioritize_visit_condition_results(
        self, results: list[ChunkResult]
    ) -> list[ChunkResult]:
        """Prefer visit-style sources over generic manuals for condition summaries."""
        if not results:
            return results

        def priority(result: ChunkResult) -> tuple[int, int, int]:
            lower = result.source_path.lower()
            in_curated_corpus = int(
                not any(token in lower for token in ("test_corpus", "thule_fixture"))
            )
            looks_like_visit_artifact = int(
                any(token in lower for token in ("maintenance", "report", "email", "log"))
            )
            field_visit_corpus = int("field_engineer" in lower)
            return (in_curated_corpus, looks_like_visit_artifact, field_visit_corpus)

        return sorted(results, key=priority, reverse=True)

    def _cap_results_per_source(
        self, results: list[ChunkResult], per_source_limit: int
    ) -> list[ChunkResult]:
        """Keep one source from dominating a stitched semantic context."""
        counts: dict[str, int] = {}
        capped: list[ChunkResult] = []

        for result in results:
            count = counts.get(result.source_path, 0)
            if count >= per_source_limit:
                continue
            counts[result.source_path] = count + 1
            capped.append(result)

        return capped
