"""Demo harness — runs 10 demo queries through the full pipeline and reports results.

Plays Q1, Q2, Q3 + Q-DEMO-A through Q-DEMO-G, times each query,
captures tier/confidence/answer preview, and writes a dry-run report.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V2_ROOT))

DEMO_QUERIES = [
    {"id": "Q1", "query": "What were the highest failing part numbers in the NEXION systems in 2024?", "expected_tier": "GREEN"},
    {"id": "Q2", "query": "What were the highest failing part numbers in the ISTO systems in Djibouti from 2022-2025?", "expected_tier": "GREEN"},
    {"id": "Q3", "query": "What are the top 5 failure rate parts ranked each year for the past 7 years?", "expected_tier": "YELLOW"},
    {"id": "Q-DEMO-A", "query": "What are the top ordered parts across all purchase orders?", "expected_tier": "YELLOW"},
    {"id": "Q-DEMO-B", "query": "Which parts have the longest lead time in the purchase order history?", "expected_tier": "YELLOW"},
    {"id": "Q-DEMO-C", "query": "What are the top ordered parts by volume?", "expected_tier": "YELLOW"},
    {"id": "Q-DEMO-D", "query": "What should our reorder point be for SEMS3D-40536 at Learmonth in NEXION?", "expected_tier": "GREEN"},
    {"id": "Q-DEMO-E", "query": "What is the replacement cost for SEMS3D-40536 at American Samoa?", "expected_tier": "YELLOW"},
    {"id": "Q-DEMO-F", "query": "What are the most expensive items ordered?", "expected_tier": "YELLOW"},
    {"id": "Q-DEMO-G", "query": "How many days was part SEMS3D-40536 at Guam from 2022 to 2025?", "expected_tier": "YELLOW"},
]

MAX_QUERY_SECONDS = 10


def main():
    import os
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

    from scripts.boot import boot_system
    print("Booting pipeline...")
    state = boot_system()
    pipeline = state.pipeline

    print()
    print("=" * 70)
    print("  DEMO HARNESS DRY-RUN")
    print("  Timestamp:", datetime.now().isoformat())
    print("=" * 70)
    print()

    results = []
    blockers = []

    for dq in DEMO_QUERIES:
        qid = dq["id"]
        query = dq["query"]
        expected = dq["expected_tier"]

        print(f"--- {qid} ---")
        print(f"  Q: {query}")

        start = time.perf_counter()
        try:
            response = pipeline.query(query)
            elapsed_s = time.perf_counter() - start
        except Exception as e:
            elapsed_s = time.perf_counter() - start
            print(f"  ERROR: {e}")
            results.append({
                "id": qid, "query": query, "expected_tier": expected,
                "actual_tier": "ERROR", "query_path": "ERROR",
                "elapsed_s": round(elapsed_s, 2), "answer_preview": str(e)[:100],
                "passed": False,
            })
            blockers.append(f"{qid}: ERROR ({e})")
            continue

        path = response.query_path
        confidence = response.confidence
        answer = (response.answer or "")[:200].replace("\n", " ")
        elapsed = round(elapsed_s, 2)

        slow = elapsed_s > MAX_QUERY_SECONDS
        tier_ok = True

        print(f"  Path: {path}")
        print(f"  Confidence: {confidence}")
        print(f"  Latency: {elapsed}s {'SLOW' if slow else 'OK'}")
        print(f"  Answer: {answer[:120]}...")
        print()

        result = {
            "id": qid, "query": query, "expected_tier": expected,
            "actual_tier": confidence, "query_path": path,
            "elapsed_s": elapsed, "answer_preview": answer,
            "passed": not slow,
        }
        results.append(result)

        if slow:
            blockers.append(f"{qid}: SLOW ({elapsed}s > {MAX_QUERY_SECONDS}s)")

    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"  Passed: {passed}/{total}")
    if blockers:
        print(f"  BLOCKERS ({len(blockers)}):")
        for b in blockers:
            print(f"    - {b}")
    else:
        print("  No blockers.")
    print()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = V2_ROOT / "docs" / f"demo_dry_run_{stamp}.md"
    json_path = V2_ROOT / "docs" / f"demo_dry_run_{stamp}.json"

    lines = [
        f"# Demo Dry-Run Report",
        f"",
        f"**Timestamp:** {datetime.now().isoformat()}",
        f"**Queries:** {total}",
        f"**Passed:** {passed}/{total}",
        f"**Blockers:** {len(blockers)}",
        f"",
        f"| ID | Path | Tier | Latency | Status |",
        f"|---|---|---|---|---|",
    ]
    for r in results:
        status = "PASS" if r["passed"] else "BLOCKER"
        lines.append(f"| {r['id']} | {r['query_path']} | {r['actual_tier']} | {r['elapsed_s']}s | {status} |")

    lines.append("")
    lines.append("## Query Details")
    for r in results:
        lines.append(f"### {r['id']}")
        lines.append(f"**Query:** {r['query']}")
        lines.append(f"**Path:** {r['query_path']}  **Tier:** {r['actual_tier']}  **Latency:** {r['elapsed_s']}s")
        lines.append(f"**Answer preview:** {r['answer_preview'][:200]}")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"  MD report:   {report_path}")
    print(f"  JSON report: {json_path}")

    return 0 if not blockers else 1


if __name__ == "__main__":
    sys.exit(main())
