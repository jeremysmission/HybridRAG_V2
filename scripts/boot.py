"""
HybridRAG V2 boot validation script.

Loads config, validates all fields, prints status, exits.
Usage: python scripts/boot.py [--config path/to/config.yaml]
"""

import argparse
import sys
from pathlib import Path

# Add project root to path so src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.schema import load_config


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
