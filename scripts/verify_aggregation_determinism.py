"""Determinism verification for GREEN-tier aggregation queries.

Runs each target query N times and verifies that ranked_rows, tier, and
context_text are byte-identical across all runs. Produces a pass/fail
report suitable for QA evidence.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time

from src.query.aggregation_executor import build_default_executor


TARGET_QUERIES = [
    {
        "id": "Q1",
        "query": "What were the highest failing part numbers in the monitoring systems in 2024?",
        "expected_tier": "GREEN",
    },
    {
        "id": "Q2",
        "query": "What were the highest failing part numbers in the legacy monitoring systems in Djibouti from 2022-2025?",
        "expected_tier": "GREEN",
    },
    {
        "id": "Q3",
        "query": "What are the top 5 failure rate parts ranked each year for the past 7 years?",
        "expected_tier": "YELLOW",
    },
]

RUNS_PER_QUERY = 10


def _hash_result(result) -> str:
    canonical = json.dumps(result.to_dict(), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def main():
    print("=" * 60)
    print("  Aggregation Determinism Verification")
    print("=" * 60)
    print()

    executor = build_default_executor()
    coverage = executor.store.coverage_summary()
    print("Substrate: {:,} events, {:,} distinct parts".format(
        coverage.get("total_events", 0),
        coverage.get("distinct_parts", 0),
    ))
    print("Runs per query: {}".format(RUNS_PER_QUERY))
    print()

    all_pass = True
    report_lines = []

    for tq in TARGET_QUERIES:
        qid = tq["id"]
        query = tq["query"]
        expected_tier = tq["expected_tier"]

        print("--- {} ---".format(qid))
        print("Query: {}".format(query))

        hashes = []
        tiers = []
        row_counts = []
        elapsed_ms = []

        for i in range(RUNS_PER_QUERY):
            start = time.perf_counter()
            result = executor.try_execute(query)
            ms = int((time.perf_counter() - start) * 1000)
            elapsed_ms.append(ms)

            if result is None:
                print("  Run {}: NO MATCH (aggregation intent not detected)".format(i + 1))
                hashes.append("NONE")
                tiers.append("NONE")
                row_counts.append(0)
                continue

            h = _hash_result(result)
            hashes.append(h)
            tiers.append(result.tier)
            n_rows = len(result.ranked_rows) + sum(
                len(v) for v in result.per_year_rows.values()
            )
            row_counts.append(n_rows)

        unique_hashes = set(hashes)
        unique_tiers = set(tiers)
        deterministic = len(unique_hashes) == 1 and "NONE" not in unique_hashes
        tier_consistent = len(unique_tiers) == 1
        tier_correct = unique_tiers == {expected_tier}

        passed = deterministic and tier_consistent and tier_correct

        status = "PASS" if passed else "FAIL"
        print("  Tier: {} (expected {})".format(
            "/".join(unique_tiers), expected_tier))
        print("  Deterministic: {} ({} unique hash(es) across {} runs)".format(
            deterministic, len(unique_hashes), RUNS_PER_QUERY))
        print("  Row counts: {}".format(row_counts[:3]))
        print("  Latency: {:.0f}ms avg, {:.0f}ms max".format(
            sum(elapsed_ms) / len(elapsed_ms), max(elapsed_ms)))
        print("  Hash: {}".format(list(unique_hashes)[0][:16] if unique_hashes else "n/a"))
        print("  Result: {}".format(status))
        print()

        if not passed:
            all_pass = False

        report_lines.append({
            "query_id": qid,
            "query": query,
            "expected_tier": expected_tier,
            "actual_tiers": list(unique_tiers),
            "deterministic": deterministic,
            "unique_hashes": len(unique_hashes),
            "runs": RUNS_PER_QUERY,
            "avg_latency_ms": round(sum(elapsed_ms) / len(elapsed_ms), 1),
            "max_latency_ms": max(elapsed_ms),
            "result": status,
        })

    print("=" * 60)
    print("  Overall: {}".format("ALL PASS" if all_pass else "SOME FAILED"))
    print("=" * 60)

    report_path = "output/aggregation_determinism_report.json"
    try:
        from pathlib import Path
        Path("output").mkdir(exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_lines, f, indent=2)
        print("Report written to: {}".format(report_path))
    except Exception as e:
        print("Could not write report: {}".format(e))

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
