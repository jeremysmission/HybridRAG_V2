"""
HybridRAG V2 boot validation script.

Loads config, validates all fields, prints status, exits.
Usage: python scripts/boot.py [--config path/to/config.yaml]
"""

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

# Add project root to path so src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.schema import load_config, V2Config


def boot_system(config: V2Config | str | Path | None = None) -> SimpleNamespace:
    """
    Build the runtime objects used by demo and QA harnesses.

    Returns a SimpleNamespace containing config, stores, clients, and pipeline.
    Leaves the caller responsible for closing stores if needed.
    """
    if config is None:
        cfg = load_config()
    elif isinstance(config, (str, Path)):
        cfg = load_config(str(config))
    else:
        cfg = config

    from src.store.lance_store import LanceStore
    from src.store.entity_store import EntityStore
    from src.store.relationship_store import RelationshipStore
    from src.query.embedder import Embedder
    from src.llm.client import LLMClient
    from src.query.query_router import QueryRouter
    from src.query.vector_retriever import VectorRetriever
    from src.query.entity_retriever import EntityRetriever
    from src.query.context_builder import ContextBuilder
    from src.query.generator import Generator
    from src.query.pipeline import QueryPipeline
    from src.query.crag_verifier import CRAGVerifier

    lance_store = LanceStore(cfg.paths.lance_db)
    entity_store = EntityStore(cfg.paths.entity_db)
    relationship_store = RelationshipStore(cfg.paths.entity_db)
    embedder = Embedder(
        model_name="nomic-ai/nomic-embed-text-v1.5",
        dim=768,
        device="cuda",
    )

    provider = cfg.llm.provider if cfg.llm.provider != "auto" else ""
    llm_client = LLMClient(
        api_base=cfg.llm.api_base,
        api_version=cfg.llm.api_version,
        model=cfg.llm.model,
        deployment=cfg.llm.deployment,
        max_tokens=cfg.llm.max_tokens,
        temperature=cfg.llm.temperature,
        timeout_seconds=cfg.llm.timeout_seconds,
        provider_override=provider,
    )

    query_router = QueryRouter(llm_client)
    vector_retriever = VectorRetriever(
        lance_store, embedder, top_k=cfg.retrieval.top_k
    )
    entity_retriever = EntityRetriever(
        entity_store=entity_store,
        relationship_store=relationship_store,
        min_confidence=cfg.extraction.min_confidence,
    )
    context_builder = ContextBuilder(
        top_k=cfg.retrieval.top_k,
        reranker_enabled=cfg.retrieval.reranker_enabled,
    )
    generator = Generator(llm_client) if llm_client.available else None

    crag_verifier = None
    if cfg.crag.enabled and generator is not None:
        crag_verifier = CRAGVerifier(
            config=cfg.crag,
            llm_client=llm_client,
            vector_retriever=vector_retriever,
            context_builder=context_builder,
            generator=generator,
        )

    pipeline = None
    if generator is not None:
        pipeline = QueryPipeline(
            router=query_router,
            vector_retriever=vector_retriever,
            entity_retriever=entity_retriever,
            context_builder=context_builder,
            generator=generator,
            crag_verifier=crag_verifier,
        )

    return SimpleNamespace(
        config=cfg,
        lance_store=lance_store,
        entity_store=entity_store,
        relationship_store=relationship_store,
        embedder=embedder,
        llm_client=llm_client,
        query_router=query_router,
        vector_retriever=vector_retriever,
        entity_retriever=entity_retriever,
        context_builder=context_builder,
        generator=generator,
        crag_verifier=crag_verifier,
        pipeline=pipeline,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="HybridRAG V2 boot validation")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to config YAML file (default: config/config.yaml)",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("  HybridRAG V2 — Boot Validation")
    print("=" * 50)

    config = load_config(args.config)

    print(f"  Preset:    {config.hardware_preset}")
    print(f"  LLM:       {config.llm.model} (temp={config.llm.temperature})")
    print(f"  Retrieval: top_k={config.retrieval.top_k}, pool={config.retrieval.candidate_pool}")
    print(f"  Reranker:  {'ON' if config.retrieval.reranker_enabled else 'OFF'}")
    print(f"  GLiNER:    {'ON' if config.extraction.gliner_enabled else 'OFF (waiver pending)'}")
    print(f"  GPT-4o NER:{'ON' if config.extraction.gpt4o_extraction else 'OFF'}")
    print(f"  CRAG:      {'ON' if config.crag.enabled else 'OFF (Sprint 3+)'}")
    print(f"  Server:    {config.server.host}:{config.server.port}")
    print(f"  LanceDB:   {config.paths.lance_db}")
    print(f"  Entity DB: {config.paths.entity_db}")
    print(f"  Import:    {config.paths.embedengine_output}")
    api_status = "SET" if config.llm.api_base else "NOT SET (required for queries)"
    print(f"  API Base:  {api_status}")
    print("=" * 50)
    print("  V2 ready.")
    print("=" * 50)


if __name__ == "__main__":
    main()
