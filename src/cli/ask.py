from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.boot import boot_system


def _close_runtime(runtime) -> None:
    for attr in ("lance_store", "entity_store", "relationship_store"):
        obj = getattr(runtime, attr, None)
        close = getattr(obj, "close", None)
        if callable(close):
            close()
    pipeline = getattr(runtime, "pipeline", None)
    aggregation_executor = getattr(pipeline, "aggregation_executor", None)
    for attr in ("store", "po_store"):
        obj = getattr(aggregation_executor, attr, None)
        close = getattr(obj, "close", None)
        if callable(close):
            close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a HybridRAG V2 query from the CLI")
    parser.add_argument("query", nargs="+", help="Query text to execute")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Config path (default: config/config.yaml)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Top-k override for the query pipeline (default: 10)",
    )
    args = parser.parse_args()

    query_text = " ".join(args.query).strip()
    if not query_text:
        raise SystemExit("query text is required")

    runtime = boot_system(args.config)
    try:
        if runtime.pipeline is None:
            raise RuntimeError("Query pipeline did not assemble during boot")
        response = runtime.pipeline.query(query_text, top_k=max(1, int(args.top_k)))
        print(f"Query: {query_text}")
        print(f"Path: {response.query_path}")
        print(f"Confidence: {response.confidence}")
        print(f"Sources: {len(response.sources)}")
        print(response.answer)
    finally:
        _close_runtime(runtime)


if __name__ == "__main__":
    main()
