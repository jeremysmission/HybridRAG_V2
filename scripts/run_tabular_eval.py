"""Deterministic row-level tabular eval runner.

Loads a narrow tabular query pack (see
``tests/tabular_eval/tabular_queries_lane2_followon_2026-04-13.json``)
and executes each query directly against an entity store via
``EntityStore.query_tables``. No LLM, no router, no retrieval pipeline.

This is the Lane 2 follow-on's substrate-layer eval: it measures whether
row data is addressable and retrievable at the SQL layer, not whether the
end-to-end RAG pipeline answers a user-facing question. That is intentional.

Usage:

    .venv\\Scripts\\python.exe scripts/run_tabular_eval.py ^
      --pack tests/tabular_eval/tabular_queries_lane2_followon_2026-04-13.json ^
      --config config/config.lane2_followon_stage_2026-04-13.yaml ^
      --report-md docs/TABULAR_EVAL_LANE2_FOLLOWON_RESULTS_2026-04-13.md ^
      --results-json docs/tabular_eval_lane2_followon_results_2026-04-13.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.config.schema import load_config  # noqa: E402
from src.store.entity_store import EntityStore  # noqa: E402


def _check_query(query: dict, store: EntityStore) -> dict:
    """Run a validation check and return whether the expected condition is true."""
    spec = query["query_tables"]
    results = store.query_tables(
        source_pattern=spec.get("source_pattern"),
        header_contains=spec.get("header_contains"),
        value_contains=spec.get("value_contains"),
        limit=500,
    )
    row_count = len(results)
    reasons: list[str] = []
    verdict = "PASS"

    min_rows = int(query.get("expect_min_rows", 1))
    if row_count < min_rows:
        verdict = "FAIL"
        reasons.append(f"row_count {row_count} < expect_min_rows {min_rows}")

    expect_headers = query.get("expect_any_header") or []
    if expect_headers:
        found = False
        for r in results:
            if any(h in r.headers for h in expect_headers):
                found = True
                break
        if not found:
            verdict = "FAIL"
            reasons.append(f"no row had any header in {expect_headers}")

    expect_src = query.get("expect_any_source_contains") or []
    if expect_src:
        found = False
        for r in results:
            if any(needle in r.source_path for needle in expect_src):
                found = True
                break
        if not found:
            verdict = "FAIL"
            reasons.append(f"no row source matched any of {expect_src}")

    expect_tid = query.get("expect_any_table_id_contains") or []
    if expect_tid:
        found = False
        for r in results:
            if any(needle in r.table_id for needle in expect_tid):
                found = True
                break
        if not found:
            verdict = "FAIL"
            reasons.append(f"no row table_id matched any of {expect_tid}")

    sample_rows = []
    for r in results[:3]:
        sample_rows.append({
            "source_path": r.source_path,
            "table_id": r.table_id,
            "row_index": r.row_index,
            "headers": r.headers,
            "values": r.values,
        })

    return {
        "id": query["id"],
        "family": query.get("family"),
        "kind": query.get("kind"),
        "question_plain": query.get("question_plain"),
        "verdict": verdict,
        "row_count": row_count,
        "reasons": reasons,
        "sample_rows": sample_rows,
    }


def main() -> None:
    """Parse command-line inputs and run the main run tabular eval workflow."""
    parser = argparse.ArgumentParser(description="Lane 2 follow-on tabular eval runner")
    parser.add_argument("--pack", required=True, help="Tabular query pack JSON.")
    parser.add_argument("--config", required=True, help="V2 config YAML.")
    parser.add_argument("--report-md", required=True, help="Markdown report output.")
    parser.add_argument("--results-json", required=True, help="JSON results output.")
    args = parser.parse_args()

    pack = json.loads(Path(args.pack).read_text(encoding="utf-8"))
    cfg = load_config(args.config)
    store = EntityStore(cfg.paths.entity_db)

    total_rows = store.count_table_rows()
    print(f"entity_db: {cfg.paths.entity_db}")
    print(f"table_row_count: {total_rows:,}")
    print(f"pack: {pack.get('pack')}")
    print(f"queries: {len(pack['queries'])}")
    print()

    results = []
    pass_count = 0
    for q in pack["queries"]:
        r = _check_query(q, store)
        results.append(r)
        mark = "PASS" if r["verdict"] == "PASS" else "FAIL"
        print(f"  {r['id']:<6} {mark:<4} rows={r['row_count']:<5} {r['kind']}")
        if r["reasons"]:
            for rr in r["reasons"]:
                print(f"           reason: {rr}")
        if r["verdict"] == "PASS":
            pass_count += 1

    summary = {
        "pack": pack.get("pack"),
        "config": args.config,
        "entity_db": str(cfg.paths.entity_db),
        "total_table_rows": total_rows,
        "query_count": len(pack["queries"]),
        "pass_count": pass_count,
        "fail_count": len(pack["queries"]) - pass_count,
        "results": results,
    }
    Path(args.results_json).write_text(
        json.dumps(summary, indent=2), encoding="utf-8", newline="\n"
    )

    lines = [
        f"# Tabular Eval Report — {pack.get('pack')}",
        "",
        f"**Date:** {pack.get('date', 'unknown')}",
        f"**Config:** `{args.config}`",
        f"**Entity DB:** `{cfg.paths.entity_db}`",
        f"**Total table rows in store:** {total_rows:,}",
        f"**Queries:** {len(pack['queries'])}",
        f"**PASS:** {pass_count}",
        f"**FAIL:** {len(pack['queries']) - pass_count}",
        "",
        "## Results",
        "",
        "| ID | Family | Kind | Verdict | Rows | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        notes = "; ".join(r["reasons"]) if r["reasons"] else ""
        lines.append(
            f"| {r['id']} | {r['family']} | {r['kind']} | **{r['verdict']}** | {r['row_count']} | {notes} |"
        )

    lines += ["", "## Sample rows per query", ""]
    for r in results:
        lines.append(f"### {r['id']} — {r['question_plain']}")
        lines.append("")
        if not r["sample_rows"]:
            lines.append("_no rows_")
            lines.append("")
            continue
        for s in r["sample_rows"][:2]:
            lines.append(f"- `{s['source_path'][-120:]}` `{s['table_id'][-40:]}` row={s['row_index']}")
            for h, v in list(zip(s["headers"], s["values"]))[:6]:
                lines.append(f"    - `{h}`: `{str(v)[:100]}`")
            lines.append("")

    Path(args.report_md).write_text(
        "\n".join(lines), encoding="utf-8", newline="\n"
    )
    store.close()
    print()
    print(f"PASS {pass_count}/{len(pack['queries'])}")
    print(f"report: {args.report_md}")
    print(f"json:   {args.results_json}")
    if pass_count < len(pack["queries"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
