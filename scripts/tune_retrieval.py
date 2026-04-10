"""
Retrieval parameter sweep — overnight autotune for V2 query pipeline.

Sweeps top_k, candidate_pool, hybrid alpha, and nprobes against the
golden eval queries. Scores each configuration by fact-hit rate on
retrieval context (no LLM needed). Produces a ranked leaderboard.

Designed to run overnight unattended:
  .venv\\Scripts\\python.exe scripts/tune_retrieval.py
  .venv\\Scripts\\python.exe scripts/tune_retrieval.py --questions 30 --rounds 3
  .venv\\Scripts\\python.exe scripts/tune_retrieval.py --quick  # 10 questions, 1 round

Output: results/tune_retrieval_YYYYMMDD_HHMMSS.json + leaderboard to stdout.

Time estimates (primary workstation, 17K chunks, 30 queries):
  --quick (12 configs, 1 round):  ~2 min
  default (72 configs, 3 rounds): ~45 min
  400-Q full (72 configs, 3 rounds, 400 questions): ~10 hours (overnight)

Recommended workflow:
  1. Quick smoke test:  --quick --questions 5
  2. Quick full set:    --quick
  3. Full sweep:        (default, no flags)
  4. Production tune:   --questions 0 (all 400 from tuning corpus) --rounds 3

Jeremy Randall | HybridRAG_V2
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.config.schema import load_config
from src.store.lance_store import LanceStore
from src.store.entity_store import EntityStore
from src.store.relationship_store import RelationshipStore
from src.query.embedder import Embedder
from src.query.vector_retriever import VectorRetriever
from src.query.entity_retriever import EntityRetriever
from src.query.context_builder import ContextBuilder
from src.query.query_router import QueryRouter
from src.llm.client import LLMClient


# ---------------------------------------------------------------------------
# Sweep grid
# ---------------------------------------------------------------------------

DEFAULT_GRID = {
    "top_k": [5, 10, 15, 20],
    "candidate_pool": [20, 30, 50],
    "nprobes": [10, 20, 40],
    "reranker": [True, False],
}
# Full grid: 4 * 3 * 3 * 2 = 72 configs
# At ~25 queries * 3 rounds * ~0.5s/query = ~2700 calls
# Estimated: ~23 min (without reranker configs) to ~45 min (with)

QUICK_GRID = {
    "top_k": [5, 10, 20],
    "candidate_pool": [20, 50],
    "nprobes": [20],
    "reranker": [True, False],
}
# Quick grid: 3 * 2 * 1 * 2 = 12 configs
# At 10 queries * 1 round * ~0.5s/query = ~60 calls
# Estimated: ~1 min


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def check_facts(expected: list[str], context: str) -> tuple[list[str], list[str]]:
    """Check which expected facts appear in context (case-insensitive)."""
    lower = context.lower()
    found = [f for f in expected if f.lower() in lower]
    missing = [f for f in expected if f.lower() not in lower]
    return found, missing


@dataclass
class ConfigResult:
    """Result from one configuration sweep."""

    name: str
    settings: dict
    queries_run: int = 0
    fact_hits: int = 0
    fact_total: int = 0
    retrieval_pass: int = 0
    retrieval_fail: int = 0
    latencies_ms: list[int] = field(default_factory=list)
    errors: int = 0

    @property
    def fact_rate(self) -> float:
        return self.fact_hits / self.fact_total if self.fact_total else 0.0

    @property
    def pass_rate(self) -> float:
        total = self.retrieval_pass + self.retrieval_fail
        return self.retrieval_pass / total if total else 0.0

    @property
    def avg_latency(self) -> float:
        return sum(self.latencies_ms) / len(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def p50_latency(self) -> int:
        if not self.latencies_ms:
            return 0
        s = sorted(self.latencies_ms)
        return s[len(s) // 2]

    @property
    def p95_latency(self) -> int:
        if not self.latencies_ms:
            return 0
        s = sorted(self.latencies_ms)
        return s[int(len(s) * 0.95)]


# ---------------------------------------------------------------------------
# Core sweep
# ---------------------------------------------------------------------------

def build_configurations(grid: dict) -> list[dict]:
    """Generate all combinations from the sweep grid."""
    keys = sorted(grid.keys())
    combos = list(itertools.product(*(grid[k] for k in keys)))
    configs = []
    for combo in combos:
        cfg = dict(zip(keys, combo))
        name = "_".join(f"{k}{v}" for k, v in cfg.items())
        configs.append({"name": name, **cfg})
    return configs


def run_sweep(
    queries: list[dict],
    configurations: list[dict],
    rounds: int,
    config_path: str,
) -> list[ConfigResult]:
    """Run the full parameter sweep."""

    config = load_config(config_path)
    store = LanceStore(str(V2_ROOT / config.paths.lance_db))
    embedder = Embedder(model_name="nomic-ai/nomic-embed-text-v1.5", dim=768, device="cuda")
    entity_db_path = V2_ROOT / config.paths.entity_db
    entity_retriever = None
    if entity_db_path.exists():
        es = EntityStore(str(entity_db_path))
        rs = RelationshipStore(str(entity_db_path))
        entity_retriever = EntityRetriever(es, rs)
    llm = LLMClient()
    router = QueryRouter(llm)

    # Warm up
    retriever = VectorRetriever(store, embedder, top_k=10)
    _ = retriever.search("warm up query", top_k=5)

    total_configs = len(configurations)
    total_calls = total_configs * len(queries) * rounds
    print(f"  Configurations: {total_configs}")
    print(f"  Queries: {len(queries)}")
    print(f"  Rounds: {rounds}")
    print(f"  Total eval calls: {total_calls}")
    print()

    results: list[ConfigResult] = []

    for ci, cfg in enumerate(configurations):
        name = cfg["name"]
        top_k = cfg["top_k"]
        candidate_pool = cfg["candidate_pool"]
        nprobes = cfg["nprobes"]
        reranker = cfg.get("reranker", True)

        print(f"  [{ci+1}/{total_configs}] {name} ...", end="", flush=True)

        retriever = VectorRetriever(
            store, embedder, top_k=candidate_pool, nprobes=nprobes,
        )
        ctx_builder = ContextBuilder(
            top_k=top_k,
            reranker_enabled=reranker,
        )

        cr = ConfigResult(name=name, settings=cfg)

        for _ in range(rounds):
            for q in queries:
                query_text = q["query"]
                expected_facts = q.get("expected_facts", [])

                try:
                    t0 = time.perf_counter()
                    classification = router.classify(query_text)
                    search_query = classification.expanded_query or query_text
                    raw_results = retriever.search(search_query, top_k=candidate_pool)
                    context = ctx_builder.build(raw_results, query_text) if raw_results else None
                    context_text = context.context_text if context else ""

                    # Merge entity results for structured queries
                    if (
                        entity_retriever
                        and classification.query_type in ("ENTITY", "AGGREGATE", "TABULAR")
                    ):
                        structured = entity_retriever.search(classification)
                        if structured and structured.context_text:
                            context_text = f"{structured.context_text}\n\n{context_text}"

                    elapsed_ms = int((time.perf_counter() - t0) * 1000)

                    found, missing = check_facts(expected_facts, context_text)
                    cr.fact_hits += len(found)
                    cr.fact_total += len(expected_facts)
                    cr.queries_run += 1
                    cr.latencies_ms.append(elapsed_ms)

                    if not missing:
                        cr.retrieval_pass += 1
                    else:
                        cr.retrieval_fail += 1

                except Exception as e:
                    cr.errors += 1
                    cr.queries_run += 1

        print(
            f" pass={cr.pass_rate:.0%} fact={cr.fact_rate:.0%} "
            f"p50={cr.p50_latency}ms p95={cr.p95_latency}ms"
        )
        results.append(cr)

    store.close()
    return results


def print_leaderboard(results: list[ConfigResult]) -> None:
    """Print ranked leaderboard."""
    # Sort by pass_rate desc, then fact_rate desc, then p50 asc
    ranked = sorted(
        results,
        key=lambda r: (-r.pass_rate, -r.fact_rate, r.p50_latency),
    )

    print()
    print("=" * 90)
    print(f"  {'Rank':>4s}  {'Configuration':40s}  {'Pass':>5s}  {'Facts':>5s}  "
          f"{'P50':>5s}  {'P95':>5s}  {'Err':>3s}")
    print("=" * 90)

    for i, r in enumerate(ranked):
        print(
            f"  {i+1:4d}  {r.name:40s}  {r.pass_rate:5.0%}  {r.fact_rate:5.0%}  "
            f"{r.p50_latency:5d}  {r.p95_latency:5d}  {r.errors:3d}"
        )

    print("=" * 90)
    winner = ranked[0]
    print(f"  Winner: {winner.name}")
    print(f"  Settings: {json.dumps(winner.settings, indent=2)}")
    print("=" * 90)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Overnight retrieval parameter sweep."
    )
    parser.add_argument(
        "--config", default="config/config.yaml",
        help="V2 config path.",
    )
    parser.add_argument(
        "--questions", type=int, default=0,
        help="Number of golden queries to use (0 = all).",
    )
    parser.add_argument(
        "--rounds", type=int, default=3,
        help="Number of rounds per configuration (for variance).",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick mode: fewer configs, 1 round.",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output JSON path (default: auto-timestamped in results/).",
    )
    args = parser.parse_args()

    # Load golden queries
    golden_path = V2_ROOT / "tests" / "golden_eval" / "golden_queries.json"
    with open(golden_path, encoding="utf-8") as f:
        all_queries = json.load(f)

    # Filter to answerable queries (have expected_facts)
    answerable = [q for q in all_queries if q.get("expected_facts")]
    if args.questions > 0:
        answerable = answerable[:args.questions]

    grid = QUICK_GRID if args.quick else DEFAULT_GRID
    rounds = 1 if args.quick else args.rounds
    configurations = build_configurations(grid)

    print("=" * 60)
    print("  HybridRAG V2 -- Retrieval Parameter Sweep")
    print("=" * 60)
    print(f"  Mode: {'quick' if args.quick else 'full'}")
    print(f"  Golden queries: {len(answerable)} (answerable)")
    print(f"  Grid: {', '.join(f'{k}={v}' for k, v in grid.items())}")

    t_start = time.perf_counter()
    results = run_sweep(answerable, configurations, rounds, args.config)
    t_total = time.perf_counter() - t_start

    print_leaderboard(results)
    print(f"\n  Total time: {t_total:.0f}s ({t_total/60:.1f}min)")

    # Save results
    out_path = args.output
    if not out_path:
        results_dir = V2_ROOT / "results"
        results_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = str(results_dir / f"tune_retrieval_{ts}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "mode": "quick" if args.quick else "full",
            "queries": len(answerable),
            "rounds": rounds,
            "grid": grid,
            "total_seconds": round(t_total, 1),
            "results": [
                {
                    "name": r.name,
                    "settings": r.settings,
                    "pass_rate": round(r.pass_rate, 4),
                    "fact_rate": round(r.fact_rate, 4),
                    "p50_ms": r.p50_latency,
                    "p95_ms": r.p95_latency,
                    "avg_ms": round(r.avg_latency, 1),
                    "queries": r.queries_run,
                    "errors": r.errors,
                }
                for r in sorted(results, key=lambda x: (-x.pass_rate, -x.fact_rate))
            ],
        }, f, indent=2)

    print(f"  Results saved to: {out_path}")


if __name__ == "__main__":
    main()
