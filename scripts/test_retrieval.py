"""
Test retrieval pipeline — verifies import + search works end-to-end.

Does NOT require LLM credentials. Tests vector store + embedder + retriever.
"""

import sys
from pathlib import Path

v2_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(v2_root))

from src.config.schema import load_config
from src.store.lance_store import LanceStore
from src.query.embedder import Embedder
from src.query.vector_retriever import VectorRetriever
from src.query.context_builder import ContextBuilder


def main():
    config = load_config(str(v2_root / "config" / "config.yaml"))

    store = LanceStore(str(v2_root / config.paths.lance_db))
    print(f"Store: {store.count()} chunks loaded")

    if store.count() == 0:
        print("ERROR: No chunks in store. Run import_embedengine.py first.")
        sys.exit(1)

    embedder = Embedder(
        model_name="nomic-ai/nomic-embed-text-v1.5",
        dim=768,
        device="cuda",
    )

    retriever = VectorRetriever(store, embedder, top_k=3)
    context_builder = ContextBuilder(top_k=3)

    queries = [
        "What part was replaced on the transmitter?",
        "Who is the point of contact for Thule?",
        "What was the transmitter output power after repair?",
    ]

    for query in queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")

        results = retriever.search(query)
        print(f"Results: {len(results)} chunks")

        for i, r in enumerate(results, 1):
            source = r.source_path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
            preview = r.text[:120].replace("\n", " ")
            print(f"  [{i}] score={r.score:.4f} src={source}")
            print(f"      {preview}...")

        ctx = context_builder.build(results, query)
        print(f"Context: {ctx.chunk_count} chunks, {len(ctx.context_text)} chars")

    store.close()
    print("\nAll retrieval tests passed.")


if __name__ == "__main__":
    main()
