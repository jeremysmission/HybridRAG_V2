"""
FastAPI routes for HybridRAG V2.

Sprint 1: POST /query, POST /query/stream (SSE), GET /health.
Sprint 2: Router-dispatched queries, entity/relationship endpoints.
"""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.api.models import (
    QueryRequest, QueryResponseModel, HealthResponse,
    EntityStatsResponse,
)
from src.query.generator import SYSTEM_PROMPT

router = APIRouter()

# Set by server.py at startup
_lance_store = None
_entity_store = None
_relationship_store = None
_pipeline = None
_generator = None


def init_routes(lance_store, entity_store, relationship_store, pipeline, generator):
    """Wire up dependencies — called once at server startup."""
    global _lance_store, _entity_store, _relationship_store, _pipeline, _generator
    _lance_store = lance_store
    _entity_store = entity_store
    _relationship_store = relationship_store
    _pipeline = pipeline
    _generator = generator


@router.post("/query", response_model=QueryResponseModel)
def query(request: QueryRequest):
    """Answer a question using the router-dispatched RAG pipeline."""
    if _lance_store is None or _lance_store.count() == 0:
        raise HTTPException(status_code=503, detail="No data loaded. Run import first.")

    if _generator is None or not _generator.llm.available:
        raise HTTPException(
            status_code=503,
            detail="LLM not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY.",
        )

    response = _pipeline.query(request.query, top_k=request.top_k)

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
    """
    if _lance_store is None or _lance_store.count() == 0:
        def err():
            yield f"data: {json.dumps({'type': 'error', 'message': 'No data loaded.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(err(), media_type="text/event-stream")

    if _generator is None or not _generator.llm.available:
        def err():
            yield f"data: {json.dumps({'type': 'error', 'message': 'LLM not configured.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(err(), media_type="text/event-stream")

    # Classify and retrieve
    classification = _pipeline.router.classify(request.query)

    if classification.query_type in ("ENTITY", "AGGREGATE", "TABULAR"):
        context = _pipeline._handle_structured(classification, request.top_k)
    elif classification.query_type == "COMPLEX":
        context = _pipeline._handle_complex(classification, request.top_k)
    else:
        context = _pipeline._handle_semantic(classification, request.top_k)

    if context is None:
        def empty_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': 'No relevant documents found.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    def event_stream():
        start = time.time()

        # Send retrieval metadata
        meta = {
            "type": "metadata",
            "sources": context.sources,
            "chunks_used": context.chunk_count,
            "query_path": classification.query_type,
        }
        yield f"data: {json.dumps(meta)}\n\n"

        # Stream LLM response
        try:
            model_id = _generator.llm.deployment if _generator.llm.provider == "azure" else _generator.llm.model
            response = _generator.llm._client.chat.completions.create(
                model=model_id,
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

            latency_ms = int((time.time() - start) * 1000)
            done = {
                "type": "done",
                "confidence": _generator._parse_confidence(full_text),
                "query_path": classification.query_type,
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
        chunks_loaded=_lance_store.count() if _lance_store else 0,
        entities_loaded=_entity_store.count_entities() if _entity_store else 0,
        relationships_loaded=_relationship_store.count() if _relationship_store else 0,
        llm_available=_generator.llm.available if _generator else False,
    )


@router.get("/entities/stats", response_model=EntityStatsResponse)
def entity_stats():
    """Entity store statistics."""
    if _entity_store is None:
        raise HTTPException(status_code=503, detail="Entity store not initialized.")

    return EntityStatsResponse(
        total_entities=_entity_store.count_entities(),
        total_table_rows=_entity_store.count_table_rows(),
        total_relationships=_relationship_store.count() if _relationship_store else 0,
        entity_types=_entity_store.entity_type_summary(),
        predicate_types=_relationship_store.predicate_summary() if _relationship_store else {},
    )
