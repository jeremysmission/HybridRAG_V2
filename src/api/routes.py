"""
FastAPI routes for HybridRAG V2.

Sprint 1: POST /query, POST /query/stream (SSE), GET /health.
"""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.api.models import QueryRequest, QueryResponseModel, HealthResponse
from src.query.generator import SYSTEM_PROMPT

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


def _retrieve_and_build_context(request: QueryRequest):
    """Shared retrieval + context building for both endpoints."""
    if _store is None or _store.count() == 0:
        raise HTTPException(status_code=503, detail="No data loaded. Run import first.")

    if _generator is None or not _generator.llm.available:
        raise HTTPException(
            status_code=503,
            detail="LLM not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY.",
        )

    results = _retriever.search(request.query, top_k=request.top_k)
    if not results:
        return None, None

    context = _context_builder.build(results, request.query)
    return results, context


@router.post("/query", response_model=QueryResponseModel)
def query(request: QueryRequest):
    """Answer a question using the RAG pipeline."""
    results, context = _retrieve_and_build_context(request)

    if context is None:
        return QueryResponseModel(
            answer="[NOT_FOUND] No relevant documents found for this query.",
            confidence="NOT_FOUND",
            query_path="SEMANTIC",
            sources=[],
            chunks_used=0,
            latency_ms=0,
        )

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


@router.post("/query/stream")
def query_stream(request: QueryRequest):
    """
    Stream a query answer via Server-Sent Events (SSE).

    Sends retrieval metadata first, then streams LLM tokens.
    Reduces perceived latency by 50-70% (streaming TTFT ~0.5s).
    """
    results, context = _retrieve_and_build_context(request)

    if context is None:
        def empty_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': 'No relevant documents found.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    def event_stream():
        start = time.time()

        # Send retrieval metadata first
        meta = {
            "type": "metadata",
            "sources": context.sources,
            "chunks_used": context.chunk_count,
            "query_path": "SEMANTIC",
        }
        yield f"data: {json.dumps(meta)}\n\n"

        # Stream LLM response
        try:
            response = _generator.llm._client.chat.completions.create(
                model=_generator.llm.deployment,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Context:\n{context.context_text}\n\nQuestion: {request.query}"},
                ],
                temperature=_generator.llm.temperature,
                max_tokens=_generator.llm.max_tokens,
                stream=True,
            )

            full_text = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_text += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            # Send completion event
            latency_ms = int((time.time() - start) * 1000)
            done = {
                "type": "done",
                "confidence": _generator._parse_confidence(full_text),
                "latency_ms": latency_ms,
            }
            yield f"data: {json.dumps(done)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/health", response_model=HealthResponse)
def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        chunks_loaded=_store.count() if _store else 0,
        llm_available=_generator.llm.available if _generator else False,
    )
