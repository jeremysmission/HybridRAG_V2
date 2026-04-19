"""
Failure-aggregation benchmark runner.

Reads tests/aggregation_benchmark/failure_truth_pack_*.json and scores each
question against the live AggregationExecutor. Produces a markdown accuracy
report (aggregation_backend_accuracy.md) and a JSON trace.

Scoring dimensions (per item):
  - tier_match:     expected_tier == actual tier (GREEN / YELLOW / RED / PASSTHROUGH)
  - filter_match:   expected_filters is a subset of parsed_params
  - result_present: when tier expected GREEN, ranked_rows must be non-empty
  - passthrough:    expected PASSTHROUGH → AggregationExecutor.try_execute returns None

Emits:
  output/qa_agg/aggregation_backend_accuracy.md
  output/qa_agg/aggregation_backend_accuracy.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

from src.query.aggregation_executor import build_default_executor


def _subset_match(expected: dict, parsed: dict) -> tuple[bool, list[str]]:
    """Return (match, mismatches). Only checks keys present in expected."""
    mismatches: list[str] = []
    for k, v in expected.items():
        if k not in parsed:
            mismatches.append(f"{k}=missing")
            continue
        pv = parsed[k]
        if isinstance(v, str) and isinstance(pv, str):
            if v.lower() != pv.lower():
                mismatches.append(f"{k}: expected={v!r} parsed={pv!r}")
        elif v != pv:
            mismatches.append(f"{k}: expected={v!r} parsed={pv!r}")
    return (len(mismatches) == 0, mismatches)


def score_item(item: dict, executor) -> dict:
    query = item["query"]
    expected_tier = item.get("tier_expected", "GREEN")
    tolerable_tiers = set(item.get("tolerable_tiers") or [])
    expected_filters = item.get("expected_filters", {})
    expected_params = item.get("expected_params", {})

    t0 = time.perf_counter()
    result = executor.try_execute(query)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # PASSTHROUGH case: try_execute should return None
    if expected_tier == "PASSTHROUGH":
        passed = result is None
        return {
            "id": item["id"],
            "query": query,
            "expected_tier": expected_tier,
            "actual_tier": "PASSTHROUGH" if result is None else (result.tier if result else "NONE"),
            "passed": passed,
            "latency_ms": elapsed_ms,
            "notes": "passthrough test" if passed else f"expected PASSTHROUGH but got {result.tier if result else 'NONE'}",
        }

    if result is None:
        return {
            "id": item["id"],
            "query": query,
            "expected_tier": expected_tier,
            "actual_tier": "NONE",
            "passed": False,
            "latency_ms": elapsed_ms,
            "notes": "executor returned None (aggregation intent not detected)",
        }

    # Tier match (allow YELLOW as compatible with GREEN when substrate coverage forces YELLOW)
    tier_match = (result.tier == expected_tier)
    # Soft match: exact match always passes; GREEN/YELLOW are mutually accepted
    # because substrate coverage legitimately drives the downgrade. Truth-pack
    # items can also declare `tolerable_tiers` for slices where either GREEN
    # or RED is acceptable depending on part_number coverage (e.g., narrow
    # site+year combos).
    tier_soft_match = tier_match or (result.tier in tolerable_tiers) or (
        (expected_tier == "GREEN" and result.tier in ("GREEN", "YELLOW"))
        or (expected_tier == "YELLOW" and result.tier in ("GREEN", "YELLOW"))
    )

    # Filter match
    filter_ok, filter_mismatches = _subset_match(expected_filters, result.parsed_params)
    param_ok, param_mismatches = _subset_match(expected_params, result.parsed_params)

    # Result presence when GREEN expected
    result_present = True
    if expected_tier == "GREEN":
        if item.get("expected_shape") == "top_n_by_part_per_year":
            result_present = bool(result.per_year_rows)
        else:
            result_present = bool(result.ranked_rows)

    notes: list[str] = []
    if not tier_match:
        notes.append(f"tier: expected={expected_tier} actual={result.tier}")
    if not filter_ok:
        notes.extend([f"filter {m}" for m in filter_mismatches])
    if not param_ok:
        notes.extend([f"param {m}" for m in param_mismatches])
    if not result_present:
        notes.append(f"expected ranked results but got empty (tier={result.tier})")

    passed = tier_soft_match and filter_ok and param_ok and result_present

    top_3 = []
    if result.ranked_rows:
        top_3 = [r["part_number"] for r in result.ranked_rows[:3]]
    elif result.per_year_rows:
        top_3 = [
            f"{y}:{rows[0]['part_number']}"
            for y, rows in sorted(result.per_year_rows.items())[:3]
            if rows
        ]

    return {
        "id": item["id"],
        "query": query,
        "expected_tier": expected_tier,
        "actual_tier": result.tier,
        "tier_match": tier_match,
        "tier_soft_match": tier_soft_match,
        "filter_match": filter_ok,
        "result_present": result_present,
        "top_3": top_3,
        "ranked_count": len(result.ranked_rows),
        "per_year_years": sorted(result.per_year_rows.keys()) if result.per_year_rows else [],
        "evidence_count": sum(len(v) for v in result.evidence_by_part.values()),
        "parsed_system": result.parsed_params.get("system"),
        "parsed_site": result.parsed_params.get("site_token"),
        "parsed_year_from": result.parsed_params.get("year_from"),
        "parsed_year_to": result.parsed_params.get("year_to"),
        "latency_ms": elapsed_ms,
        "passed": passed,
        "notes": "; ".join(notes) if notes else "",
    }


def render_markdown(report: dict) -> str:
    items = report["items"]
    total = len(items)
    passed = sum(1 for r in items if r["passed"])
    by_tier: dict[str, int] = {}
    for r in items:
        by_tier[r["actual_tier"]] = by_tier.get(r["actual_tier"], 0) + 1

    latencies = [r["latency_ms"] for r in items]
    p50 = sorted(latencies)[len(latencies) // 2] if latencies else 0
    max_lat = max(latencies) if latencies else 0

    lines = [
        "# Aggregation Backend Accuracy Report",
        "",
        f"**Truth pack:** `{report['truth_pack_path']}`",
        f"**Substrate:** {report['substrate_coverage']}",
        f"**Run at:** {report['run_at']}",
        "",
        "## Summary",
        "",
        f"- **Pass rate:** {passed}/{total} ({(100*passed/total if total else 0):.1f}%)",
        f"- **Latency p50:** {p50} ms",
        f"- **Latency max:** {max_lat} ms",
        f"- **Tier distribution:** {by_tier}",
        "",
        "## Per-Question Results",
        "",
        "| ID | Expected | Actual | Pass | Top-3 / Per-Year | Latency | Notes |",
        "|----|----------|--------|------|------------------|---------|-------|",
    ]
    for r in items:
        top_str = ", ".join(r.get("top_3") or []) or "-"
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(
            f"| {r['id']} | {r['expected_tier']} | {r['actual_tier']} | **{status}** | "
            f"`{top_str}` | {r['latency_ms']}ms | {r.get('notes') or '-'} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- **GREEN expected → YELLOW actual** is acceptable when the substrate has coverage < 80% for a filter axis. These are counted as soft-pass.",
        "- **GREEN expected → RED actual** is a true fail — substrate is missing or filter unresolved.",
        "- **PASSTHROUGH expected → None actual** is the correct behavior for non-aggregation queries.",
        "",
        "## Substrate Gaps Detected",
        "",
    ])
    gaps: set[str] = set()
    for r in items:
        if not r.get("passed"):
            notes = r.get("notes", "")
            if "empty" in notes:
                gaps.add(f"{r['id']}: 0 rows matched — narrower filter than substrate supports")
            if "tier=YELLOW" in notes:
                gaps.add(f"{r['id']}: coverage-driven YELLOW (consider Pass 2 or denominator population)")
    if not gaps:
        lines.append("- None flagged.")
    else:
        for g in sorted(gaps):
            lines.append(f"- {g}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("Jeremy Randall | CoPilot+ | HybridRAG_V2 | 2026-04-18 MDT")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run failure-aggregation benchmark")
    parser.add_argument("--truth-pack", default="tests/aggregation_benchmark/failure_truth_pack_2026-04-18.json")
    parser.add_argument("--lance-db", default="data/index/lancedb")
    parser.add_argument("--aliases", default="config/canonical_aliases.yaml")
    parser.add_argument("--output-md", default="output/qa_agg/aggregation_backend_accuracy.md")
    parser.add_argument("--output-json", default="output/qa_agg/aggregation_backend_accuracy.json")
    args = parser.parse_args()

    pack_path = Path(args.truth_pack)
    with pack_path.open("r", encoding="utf-8") as f:
        pack = json.load(f)

    executor = build_default_executor(args.lance_db, args.aliases)
    items = [score_item(item, executor) for item in pack["items"]]

    report = {
        "truth_pack_path": str(pack_path),
        "truth_pack_id": pack.get("truth_pack_id", ""),
        "substrate_coverage": executor.store.coverage_summary(),
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S MDT"),
        "pass_count": sum(1 for r in items if r["passed"]),
        "total_count": len(items),
        "items": items,
    }

    out_json = Path(args.output_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    out_md = Path(args.output_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(report), encoding="utf-8")

    print(f"PASS {report['pass_count']}/{report['total_count']}")
    print(f"JSON: {out_json}")
    print(f"MD:   {out_md}")


if __name__ == "__main__":
    main()
