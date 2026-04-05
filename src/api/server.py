"""
FastAPI server bootstrap for HybridRAG V2.

Usage:
  python -m src.api.server
  python -m src.api.server --config config/config.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config.schema import load_config
from src.store.lance_store import LanceStore
from src.store.entity_store import EntityStore
from src.store.relationship_store import RelationshipStore
from src.llm.client import LLMClient
from src.query.embedder import Embedder
from src.query.vector_retriever import VectorRetriever
from src.query.context_builder import ContextBuilder
from src.query.generator import Generator
from src.query.query_router import QueryRouter
from src.query.entity_retriever import EntityRetriever
from src.query.pipeline import QueryPipeline
from src.api.routes import router, init_routes


def create_app(config_path: str = "config/config.yaml") -> FastAPI:
    """Create and configure the FastAPI application."""
    config = load_config(config_path)

    app = FastAPI(
        title="HybridRAG V2",
        description="Tri-store RAG system for IGS/NEXION documents",
        version="0.4.0",
    )

    # Initialize stores
    lance_store = LanceStore(config.paths.lance_db)
    entity_store = EntityStore(config.paths.entity_db)
    relationship_store = RelationshipStore(config.paths.entity_db)

    # Initialize embedder (for query embedding)
    embedder = Embedder(
        model_name="nomic-ai/nomic-embed-text-v1.5",
        dim=768,
        device="cuda",
    )

    # Initialize LLM client
    provider = config.llm.provider if config.llm.provider != "auto" else ""
    llm_client = LLMClient(
        api_base=config.llm.api_base,
        api_version=config.llm.api_version,
        model=config.llm.model,
        deployment=config.llm.deployment,
        max_tokens=config.llm.max_tokens,
        temperature=config.llm.temperature,
        timeout_seconds=config.llm.timeout_seconds,
        provider_override=provider,
    )

    # Initialize query pipeline components
    vector_retriever = VectorRetriever(lance_store, embedder, top_k=config.retrieval.top_k)
    context_builder = ContextBuilder(top_k=config.retrieval.top_k)
    generator = Generator(llm_client)
    query_router = QueryRouter(llm_client)
    entity_retriever = EntityRetriever(
        entity_store=entity_store,
        relationship_store=relationship_store,
        min_confidence=config.extraction.min_confidence,
    )

    # Build unified pipeline
    pipeline = QueryPipeline(
        router=query_router,
        vector_retriever=vector_retriever,
        entity_retriever=entity_retriever,
        context_builder=context_builder,
        generator=generator,
    )

    # Wire routes
    init_routes(lance_store, entity_store, relationship_store, pipeline, generator)
    app.include_router(router)

    chunks = lance_store.count()
    entities = entity_store.count_entities()
    rels = relationship_store.count()
    llm_status = "available" if llm_client.available else "NOT configured"
    print(
        f"V2 server ready: {chunks} chunks, {entities} entities, "
        f"{rels} relationships, LLM={llm_status}"
    )

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="HybridRAG V2 API server")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    host = args.host or config.server.host
    port = args.port or config.server.port

    app = create_app(args.config)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
