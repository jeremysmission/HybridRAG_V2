"""Simple CLI query entrypoint for smoke tests and lane validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add repo root so `scripts.boot` is importable when run as `python -m src.cli.ask`
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.boot import boot_system


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ask a HybridRAG V2 query from the CLI")
    parser.add_argument("query", help="Query text to execute")
    parser.add_argument("--top-k", type=int, default=10, help="Top-k retrieval depth")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to config YAML file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the query result as JSON instead of human-readable text",
    )
    return parser


def _ensure_console_encoding() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    _ensure_console_encoding()

    runtime = None
    try:
        runtime = boot_system(args.config)
        if runtime.pipeline is None:
            print("[BOOT_ERROR] Query pipeline failed to assemble.", file=sys.stderr)
            return 2

        response = runtime.pipeline.query(args.query, top_k=args.top_k)

        payload = {
            "query": args.query,
            "query_path": response.query_path,
            "confidence": response.confidence,
            "sources": response.sources,
            "chunks_used": response.chunks_used,
            "latency_ms": response.latency_ms,
            "answer": response.answer,
        }

        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Query:      {args.query}")
            print(f"Path:       {response.query_path}")
            print(f"Confidence: {response.confidence}")
            print(f"Chunks:     {response.chunks_used}")
            print(f"Latency:    {response.latency_ms} ms")
            print("Sources:")
            if response.sources:
                for source in response.sources:
                    print(f"  - {source}")
            else:
                print("  - (none)")
            print()
            print(response.answer)

        return 0
    finally:
        if runtime is not None:
            for attr_name in ("lance_store", "entity_store", "relationship_store"):
                store = getattr(runtime, attr_name, None)
                close = getattr(store, "close", None)
                if callable(close):
                    close()


if __name__ == "__main__":
    raise SystemExit(main())
