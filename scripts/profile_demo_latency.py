"""
Profile warm demo-path latency by pipeline stage.

Runs the 10 demo queries against a configured pipeline, clears the exact-query
 cache between probes, and reports per-stage timing for router, retrieval,
 generation, CRAG, and total wall-clock latency.

Default config is ``config/config.yaml`` (canonical current store). Legacy
sprintN demo configs pointed at ``data/index/sprint6/lancedb`` which is a stale
store and should not be targeted by a bare invocation. Pass ``--config`` to
override if a legacy sprint config is intentionally required.

Usage:
    python scripts/profile_demo_latency.py
    python scripts/profile_demo_latency.py --rounds 2
    python scripts/profile_demo_latency.py --config config/config.sprint9_demo.yaml  # legacy override
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
from src.config.schema import load_config


def _warn_if_sprint6_lance(config_path: str) -> None:
    """Warn loudly when the resolved config points at a legacy sprint6 Lance store."""
    try:
        resolved = load_config(config_path)
    except Exception:
        return
    lance_db = getattr(resolved.paths, "lance_db", "") or ""
    if "sprint6" in lance_db.lower():
        bar = "=" * 72
        print(bar, file=sys.stderr)
        print("WARNING: explicit config points at a legacy sprint6 Lance store.", file=sys.stderr)
        print(f"  config:    {config_path}", file=sys.stderr)
        print(f"  lance_db:  {lance_db}", file=sys.stderr)
        print("  This store is stale. Proceeding only because --config was", file=sys.stderr)
        print("  supplied explicitly. Use the default config to target the", file=sys.stderr)
        print("  canonical current store.", file=sys.stderr)
        print(bar, file=sys.stderr)


def percentile(values: list[int], pct: float) -> int:
    """Compute a percentile so latency or scoring distributions are easier to interpret."""
    if not values:
        return 0
    ordered = sorted(values)
    idx = round((pct / 100.0) * (len(ordered) - 1))
    return int(ordered[idx])


def summarize(values: list[int]) -> dict[str, int | float]:
    """Support the profile demo latency workflow by handling the summarize step."""
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
    """Parse command-line inputs and run the main profile demo latency workflow."""
    parser = argparse.ArgumentParser(description="Profile warm demo latency by pipeline stage.")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help=(
            "Config YAML path. Defaults to config/config.yaml (canonical current "
            "store). Pass a legacy sprintN demo config only if that specific "
            "store is intentionally required."
        ),
    )
    parser.add_argument("--rounds", type=int, default=1, help="Measured rounds to run (default: 1).")
    parser.add_argument("--warmup-rounds", type=int, default=1, help="Unreported warmup rounds (default: 1).")
    parser.add_argument("--output", default=None, help="Optional JSON output path.")
    args = parser.parse_args()

    _warn_if_sprint6_lance(args.config)

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
