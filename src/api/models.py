"""Request/response Pydantic models for the V2 API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """POST /query request body."""

    query: str = Field(..., min_length=1, description="User question.")
    top_k: int = Field(default=10, ge=1, le=50, description="Max chunks to retrieve.")


class QueryResponseModel(BaseModel):
    """POST /query response body."""

    answer: str
    confidence: str
    query_path: str
    sources: list[str]
    chunks_used: int
    latency_ms: int
    input_tokens: int = 0
    output_tokens: int = 0


class HealthResponse(BaseModel):
    """GET /health response."""

    status: str
    chunks_loaded: int
    entities_loaded: int = 0
    relationships_loaded: int = 0
    llm_available: bool


class EntityStatsResponse(BaseModel):
    """GET /entities/stats response."""

    total_entities: int
    total_table_rows: int
    total_relationships: int
    entity_types: dict[str, int]
    predicate_types: dict[str, int]
