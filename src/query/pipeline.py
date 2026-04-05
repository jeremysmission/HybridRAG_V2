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
import time
from dataclasses import dataclass

from src.config.schema import CRAGConfig
from src.query.query_router import QueryRouter, QueryClassification
from src.query.vector_retriever import VectorRetriever
from src.query.entity_retriever import EntityRetriever, StructuredResult
from src.query.context_builder import ContextBuilder, GeneratorContext
from src.query.generator import Generator, QueryResponse
from src.query.crag_verifier import CRAGVerifier

logger = logging.getLogger(__name__)


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
        generator: Generator,
        crag_verifier: CRAGVerifier | None = None,
    ):
        self.router = router
        self.vector_retriever = vector_retriever
        self.entity_retriever = entity_retriever
        self.context_builder = context_builder
        self.generator = generator
        self.crag_verifier = crag_verifier

    def query(self, query_text: str, top_k: int = 10) -> QueryResponse:
        """
        Execute a full query pipeline.

        Routes the query, retrieves from appropriate stores,
        builds context, and generates a response.
        """
        start = time.time()

        # Step 1: Classify
        classification = self.router.classify(query_text)
        logger.info(
            "Query restricted: type=%s, reasoning=%s",
            classification.query_type, classification.reasoning,
        )

        # Step 2: Retrieve based on type
        if classification.query_type == "COMPLEX":
            context = self._handle_complex(classification, top_k)
        elif classification.query_type in ("ENTITY", "AGGREGATE", "TABULAR"):
            context = self._handle_structured(classification, top_k)
        else:
            context = self._handle_semantic(classification, top_k)

        if context is None:
            elapsed = int((time.time() - start) * 1000)
            return QueryResponse(
                answer="[NOT_FOUND] No relevant documents found for this query.",
                confidence="NOT_FOUND",
                query_path=classification.query_type,
                sources=[],
                chunks_used=0,
                latency_ms=elapsed,
            )

        # Step 3: Generate
        response = self.generator.generate(context, query_text)
        response.query_path = classification.query_type

        # Step 4: CRAG verification (SEMANTIC and COMPLEX only)
        if (
            self.crag_verifier
            and getattr(self.crag_verifier.config, "enabled", False)
            and self.crag_verifier.should_verify(classification.query_type)
        ):
            logger.info("CRAG: verifying %s query response", classification.query_type)
            response = self.crag_verifier.verify_and_correct(
                response, context, query_text, top_k=top_k,
            )

        response.latency_ms = int((time.time() - start) * 1000)

        return response

    def _handle_semantic(
        self, c: QueryClassification, top_k: int
    ) -> GeneratorContext | None:
        """Pure vector retrieval for semantic queries."""
        search_query = c.expanded_query or c.original_query
        results = self.vector_retriever.search(search_query, top_k=top_k)
        if not results:
            return None
        return self.context_builder.build(results, c.original_query)

    def _handle_structured(
        self, c: QueryClassification, top_k: int
    ) -> GeneratorContext | None:
        """
        Structured retrieval with vector fallback.

        Tries entity/table stores first. If no structured results,
        falls back to vector search. If both have results, merges them.
        """
        structured_context = None
        if self.entity_retriever:
            structured_result = self.entity_retriever.search(c)
            if structured_result:
                structured_context = structured_result

        # Always also do vector search for additional context
        search_query = c.expanded_query or c.original_query
        vector_results = self.vector_retriever.search(search_query, top_k=top_k)
        vector_context = None
        if vector_results:
            vector_context = self.context_builder.build(vector_results, c.original_query)

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
            )
        elif structured_context:
            return GeneratorContext(
                context_text=structured_context.context_text,
                sources=structured_context.sources,
                chunk_count=structured_context.result_count,
                query_text=c.original_query,
            )
        elif vector_context:
            return vector_context
        else:
            return None

    def _handle_complex(
        self, c: QueryClassification, top_k: int
    ) -> GeneratorContext | None:
        """
        Decompose complex query into sub-queries, fan out, merge results.

        Each sub-query is restricted and routed independently.
        Results are merged into a single context with section headers.
        """
        if not c.sub_queries:
            # No decomposition — treat as semantic
            return self._handle_semantic(c, top_k)

        parts = []
        all_sources = []
        total_chunks = 0

        for i, sq in enumerate(c.sub_queries, 1):
            sub_classification = QueryClassification(
                query_type=sq.query_type,
                original_query=sq.query_text,
                expanded_query=sq.query_text,
            )

            if sq.query_type in ("ENTITY", "AGGREGATE", "TABULAR"):
                ctx = self._handle_structured(sub_classification, top_k)
            else:
                ctx = self._handle_semantic(sub_classification, top_k)

            if ctx:
                parts.append(f"### Sub-query {i}: {sq.query_text}\n\n{ctx.context_text}\n")
                all_sources.extend(ctx.sources)
                total_chunks += ctx.chunk_count

        if not parts:
            return None

        merged_sources = list(dict.fromkeys(all_sources))
        return GeneratorContext(
            context_text="\n---\n".join(parts),
            sources=merged_sources,
            chunk_count=total_chunks,
            query_text=c.original_query,
        )
