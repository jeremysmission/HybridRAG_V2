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
from src.llm.client import LLMClient
from src.query.vector_retriever import VectorRetriever
from src.query.context_builder import ContextBuilder
from src.query.generator import Generator
from src.api.routes import router, init_routes


def create_app(config_path: str = "config/config.yaml") -> FastAPI:
    """Create and configure the FastAPI application."""
    config = load_config(config_path)

    app = FastAPI(
        title="HybridRAG V2",
        description="Tri-store RAG system for IGS/NEXION documents",
        version="0.3.0",
    )

    # Initialize stores
    store = LanceStore(config.paths.lance_db)

    # Initialize embedder (for query embedding)
    from src.query.embedder import Embedder

    embedder = Embedder(
        model_name="nomic-ai/nomic-embed-text-v1.5",
        dim=768,
        device="cuda",
    )

    # Initialize query pipeline
    retriever = VectorRetriever(store, embedder, top_k=config.retrieval.top_k)
    context_builder = ContextBuilder(top_k=config.retrieval.top_k)
    llm_client = LLMClient(
        api_base=config.llm.api_base,
        api_version=config.llm.api_version,
        model=config.llm.model,
        deployment=config.llm.deployment,
        max_tokens=config.llm.max_tokens,
        temperature=config.llm.temperature,
        timeout_seconds=config.llm.timeout_seconds,
    )
    generator = Generator(llm_client)

    # Wire routes
    init_routes(store, retriever, context_builder, generator)
    app.include_router(router)

    chunks = store.count()
    print(f"V2 server ready: {chunks} chunks loaded, LLM={'available' if llm_client.available else 'NOT configured'}")

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
