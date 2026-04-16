#!/usr/bin/env python3
"""
Repeatable count benchmark lane for frozen high-specificity targets.

The benchmark keeps count mode explicit:
  - raw_mentions
  - unique_documents
  - unique_chunks
  - unique_rows

It supports three deterministic surfaces:
  - chunk_exact: exact phrase hits in LanceDB chunk text
  - entity_exact: exact text hits in entities.sqlite3
  - row_exact: exact phrase hits in extracted_tables

Usage:
    .venv\\Scripts\\python.exe scripts\\count_benchmark.py --dry-run
    .venv\\Scripts\\python.exe scripts\\count_benchmark.py --output-dir tests\\golden_eval\\results\\count_benchmark
    .venv\\Scripts\\python.exe scripts\\count_benchmark.py --predictions-json path\\to\\predictions.json
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
DEFAULT_TARGETS = REPO_ROOT / "tests" / "golden_eval" / "count_benchmark_targets_2026-04-15.json"
DEFAULT_LANCE_DB = REPO_ROOT / "data" / "index" / "lancedb"
DEFAULT_ENTITY_DB = REPO_ROOT / "data" / "index" / "entities.sqlite3"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "tests" / "golden_eval" / "results" / "count_benchmark"

COUNT_MODES = ("raw_mentions", "unique_documents", "unique_chunks", "unique_rows")
SURFACES = ("chunk_exact", "entity_exact", "row_exact")


@dataclass(frozen=True)
class FrozenTarget:
    """Structured input record that keeps one unit of work easy to pass around and inspect."""
    target: str
    family: str
    deterministic_family: str
    trust: str
    tranche1_status: str
    surface: str
    query: str
    expected: dict[str, int] | None = None
    notes: str = ""


@dataclass
class CountResult:
    """Small structured record used to keep related results together as the workflow runs."""
    target: str
    family: str
    deterministic_family: str
    surface: str
    tranche1_status: str
    query: str
    counts: dict[str, int]
    expected: dict[str, int] | None = None
    expected_exact_match: bool | None = None
    predicted_counts: dict[str, int | None] | None = None
    prediction_exact_match: bool | None = None
    prediction_max_abs_error: int | None = None
    prediction_per_mode: dict[str, dict[str, int | bool | None]] | None = None
    sample_paths: list[str] = field(default_factory=list)
    sample_chunks: list[str] = field(default_factory=list)
    notes: str = ""


def _lower_like(value: str) -> str:
    """Support the count benchmark workflow by handling the lower like step."""
    escaped = value.lower().replace("'", "''")
    return f"%{escaped}%"


def _count_occurrences(text: str, needle: str) -> int:
    """Support the count benchmark workflow by handling the count occurrences step."""
    if not text or not needle:
        return 0
    return len(re.findall(re.escape(needle.lower()), text.lower()))


def load_target_set(path: Path) -> tuple[str, str, list[FrozenTarget]]:
    """Load the data needed for the count benchmark workflow."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    lane_name = payload.get("name", path.stem)
    lane_date = payload.get("date", "")
    targets: list[FrozenTarget] = []
    for row in payload.get("targets", []):
        targets.append(
            FrozenTarget(
                target=row["target"],
                family=row["family"],
                deterministic_family=row["deterministic_family"],
                trust=row.get("trust", ""),
                tranche1_status=row.get("tranche1_status", ""),
                surface=row["surface"],
                query=row.get("query", row["target"]),
                expected=row.get("expected"),
                notes=row.get("notes", ""),
            )
        )
    return lane_name, lane_date, targets


def parse_modes(value: str) -> tuple[str, ...]:
    """Parse a comma-separated mode list or ``all``."""
    if not value or value == "all":
        return COUNT_MODES
    parsed = tuple(m.strip() for m in value.split(",") if m.strip())
    invalid = [m for m in parsed if m not in COUNT_MODES]
    if invalid:
        raise ValueError(f"invalid count modes: {', '.join(invalid)}")
    return parsed


def select_targets(
    targets: Iterable[FrozenTarget],
    include_deferred: bool,
) -> list[FrozenTarget]:
    """Support the count benchmark workflow by handling the select targets step."""
    selected: list[FrozenTarget] = []
    for target in targets:
        if target.tranche1_status == "audited" or include_deferred:
            selected.append(target)
    return selected


def _normalize_count_map(payload: dict[str, object] | None) -> dict[str, int | None] | None:
    """Support the count benchmark workflow by handling the normalize count map step."""
    if payload is None:
        return None
    out: dict[str, int | None] = {}
    for mode in COUNT_MODES:
        value = payload.get(mode)
        out[mode] = None if value is None else int(value)
    return out


def load_predictions(path: Path) -> dict[str, dict[str, int | None]]:
    """Load a target-keyed prediction map from JSON."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw
    if isinstance(raw, dict):
        rows = raw.get("predictions")
        if rows is None:
            rows = raw.get("results")
    if not isinstance(rows, list):
        raise ValueError(f"prediction payload must contain a list of rows: {path}")

    out: dict[str, dict[str, int | None]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        target = str(row.get("target") or "").strip()
        if not target:
            continue
        counts_payload = row.get("counts")
        if not isinstance(counts_payload, dict):
            counts_payload = row
        normalized = _normalize_count_map(counts_payload)
        if normalized is not None:
            out[target] = normalized
    return out


def compare_count_maps(
    reference: dict[str, int],
    candidate: dict[str, int | None] | None,
    modes: Iterable[str],
) -> tuple[bool | None, int | None, dict[str, dict[str, int | bool | None]] | None]:
    """Compare candidate counts against the deterministic reference."""
    if candidate is None:
        return None, None, None

    exact_all = True
    max_abs_error = 0
    per_mode: dict[str, dict[str, int | bool | None]] = {}
    for mode in modes:
        gold = int(reference[mode])
        pred = candidate.get(mode)
        exact = pred == gold
        if not exact:
            exact_all = False
        abs_error = abs(int(pred) - gold) if pred is not None else None
        if abs_error is not None:
            max_abs_error = max(max_abs_error, abs_error)
        per_mode[mode] = {
            "deterministic": gold,
            "predicted": pred,
            "exact_match": exact,
            "abs_error": abs_error,
        }
    return exact_all, max_abs_error, per_mode


def _count_chunk_exact(store, query: str) -> tuple[dict[str, int], list[str], list[str]]:
    """Support the count benchmark workflow by handling the count chunk exact step."""
    needle = _lower_like(query)
    filter_expr = f"lower(text) LIKE '{needle}' OR lower(enriched_text) LIKE '{needle}'"
    rows = store._table.search().where(filter_expr).select(
        ["chunk_id", "source_path", "text", "enriched_text"]
    ).to_list()
    raw_mentions = 0
    docs: set[str] = set()
    chunks: set[str] = set()
    sample_paths: list[str] = []
    sample_chunks: list[str] = []
    for row in rows:
        canonical = row.get("enriched_text") or row.get("text") or ""
        raw_mentions += _count_occurrences(canonical, query)
        src = row.get("source_path", "") or ""
        cid = row.get("chunk_id", "") or ""
        if src:
            docs.add(src)
        if cid:
            chunks.add(cid)
        if len(sample_paths) < 3 and src:
            sample_paths.append(src)
        if len(sample_chunks) < 3 and cid:
            sample_chunks.append(cid)
    counts = {
        "raw_mentions": raw_mentions,
        "unique_documents": len(docs),
        "unique_chunks": len(chunks),
        "unique_rows": 0,
    }
    return counts, sample_paths, sample_chunks


def _count_entity_exact(conn: sqlite3.Connection, query: str) -> tuple[dict[str, int], list[str], list[str]]:
    """Support the count benchmark workflow by handling the count entity exact step."""
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT source_path, chunk_id, text
        FROM entities
        WHERE lower(text) = lower(?)
        """,
        (query,),
    ).fetchall()
    raw_mentions = len(rows)
    docs = {r[0] for r in rows if r[0]}
    chunks = {r[1] for r in rows if r[1]}
    sample_paths = [r[0] for r in rows[:3] if r[0]]
    sample_chunks = [r[1] for r in rows[:3] if r[1]]
    counts = {
        "raw_mentions": raw_mentions,
        "unique_documents": len(docs),
        "unique_chunks": len(chunks),
        "unique_rows": 0,
    }
    return counts, sample_paths, sample_chunks


def _count_row_exact(conn: sqlite3.Connection, query: str) -> tuple[dict[str, int], list[str], list[str]]:
    """Support the count benchmark workflow by handling the count row exact step."""
    needle = _lower_like(query)
    rows = conn.execute(
        """
        SELECT source_path, table_id, row_index, headers, values_json, chunk_id
        FROM extracted_tables
        WHERE lower(headers) LIKE ? OR lower(values_json) LIKE ?
        """,
        (needle, needle),
    ).fetchall()
    raw_mentions = 0
    docs: set[str] = set()
    chunks: set[str] = set()
    sample_paths: list[str] = []
    sample_chunks: list[str] = []
    for row in rows:
        blob = f"{row[3]} {row[4]}"
        raw_mentions += _count_occurrences(blob, query)
        if row[0]:
            docs.add(row[0])
        if row[5]:
            chunks.add(row[5])
        if len(sample_paths) < 3 and row[0]:
            sample_paths.append(row[0])
        if len(sample_chunks) < 3 and row[5]:
            sample_chunks.append(row[5])
    counts = {
        "raw_mentions": raw_mentions,
        "unique_documents": len(docs),
        "unique_chunks": len(chunks),
        "unique_rows": len(rows),
    }
    return counts, sample_paths, sample_chunks


def count_target(
    target: FrozenTarget,
    lance_store,
    entity_conn: sqlite3.Connection,
    row_conn: sqlite3.Connection,
    modes: Iterable[str],
    predictions_by_target: dict[str, dict[str, int | None]] | None = None,
) -> CountResult:
    """Support the count benchmark workflow by handling the count target step."""
    if target.surface == "chunk_exact":
        counts, sample_paths, sample_chunks = _count_chunk_exact(lance_store, target.query)
    elif target.surface == "entity_exact":
        counts, sample_paths, sample_chunks = _count_entity_exact(entity_conn, target.query)
    elif target.surface == "row_exact":
        counts, sample_paths, sample_chunks = _count_row_exact(row_conn, target.query)
    else:
        raise ValueError(f"Unknown target surface: {target.surface}")

    expected_exact_match = None
    if target.expected:
        expected_exact_match = all(counts.get(mode, -1) == target.expected.get(mode, -2) for mode in modes)

    predicted_counts = None
    prediction_exact_match = None
    prediction_max_abs_error = None
    prediction_per_mode = None
    if predictions_by_target:
        predicted_counts = predictions_by_target.get(target.target)
        prediction_exact_match, prediction_max_abs_error, prediction_per_mode = compare_count_maps(
            counts, predicted_counts, modes
        )

    return CountResult(
        target=target.target,
        family=target.family,
        deterministic_family=target.deterministic_family,
        surface=target.surface,
        tranche1_status=target.tranche1_status,
        query=target.query,
        counts=counts,
        expected=target.expected,
        expected_exact_match=expected_exact_match,
        predicted_counts=predicted_counts,
        prediction_exact_match=prediction_exact_match,
        prediction_max_abs_error=prediction_max_abs_error,
        prediction_per_mode=prediction_per_mode,
        sample_paths=sample_paths,
        sample_chunks=sample_chunks,
        notes=target.notes,
    )


def summarize_results(
    results: list[CountResult],
    modes: Iterable[str],
) -> dict[str, object]:
    """Condense detailed results into a shorter summary that is easier to review."""
    mode_list = tuple(modes)
    expected_total = sum(1 for r in results if r.expected is not None)
    expected_exact = sum(1 for r in results if r.expected_exact_match)
    prediction_total = sum(1 for r in results if r.predicted_counts is not None)
    prediction_exact = sum(1 for r in results if r.prediction_exact_match)
    max_abs_error = max(
        (r.prediction_max_abs_error or 0) for r in results if r.prediction_max_abs_error is not None
    ) if prediction_total else None
    per_mode_prediction_exact: dict[str, int] = {mode: 0 for mode in mode_list}
    for result in results:
        if not result.prediction_per_mode:
            continue
        for mode in mode_list:
            info = result.prediction_per_mode.get(mode)
            if info and info.get("exact_match"):
                per_mode_prediction_exact[mode] += 1
    return {
        "selected_targets": len(results),
        "expected_total": expected_total,
        "expected_exact": expected_exact,
        "prediction_total": prediction_total,
        "prediction_exact": prediction_exact,
        "prediction_max_abs_error": max_abs_error,
        "per_mode_prediction_exact": per_mode_prediction_exact if prediction_total else None,
    }


def build_markdown(
    results: list[CountResult],
    lane_name: str,
    lane_date: str,
    targets_path: Path,
    include_deferred: bool,
    modes: Iterable[str],
    predictions_json: Path | None,
) -> str:
    """Assemble the structured object this workflow needs for its next step."""
    summary = summarize_results(results, modes)
    lines = [
        f"# Count Benchmark Results {lane_date or time.strftime('%Y-%m-%d')}",
        "",
        f"- Lane: `{lane_name}`",
        f"- Target set: `{targets_path}`",
        f"- Include deferred: `{include_deferred}`",
        f"- Count modes: `{', '.join(modes)}`",
        f"- Prediction input: `{predictions_json}`" if predictions_json else "- Prediction input: `none`",
        f"- Selected targets: `{summary['selected_targets']}`",
    ]
    if summary["expected_total"]:
        lines.append(
            f"- Frozen-expectation verification: `{summary['expected_exact']}/{summary['expected_total']}` exact target matches"
        )
    if summary["prediction_total"]:
        lines.append(
            f"- Prediction exact-match rate: `{summary['prediction_exact']}/{summary['prediction_total']}` targets"
        )
        lines.append(
            f"- Prediction max absolute error: `{summary['prediction_max_abs_error']}`"
        )
    lines.extend(
        [
            "",
            "| target | surface | status | raw_mentions | unique_documents | unique_chunks | unique_rows | frozen exact | prediction exact |",
            "|---|---|---|---:|---:|---:|---:|---|---|",
        ]
    )
    for result in results:
        frozen_exact = "" if result.expected_exact_match is None else ("yes" if result.expected_exact_match else "no")
        prediction_exact = "" if result.prediction_exact_match is None else ("yes" if result.prediction_exact_match else "no")
        lines.append(
            f"| `{result.target}` | `{result.surface}` | `{result.tranche1_status}` | "
            f"{result.counts['raw_mentions']} | {result.counts['unique_documents']} | "
            f"{result.counts['unique_chunks']} | {result.counts['unique_rows']} | {frozen_exact} | {prediction_exact} |"
        )
    if summary["prediction_total"]:
        lines.extend(["", "## Prediction Comparison"])
        for mode, exact in (summary["per_mode_prediction_exact"] or {}).items():
            lines.append(f"- `{mode}` exact: `{exact}/{summary['prediction_total']}`")
    return "\n".join(lines) + "\n"


def run_benchmark(
    targets: list[FrozenTarget],
    lance_store,
    entity_conn: sqlite3.Connection,
    row_conn: sqlite3.Connection,
    modes: Iterable[str],
    predictions_by_target: dict[str, dict[str, int | None]] | None = None,
) -> list[CountResult]:
    """Execute one complete stage of the workflow and return its results."""
    return [
        count_target(
            target,
            lance_store,
            entity_conn,
            row_conn,
            modes=modes,
            predictions_by_target=predictions_by_target,
        )
        for target in targets
    ]


def main() -> None:
    """Parse command-line inputs and run the main count benchmark workflow."""
    parser = argparse.ArgumentParser(description="Repeatable count benchmark lane")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS, help="Frozen target-set JSON")
    parser.add_argument("--lance-db", type=Path, default=DEFAULT_LANCE_DB, help="LanceDB chunk store path")
    parser.add_argument("--entity-db", type=Path, default=DEFAULT_ENTITY_DB, help="Entity SQLite path")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for benchmark artifacts")
    parser.add_argument("--modes", default="all", help="Comma-separated count modes or 'all'")
    parser.add_argument("--include-deferred", action="store_true", help="Include deferred targets in addition to audited ones")
    parser.add_argument("--dry-run", action="store_true", help="Print the selected target lane and exit without store access")
    parser.add_argument(
        "--predictions-json",
        type=Path,
        default=None,
        help="Optional model prediction JSON to score against deterministic counts",
    )
    args = parser.parse_args()

    lane_name, lane_date, loaded_targets = load_target_set(args.targets)
    targets = select_targets(loaded_targets, include_deferred=args.include_deferred)
    modes = parse_modes(args.modes)

    if args.dry_run:
        print(f"lane={lane_name} date={lane_date}")
        print(f"targets_path={args.targets}")
        print(f"selected_targets={len(targets)}")
        print(f"count_modes={','.join(modes)}")
        for target in targets:
            print(f"- {target.target} [{target.surface}] {target.tranche1_status} expected={target.expected is not None}")
        return

    from src.store.lance_store import LanceStore

    args.output_dir.mkdir(parents=True, exist_ok=True)
    predictions_by_target = load_predictions(args.predictions_json) if args.predictions_json else None
    store = LanceStore(str(args.lance_db))
    entity_conn = sqlite3.connect(f"file:{args.entity_db.as_posix()}?mode=ro", uri=True)
    entity_conn.row_factory = sqlite3.Row
    row_conn = sqlite3.connect(f"file:{args.entity_db.as_posix()}?mode=ro", uri=True)
    row_conn.row_factory = sqlite3.Row

    try:
        results = run_benchmark(
            targets,
            store,
            entity_conn,
            row_conn,
            modes=modes,
            predictions_by_target=predictions_by_target,
        )
    finally:
        entity_conn.close()
        row_conn.close()
        store.close()

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    json_path = args.output_dir / f"count_benchmark_{timestamp}.json"
    md_path = args.output_dir / f"count_benchmark_{timestamp}.md"
    payload = {
        "lane_name": lane_name,
        "lane_date": lane_date,
        "targets_path": str(args.targets),
        "lance_db": str(args.lance_db),
        "entity_db": str(args.entity_db),
        "selected_target_count": len(targets),
        "modes": list(modes),
        "predictions_json": str(args.predictions_json) if args.predictions_json else None,
        "summary": summarize_results(results, modes),
        "results": [asdict(r) for r in results],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    md_path.write_text(
        build_markdown(
            results,
            lane_name,
            lane_date,
            args.targets,
            args.include_deferred,
            modes,
            args.predictions_json,
        ),
        encoding="utf-8",
        newline="\n",
    )

    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    expected_total = sum(1 for r in results if r.expected is not None)
    expected_exact = sum(1 for r in results if r.expected_exact_match)
    if expected_total:
        print(f"frozen_exact_match={expected_exact}/{expected_total}")
    prediction_total = sum(1 for r in results if r.predicted_counts is not None)
    prediction_exact = sum(1 for r in results if r.prediction_exact_match)
    if prediction_total:
        print(f"prediction_exact_match={prediction_exact}/{prediction_total}")


if __name__ == "__main__":
    main()
