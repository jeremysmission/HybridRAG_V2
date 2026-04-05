"""
HybridRAG V2 performance benchmark suite.

Measures embedding, LanceDB search, SQLite entity lookup, and full pipeline
latency with P50/P95/P99 percentile reporting.

Usage:
    python -m scripts.benchmark --config config/config.yaml --rounds 10
    python -m scripts.benchmark --skip-gpu --skip-pipeline
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.schema import load_config, V2Config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Percentile helpers
# ---------------------------------------------------------------------------

def percentile(sorted_vals: list[float], pct: float) -> float:
    """Return the pct-th percentile from a pre-sorted list."""
    if not sorted_vals:
        return 0.0
    idx = (pct / 100.0) * (len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return sorted_vals[lo]
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def compute_stats(latencies: list[float]) -> dict:
    """Compute P50/P95/P99/mean/min/max from a list of latencies in seconds."""
    ms = sorted([t * 1000 for t in latencies])
    return {
        "count": len(ms),
        "min_ms": round(ms[0], 3) if ms else 0,
        "max_ms": round(ms[-1], 3) if ms else 0,
        "mean_ms": round(sum(ms) / len(ms), 3) if ms else 0,
        "p50_ms": round(percentile(ms, 50), 3),
        "p95_ms": round(percentile(ms, 95), 3),
        "p99_ms": round(percentile(ms, 99), 3),
    }


# ---------------------------------------------------------------------------
# Sample data for benchmarks
# ---------------------------------------------------------------------------

SAMPLE_TEXTS = [
    "The ionosonde at Thule recorded a foF2 of 8.2 MHz during the storm.",
    "SSgt Marcus Webb is the primary point of contact for site maintenance.",
    "Part ARC-1234 was replaced at Cedar Ridge on 2025-11-15.",
    "The quarterly maintenance report shows 47 unscheduled repairs.",
    "Frequency sweep data indicates degraded performance below 3 MHz.",
    "PO-2025-0042 authorized procurement of FM-220 antenna modules.",
    "Site Gakona experienced power outages affecting data collection.",
    "The SEMS3D-450 sensor array requires calibration every 90 days.",
    "Ionogram quality scores dropped below threshold at 3 Arctic sites.",
    "Replacement schedule for legacy receivers covers FY2026-FY2028.",
]

SAMPLE_QUERIES = {
    "SEMANTIC": "What were the ionospheric conditions during the storm?",
    "ENTITY": "Who is the POC for Thule?",
    "AGGREGATE": "How many unscheduled repairs occurred last quarter?",
    "TABULAR": "Show the maintenance schedule for Arctic sites.",
    "COMPLEX": "Compare ionogram quality at Thule vs Gakona and list POCs.",
}


# ---------------------------------------------------------------------------
# Benchmark: Embedding latency
# ---------------------------------------------------------------------------

def bench_embedding(config: V2Config, rounds: int) -> dict:
    """Benchmark embedding latency at various batch sizes."""
    from src.query.embedder import Embedder

    embedder = Embedder(
        model_name="nomic-ai/nomic-embed-text-v1.5",
        dim=768,
        device="cuda",
    )
    results = {}

    for batch_size in [1, 10, 100, 500]:
        texts = (SAMPLE_TEXTS * ((batch_size // len(SAMPLE_TEXTS)) + 1))[:batch_size]
        latencies = []

        # Warm-up
        embedder.embed_batch(texts[:1])

        for _ in range(rounds):
            start = time.perf_counter()
            embedder.embed_batch(texts)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        stats = compute_stats(latencies)
        stats["batch_size"] = batch_size
        stats["texts_per_sec"] = round(batch_size / (stats["mean_ms"] / 1000), 1) if stats["mean_ms"] > 0 else 0
        results[f"embed_batch_{batch_size}"] = stats
        print(f"  embed batch={batch_size:>4}: "
              f"P50={stats['p50_ms']:>8.2f}ms  P95={stats['p95_ms']:>8.2f}ms  "
              f"P99={stats['p99_ms']:>8.2f}ms  ({stats['texts_per_sec']} texts/sec)")

    return results


# ---------------------------------------------------------------------------
# Benchmark: GPU memory
# ---------------------------------------------------------------------------

def bench_gpu_memory(config: V2Config) -> dict:
    """Measure peak GPU memory during embedding."""
    try:
        import torch
        if not torch.cuda.is_available():
            print("  GPU not available, skipping GPU memory benchmark.")
            return {"gpu_available": False}
    except ImportError:
        print("  torch not installed, skipping GPU memory benchmark.")
        return {"gpu_available": False}

    from src.query.embedder import Embedder

    torch.cuda.reset_peak_memory_stats()
    mem_before = torch.cuda.max_memory_allocated() / (1024 ** 2)

    embedder = Embedder(
        model_name="nomic-ai/nomic-embed-text-v1.5",
        dim=768,
        device="cuda",
    )
    texts = SAMPLE_TEXTS * 50  # 500 texts
    embedder.embed_batch(texts)

    mem_after = torch.cuda.max_memory_allocated() / (1024 ** 2)
    peak_mb = round(mem_after, 1)
    delta_mb = round(mem_after - mem_before, 1)

    result = {
        "gpu_available": True,
        "peak_gpu_mb": peak_mb,
        "delta_gpu_mb": delta_mb,
        "batch_size": len(texts),
    }
    print(f"  GPU peak: {peak_mb} MB  (delta: {delta_mb} MB for {len(texts)} texts)")
    return result


# ---------------------------------------------------------------------------
# Benchmark: LanceDB search
# ---------------------------------------------------------------------------

def bench_lance_search(config: V2Config, rounds: int) -> dict:
    """Benchmark LanceDB hybrid search at various top_k."""
    from src.store.lance_store import LanceStore

    store = LanceStore(config.paths.lance_db)
    if store.count() == 0:
        print("  LanceDB store is empty, skipping search benchmark.")
        return {"store_empty": True}

    # Generate a random query vector (768-dim)
    rng = np.random.default_rng(42)
    query_vec = rng.standard_normal(768).astype(np.float32)
    query_vec /= np.linalg.norm(query_vec)

    results = {}
    for top_k in [10, 30, 50]:
        latencies = []

        # Warm-up
        store.hybrid_search(query_vec, query_text="test", top_k=top_k)

        for _ in range(rounds):
            start = time.perf_counter()
            store.hybrid_search(query_vec, query_text="maintenance report", top_k=top_k)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        stats = compute_stats(latencies)
        stats["top_k"] = top_k
        stats["store_rows"] = store.count()
        results[f"lance_search_top{top_k}"] = stats
        print(f"  lance search top_k={top_k:>3}: "
              f"P50={stats['p50_ms']:>8.2f}ms  P95={stats['p95_ms']:>8.2f}ms  "
              f"P99={stats['p99_ms']:>8.2f}ms")

    store.close()
    return results


# ---------------------------------------------------------------------------
# Benchmark: SQLite entity lookups
# ---------------------------------------------------------------------------

def bench_sqlite_entities(config: V2Config, rounds: int) -> dict:
    """Benchmark SQLite entity lookups and aggregations."""
    from src.store.entity_store import EntityStore

    db_path = config.paths.entity_db
    if not Path(db_path).exists():
        print("  Entity DB not found, skipping SQLite benchmark.")
        return {"db_exists": False}

    store = EntityStore(db_path)
    total = store.count_entities()
    if total == 0:
        print("  Entity store is empty, skipping SQLite benchmark.")
        store.close()
        return {"entity_count": 0}

    results = {}

    # Benchmark: lookup by type
    latencies = []
    for _ in range(rounds):
        start = time.perf_counter()
        store.lookup_entities(entity_type="PERSON", limit=50)
        elapsed = time.perf_counter() - start
        latencies.append(elapsed)

    stats = compute_stats(latencies)
    stats["operation"] = "lookup_by_type"
    stats["entity_count"] = total
    results["sqlite_lookup_type"] = stats
    print(f"  sqlite lookup_by_type:  "
          f"P50={stats['p50_ms']:>8.2f}ms  P95={stats['p95_ms']:>8.2f}ms  "
          f"P99={stats['p99_ms']:>8.2f}ms  ({total} entities)")

    # Benchmark: text pattern search
    latencies = []
    for _ in range(rounds):
        start = time.perf_counter()
        store.lookup_entities(text_pattern="%ARC%", limit=50)
        elapsed = time.perf_counter() - start
        latencies.append(elapsed)

    stats = compute_stats(latencies)
    stats["operation"] = "lookup_pattern"
    results["sqlite_lookup_pattern"] = stats
    print(f"  sqlite lookup_pattern:  "
          f"P50={stats['p50_ms']:>8.2f}ms  P95={stats['p95_ms']:>8.2f}ms  "
          f"P99={stats['p99_ms']:>8.2f}ms")

    # Benchmark: aggregation
    latencies = []
    for _ in range(rounds):
        start = time.perf_counter()
        store.aggregate_entity(entity_type="PART")
        elapsed = time.perf_counter() - start
        latencies.append(elapsed)

    stats = compute_stats(latencies)
    stats["operation"] = "aggregate"
    results["sqlite_aggregate"] = stats
    print(f"  sqlite aggregate:       "
          f"P50={stats['p50_ms']:>8.2f}ms  P95={stats['p95_ms']:>8.2f}ms  "
          f"P99={stats['p99_ms']:>8.2f}ms")

    # Benchmark: type summary
    latencies = []
    for _ in range(rounds):
        start = time.perf_counter()
        store.entity_type_summary()
        elapsed = time.perf_counter() - start
        latencies.append(elapsed)

    stats = compute_stats(latencies)
    stats["operation"] = "type_summary"
    results["sqlite_type_summary"] = stats
    print(f"  sqlite type_summary:    "
          f"P50={stats['p50_ms']:>8.2f}ms  P95={stats['p95_ms']:>8.2f}ms  "
          f"P99={stats['p99_ms']:>8.2f}ms")

    store.close()
    return results


# ---------------------------------------------------------------------------
# Benchmark: Full pipeline
# ---------------------------------------------------------------------------

def bench_pipeline(config: V2Config, rounds: int) -> dict:
    """Benchmark full query pipeline for each query type."""
    from scripts.boot import boot_system

    system = boot_system(config)
    if system.lance_store.count() == 0:
        print("  LanceDB empty, skipping pipeline benchmark.")
        return {"store_empty": True}
    if system.pipeline is None:
        print("  LLM unavailable, skipping pipeline benchmark.")
        return {"llm_available": False}

    results = {}
    for qtype, query in SAMPLE_QUERIES.items():
        latencies = []
        for _ in range(rounds):
            start = time.perf_counter()
            try:
                system.pipeline.query(query, top_k=config.retrieval.top_k)
            except Exception as e:
                logger.warning("Pipeline query failed (%s): %s", qtype, e)
                break
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        if latencies:
            stats = compute_stats(latencies)
            stats["query_type"] = qtype
            stats["query"] = query
            results[f"pipeline_{qtype.lower()}"] = stats
            print(f"  pipeline {qtype:<10}: "
                  f"P50={stats['p50_ms']:>10.2f}ms  P95={stats['p95_ms']:>10.2f}ms  "
                  f"P99={stats['p99_ms']:>10.2f}ms")
        else:
            results[f"pipeline_{qtype.lower()}"] = {"error": "all rounds failed"}
            print(f"  pipeline {qtype:<10}: FAILED")

    system.entity_store.close()
    system.relationship_store.close()
    system.lance_store.close()
    return results


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

def print_summary(all_results: dict) -> None:
    """Print a formatted summary table."""
    print("\n" + "=" * 80)
    print(f"{'Benchmark':<30} {'P50 (ms)':>10} {'P95 (ms)':>10} {'P99 (ms)':>10} {'Mean (ms)':>10}")
    print("-" * 80)

    for key, stats in all_results.items():
        if isinstance(stats, dict) and "p50_ms" in stats:
            print(f"{key:<30} {stats['p50_ms']:>10.2f} {stats['p95_ms']:>10.2f} "
                  f"{stats['p99_ms']:>10.2f} {stats['mean_ms']:>10.2f}")

    print("=" * 80)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="HybridRAG V2 Performance Benchmark")
    parser.add_argument("--config", default="config/config.yaml", help="Config YAML path")
    parser.add_argument("--rounds", type=int, default=10, help="Repetitions per benchmark")
    parser.add_argument("--output", default=None, help="JSON output path for results")
    parser.add_argument("--skip-gpu", action="store_true", help="Skip GPU-dependent tests")
    parser.add_argument("--skip-pipeline", action="store_true", help="Skip full pipeline tests")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    config = load_config(args.config)
    all_results: dict = {
        "config_path": args.config,
        "rounds": args.rounds,
        "hardware_preset": config.hardware_preset,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    print(f"HybridRAG V2 Benchmark — {args.rounds} rounds, preset={config.hardware_preset}")
    print("=" * 80)

    # 1. Embedding latency
    if not args.skip_gpu:
        print("\n[1/5] Embedding latency")
        try:
            all_results["embedding"] = bench_embedding(config, args.rounds)
        except Exception as e:
            print(f"  SKIPPED: {e}")
            all_results["embedding"] = {"error": str(e)}

        # 2. GPU memory
        print("\n[2/5] GPU memory")
        try:
            all_results["gpu_memory"] = bench_gpu_memory(config)
        except Exception as e:
            print(f"  SKIPPED: {e}")
            all_results["gpu_memory"] = {"error": str(e)}
    else:
        print("\n[1/5] Embedding latency — SKIPPED (--skip-gpu)")
        print("[2/5] GPU memory — SKIPPED (--skip-gpu)")
        all_results["embedding"] = {"skipped": True}
        all_results["gpu_memory"] = {"skipped": True}

    # 3. LanceDB search
    print("\n[3/5] LanceDB search latency")
    try:
        lance_results = bench_lance_search(config, args.rounds)
        all_results.update(lance_results)
    except Exception as e:
        print(f"  SKIPPED: {e}")
        all_results["lance_search"] = {"error": str(e)}

    # 4. SQLite entity lookups
    print("\n[4/5] SQLite entity lookups")
    try:
        sqlite_results = bench_sqlite_entities(config, args.rounds)
        all_results.update(sqlite_results)
    except Exception as e:
        print(f"  SKIPPED: {e}")
        all_results["sqlite"] = {"error": str(e)}

    # 5. Full pipeline
    if not args.skip_pipeline:
        print("\n[5/5] Full pipeline latency")
        try:
            pipeline_results = bench_pipeline(config, args.rounds)
            all_results.update(pipeline_results)
        except Exception as e:
            print(f"  SKIPPED: {e}")
            all_results["pipeline"] = {"error": str(e)}
    else:
        print("\n[5/5] Full pipeline — SKIPPED (--skip-pipeline)")
        all_results["pipeline"] = {"skipped": True}

    # Summary
    print_summary(all_results)

    # Write JSON output
    output_path = args.output or f"benchmark_results_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults written to: {output_path}")


if __name__ == "__main__":
    main()
