#!/usr/bin/env python3
"""HybridRAG V2 health check / status dashboard."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Ensure project root is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def _dir_size(p: Path) -> int:
    """Total bytes of files under a directory."""
    if not p.exists():
        return 0
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# -- Collectors ---------------------------------------------------------------

def collect_stores(cfg) -> dict:
    """Collect store counts without making API calls."""
    info: dict = {}

    # LanceDB
    lance_path = Path(cfg.paths.lance_db)
    try:
        from src.store.lance_store import LanceStore
        ls = LanceStore(str(lance_path))
        info["lance_chunks"] = ls.count()
        ls.close()
    except Exception as exc:
        info["lance_chunks"] = f"error: {exc}"
    info["lance_path"] = str(lance_path)

    # Entity store
    ent_path = Path(cfg.paths.entity_db)
    try:
        from src.store.entity_store import EntityStore
        es = EntityStore(str(ent_path))
        info["entity_count"] = es.count_entities()
        info["table_row_count"] = es.count_table_rows()
        info["entity_types"] = es.entity_type_summary()
        es.close()
    except Exception as exc:
        info["entity_count"] = f"error: {exc}"
        info["table_row_count"] = 0
        info["entity_types"] = {}
    info["entity_path"] = str(ent_path)

    # Relationship store (shares entity_db path)
    try:
        from src.store.relationship_store import RelationshipStore
        rs = RelationshipStore(str(ent_path))
        info["relationship_count"] = rs.count()
        info["predicates"] = rs.predicate_summary()
        rs.close()
    except Exception as exc:
        info["relationship_count"] = f"error: {exc}"
        info["predicates"] = {}

    return info


def collect_config(cfg) -> dict:
    return {
        "llm_model": cfg.llm.model,
        "llm_provider": cfg.llm.provider,
        "crag_enabled": cfg.crag.enabled,
        "reranker_enabled": cfg.retrieval.reranker_enabled,
        "top_k": cfg.retrieval.top_k,
        "min_confidence": cfg.extraction.min_confidence,
        "hardware": cfg.hardware_preset,
    }


def collect_api() -> dict:
    info: dict = {}

    # OpenAI key check (no actual call)
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    has_azure = bool(os.environ.get("AZURE_OPENAI_API_KEY"))
    if has_azure:
        info["llm_available"] = "yes (Azure OpenAI)"
    elif has_openai:
        info["llm_available"] = "yes (commercial OpenAI)"
    else:
        info["llm_available"] = "no key set"

    # Ollama check
    try:
        r = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            models = [
                line.split()[0].split(":")[0]
                for line in r.stdout.strip().splitlines()[1:]
                if line.strip()
            ]
            info["ollama"] = f"running ({', '.join(models)})" if models else "running (no models)"
        else:
            info["ollama"] = "not running"
    except FileNotFoundError:
        info["ollama"] = "not installed"
    except Exception:
        info["ollama"] = "not running"

    return info


def collect_gpu() -> dict:
    info: dict = {}
    try:
        import torch
        if torch.cuda.is_available():
            info["cuda"] = "available"
            info["device"] = torch.cuda.get_device_name(0)
            total = torch.cuda.get_device_properties(0).total_memory
            used = torch.cuda.memory_allocated(0)
            info["vram"] = f"{_human_bytes(total)} ({_human_bytes(used)} used)"
        else:
            info["cuda"] = "not available"
    except ImportError:
        info["cuda"] = "torch not installed"
    return info


def collect_disk(cfg) -> dict:
    info: dict = {}
    lance_path = Path(cfg.paths.lance_db)
    ent_path = Path(cfg.paths.entity_db)

    info["lance_size"] = _human_bytes(_dir_size(lance_path))
    info["entity_size"] = _human_bytes(ent_path.stat().st_size) if ent_path.exists() else "0 B"

    usage = shutil.disk_usage(ROOT)
    info["free_space"] = _human_bytes(usage.free)
    return info


# -- Formatters ---------------------------------------------------------------

def format_text(data: dict) -> str:
    s = data["stores"]
    c = data["config"]
    a = data["api"]
    g = data["gpu"]
    d = data["disk"]

    types_str = ", ".join(f"{k}: {v}" for k, v in s.get("entity_types", {}).items()) or "(empty)"
    preds_str = ", ".join(f"{k}: {v}" for k, v in s.get("predicates", {}).items()) or "(empty)"

    lines = [
        "HybridRAG V2 -- Health Check",
        "============================",
        "",
        "Stores:",
        f"  LanceDB:        {s['lance_chunks']} chunks ({s['lance_path']})",
        f"  Entities:       {s['entity_count']} entities, {s['table_row_count']} table rows ({s['entity_path']})",
        f"  Relationships:  {s['relationship_count']} relationships",
        f"  Entity types:   {types_str}",
        f"  Predicates:     {preds_str}",
        "",
        "Config:",
        f"  LLM model:      {c['llm_model']} (provider: {c['llm_provider']})",
        f"  CRAG:           {'enabled' if c['crag_enabled'] else 'disabled'}",
        f"  Reranker:       {'enabled (FlashRank)' if c['reranker_enabled'] else 'disabled'}",
        f"  Top-K:          {c['top_k']}",
        f"  Min confidence: {c['min_confidence']}",
        f"  Hardware:       {c['hardware']}",
        "",
        "API:",
        f"  LLM available:  {a['llm_available']}",
        f"  Ollama:         {a.get('ollama', 'n/a')}",
    ]

    if g:
        lines += [
            "",
            "GPU:",
            f"  CUDA:           {g.get('cuda', 'n/a')}",
        ]
        if "device" in g:
            lines.append(f"  Device:         {g['device']}")
        if "vram" in g:
            lines.append(f"  VRAM:           {g['vram']}")

    lines += [
        "",
        "Disk:",
        f"  LanceDB size:   {d['lance_size']}",
        f"  Entity DB size: {d['entity_size']}",
        f"  Free space:     {d['free_space']}",
    ]
    return "\n".join(lines)


def gather_all(cfg) -> dict:
    return {
        "stores": collect_stores(cfg),
        "config": collect_config(cfg),
        "api": collect_api(),
        "gpu": collect_gpu(),
        "disk": collect_disk(cfg),
    }


# -- Main ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="HybridRAG V2 health check dashboard")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    parser.add_argument("--watch", action="store_true", help="Refresh every 5 seconds")
    args = parser.parse_args()

    from src.config.schema import load_config
    cfg = load_config()

    if args.watch:
        try:
            while True:
                data = gather_all(cfg)
                if args.json:
                    print(json.dumps(data, indent=2))
                else:
                    os.system("cls" if os.name == "nt" else "clear")
                    print(format_text(data))
                    print(f"\n  (refreshing every 5s -- Ctrl+C to stop)")
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nStopped.")
    else:
        data = gather_all(cfg)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(format_text(data))


if __name__ == "__main__":
    main()
