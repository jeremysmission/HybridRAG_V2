"""Utility script for comparing two production evaluation result files and summarizing what improved or regressed."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def _load(path: str | Path) -> dict:
    """Load the data needed for the compare production eval results workflow."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _results_by_id(payload: dict) -> dict[str, dict]:
    """Support the compare production eval results workflow by handling the results by id step."""
    return {row["id"]: row for row in payload.get("results", [])}


def _delta(a: int | float, b: int | float) -> str:
    """Support the compare production eval results workflow by handling the delta step."""
    diff = b - a
    sign = "+" if diff >= 0 else ""
    if isinstance(a, float) or isinstance(b, float):
        return f"{sign}{diff:.1f}"
    return f"{sign}{diff}"


def _summary_lines(base: dict, new: dict, overlap: list[tuple[dict, dict]]) -> list[str]:
    """Support the compare production eval results workflow by handling the summary lines step."""
    lines: list[str] = []
    lines.append("# Production Eval Delta")
    lines.append("")
    lines.append("## Run Scope")
    lines.append("")
    lines.append(f"- baseline: `{base.get('run_id', 'unknown')}`")
    lines.append(f"- new: `{new.get('run_id', 'unknown')}`")
    lines.append(f"- baseline queries: `{base.get('total_queries', len(base.get('results', [])))}`")
    lines.append(f"- new queries: `{new.get('total_queries', len(new.get('results', [])))}`")
    lines.append(f"- overlapping IDs compared: `{len(overlap)}`")
    lines.append("")
    lines.append("## Headline Delta")
    lines.append("")
    lines.append(f"- PASS: `{base.get('pass_count', 0)}` -> `{new.get('pass_count', 0)}` ({_delta(base.get('pass_count', 0), new.get('pass_count', 0))})")
    lines.append(f"- PARTIAL: `{base.get('partial_count', 0)}` -> `{new.get('partial_count', 0)}` ({_delta(base.get('partial_count', 0), new.get('partial_count', 0))})")
    lines.append(f"- MISS: `{base.get('miss_count', 0)}` -> `{new.get('miss_count', 0)}` ({_delta(base.get('miss_count', 0), new.get('miss_count', 0))})")
    lines.append(f"- routing correct: `{base.get('routing_correct', 0)}` -> `{new.get('routing_correct', 0)}` ({_delta(base.get('routing_correct', 0), new.get('routing_correct', 0))})")
    lines.append(f"- retrieval P50 ms: `{base.get('p50_pure_retrieval_ms', 0)}` -> `{new.get('p50_pure_retrieval_ms', 0)}` ({_delta(base.get('p50_pure_retrieval_ms', 0), new.get('p50_pure_retrieval_ms', 0))})")
    lines.append(f"- retrieval P95 ms: `{base.get('p95_pure_retrieval_ms', 0)}` -> `{new.get('p95_pure_retrieval_ms', 0)}` ({_delta(base.get('p95_pure_retrieval_ms', 0), new.get('p95_pure_retrieval_ms', 0))})")
    lines.append("")

    verdict_flips = Counter()
    family_delta = defaultdict(lambda: Counter())
    route_flips = Counter()
    improved: list[str] = []
    regressed: list[str] = []
    for b_row, n_row in overlap:
        if b_row["verdict"] != n_row["verdict"]:
            verdict_flips[(b_row["verdict"], n_row["verdict"])] += 1
            if _rank(n_row["verdict"]) > _rank(b_row["verdict"]):
                improved.append(n_row["id"])
            else:
                regressed.append(n_row["id"])
        if b_row["routing_correct"] != n_row["routing_correct"]:
            route_flips[(b_row["routing_correct"], n_row["routing_correct"])] += 1
        family = n_row.get("expected_document_family", "unknown")
        family_delta[family][n_row["verdict"]] += 1

    if verdict_flips:
        lines.append("## Verdict Flips")
        lines.append("")
        for (before, after), count in sorted(verdict_flips.items()):
            lines.append(f"- `{before} -> {after}`: `{count}`")
        lines.append("")

    if route_flips:
        lines.append("## Routing Flips")
        lines.append("")
        for (before, after), count in sorted(route_flips.items()):
            lines.append(f"- `{before} -> {after}`: `{count}`")
        lines.append("")

    family_rows: list[tuple[str, int, int, int]] = []
    base_by_family = _family_counts(base)
    new_by_family = _family_counts(new)
    families = sorted(set(base_by_family) | set(new_by_family))
    for family in families:
        b_pass = base_by_family[family]["PASS"]
        n_pass = new_by_family[family]["PASS"]
        b_partial = base_by_family[family]["PARTIAL"]
        n_partial = new_by_family[family]["PARTIAL"]
        b_miss = base_by_family[family]["MISS"]
        n_miss = new_by_family[family]["MISS"]
        family_rows.append((family, n_pass - b_pass, n_partial - b_partial, n_miss - b_miss))

    lines.append("## Family Delta")
    lines.append("")
    lines.append("| Family | PASS delta | PARTIAL delta | MISS delta |")
    lines.append("| --- | ---: | ---: | ---: |")
    for family, d_pass, d_partial, d_miss in family_rows:
        lines.append(f"| {family} | {d_pass:+d} | {d_partial:+d} | {d_miss:+d} |")
    lines.append("")

    if improved:
        lines.append("## Improved IDs")
        lines.append("")
        lines.append("- " + ", ".join(f"`{qid}`" for qid in improved[:40]))
        lines.append("")
    if regressed:
        lines.append("## Regressed IDs")
        lines.append("")
        lines.append("- " + ", ".join(f"`{qid}`" for qid in regressed[:40]))
        lines.append("")
    return lines


def _family_counts(payload: dict) -> dict[str, Counter]:
    """Support the compare production eval results workflow by handling the family counts step."""
    counts: dict[str, Counter] = defaultdict(Counter)
    for row in payload.get("results", []):
        counts[row.get("expected_document_family", "unknown")][row["verdict"]] += 1
    return counts


def _rank(verdict: str) -> int:
    """Support the compare production eval results workflow by handling the rank step."""
    return {"MISS": 0, "PARTIAL": 1, "PASS": 2}.get(verdict, -1)


def main() -> int:
    """Parse command-line inputs and run the main compare production eval results workflow."""
    parser = argparse.ArgumentParser(description="Compare two production-eval JSON result files.")
    parser.add_argument("--baseline", required=True, help="Older JSON result file")
    parser.add_argument("--new", required=True, help="Newer JSON result file")
    parser.add_argument("--markdown", help="Optional markdown output path")
    args = parser.parse_args()

    base = _load(args.baseline)
    new = _load(args.new)
    base_rows = _results_by_id(base)
    new_rows = _results_by_id(new)
    overlap_ids = sorted(set(base_rows) & set(new_rows))
    overlap = [(base_rows[qid], new_rows[qid]) for qid in overlap_ids]

    lines = _summary_lines(base, new, overlap)
    text = "\n".join(lines) + "\n"
    if args.markdown:
        Path(args.markdown).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
