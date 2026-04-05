"""
FastAPI routes for HybridRAG V2.

Slice 0.3: POST /query and GET /health.
Sprint 1+ adds: POST /query/stream (SSE), GET /audit.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.models import QueryRequest, QueryResponseModel, HealthResponse

router = APIRouter()

# These are set by server.py at startup
_store = None
_retriever = None
_context_builder = None
_generator = None


def init_routes(store, retriever, context_builder, generator):
    """Wire up dependencies — called once at server startup."""
    global _store, _retriever, _context_builder, _generator
    _store = store
    _retriever = retriever
    _context_builder = context_builder
    _generator = generator


@router.post("/query", response_model=QueryResponseModel)
def query(request: QueryRequest):
    """Answer a question using the RAG pipeline."""
    if _store is None or _store.count() == 0:
        raise HTTPException(status_code=503, detail="No data loaded. Run import first.")

    if _generator is None or not _generator.llm.available:
        raise HTTPException(
            status_code=503,
            detail="LLM not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY.",
        )

    # Retrieve
    results = _retriever.search(request.query, top_k=request.top_k)
    if not results:
        return QueryResponseModel(
            answer="[NOT_FOUND] No relevant documents found for this query.",
            confidence="NOT_FOUND",
            query_path="SEMANTIC",
            sources=[],
            chunks_used=0,
            latency_ms=0,
        )

    # Build context
    context = _context_builder.build(results, request.query)

    # Generate
    response = _generator.generate(context, request.query)

    return QueryResponseModel(
        answer=response.answer,
        confidence=response.confidence,
        query_path=response.query_path,
        sources=response.sources,
        chunks_used=response.chunks_used,
        latency_ms=response.latency_ms,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )


@router.get("/health", response_model=HealthResponse)
def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        chunks_loaded=_store.count() if _store else 0,
        llm_available=_generator.llm.available if _generator else False,
    )
