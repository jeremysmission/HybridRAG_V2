"""
Profile warm demo-path latency by pipeline stage.

Runs the 10 demo queries against a configured pipeline, clears the exact-query
 cache between probes, and reports per-stage timing for router, retrieval,
 generation, CRAG, and total wall-clock latency.

Usage:
    python scripts/profile_demo_latency.py --config config/config.sprint9_demo.yaml
    python scripts/profile_demo_latency.py --config config/config.sprint9_demo.yaml --rounds 2
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.boot import boot_system
from scripts.demo_rehearsal import DEMO_QUERIES, run_query


def percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    idx = round((pct / 100.0) * (len(ordered) - 1))
    return int(ordered[idx])


def summarize(values: list[int]) -> dict[str, int | float]:
    if not values:
        return {"count": 0, "avg_ms": 0, "p50_ms": 0, "p95_ms": 0, "min_ms": 0, "max_ms": 0}
    return {
        "count": len(values),
        "avg_ms": round(sum(values) / len(values), 1),
        "p50_ms": percentile(values, 50),
        "p95_ms": percentile(values, 95),
        "min_ms": min(values),
        "max_ms": max(values),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile warm demo latency by pipeline stage.")
    parser.add_argument("--config", default="config/config.sprint9_demo.yaml", help="Config YAML path.")
    parser.add_argument("--rounds", type=int, default=1, help="Measured rounds to run (default: 1).")
    parser.add_argument("--warmup-rounds", type=int, default=1, help="Unreported warmup rounds (default: 1).")
    parser.add_argument("--output", default=None, help="Optional JSON output path.")
    args = parser.parse_args()

    system = boot_system(args.config)
    if system.pipeline is None:
        print("ERROR: Pipeline unavailable. Check LLM configuration.")
        return 1

    pipeline = system.pipeline
    warmup_queries = [dq.query for dq in DEMO_QUERIES]

    print(f"Profiling config: {args.config}")
    print(f"Warmup rounds: {args.warmup_rounds}  |  Measured rounds: {args.rounds}")

    try:
        for warm_round in range(args.warmup_rounds):
            print(f"  Warmup round {warm_round + 1}/{args.warmup_rounds}")
            for query_text in warmup_queries:
                pipeline._query_cache.clear()
                pipeline.query(query_text)

        records: list[dict] = []
        stage_values: dict[str, list[int]] = {
            "router": [],
            "retrieval": [],
            "generation": [],
            "crag": [],
            "total": [],
            "wall_clock": [],
        }

        for round_idx in range(args.rounds):
            print(f"  Measured round {round_idx + 1}/{args.rounds}")
            for dq in DEMO_QUERIES:
                pipeline._query_cache.clear()
                result = run_query(dq, pipeline, show_timing=True)
                record = {
                    "round": round_idx + 1,
                    "query_number": dq.number,
                    "title": dq.title,
                    "query": dq.query,
                    "passed": result.passed,
                    "latency_ms": result.latency_ms,
                    "confidence": result.actual_confidence,
                    "query_path": result.actual_path,
                    "stage_times_ms": result.stage_times,
                    "facts_missing": result.facts_missing,
                    "error": result.error or "",
                }
                records.append(record)

                for stage in stage_values:
                    if stage in result.stage_times:
                        stage_values[stage].append(int(result.stage_times[stage]))

                print(
                    f"    Q{dq.number:<2} {dq.title:<28} "
                    f"{result.latency_ms:>6} ms  "
                    f"path={result.actual_path:<8} conf={result.actual_confidence:<9} "
                    f"{'PASS' if result.passed else 'FAIL'}"
                )

        summary = {stage: summarize(values) for stage, values in stage_values.items()}
        pass_count = sum(1 for record in records if record["passed"])
        report = {
            "timestamp": datetime.now().isoformat(),
            "config": args.config,
            "warmup_rounds": args.warmup_rounds,
            "rounds": args.rounds,
            "queries_per_round": len(DEMO_QUERIES),
            "passes": pass_count,
            "total_runs": len(records),
            "stages": summary,
            "records": records,
        }

        print("\nStage summary")
        for stage, stats in summary.items():
            if stats["count"] == 0:
                continue
            print(
                f"  {stage:<10} avg={stats['avg_ms']:>7} ms  "
                f"p50={stats['p50_ms']:>7} ms  "
                f"p95={stats['p95_ms']:>7} ms"
            )

        if args.output:
            output_path = Path(args.output)
            if not output_path.is_absolute():
                output_path = ROOT / output_path
        else:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = ROOT / "results" / f"demo_latency_profile_{stamp}.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nLatency profile written to: {output_path}")
        return 0
    finally:
        system.entity_store.close()
        system.relationship_store.close()
        system.lance_store.close()


if __name__ == "__main__":
    raise SystemExit(main())
