"""
Live Phase 2C backfill target reporter for the production 400-query corpus.

Read-only helper:
  - reads the live query JSON
  - reports current backfill counts
  - surfaces the cheapest wins and highest-value missing-context targets
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUERIES = (
    REPO_ROOT / "tests" / "golden_eval" / "production_queries_400_2026-04-12.json"
)

QUERY_TYPE_PRIORITY = {
    "AGGREGATE": 0,
    "TABULAR": 1,
    "ENTITY": 2,
    "SEMANTIC": 3,
    "COMPLEX": 4,
}
FAMILY_PRIORITY = {
    "CDRLs": 0,
    "Logistics": 1,
    "Program Management": 2,
    "Cybersecurity": 3,
    "Site Visits": 4,
    "Systems Engineering": 5,
    "Engineering": 6,
    "SysAdmin": 7,
    "Asset Mgmt": 8,
}


@dataclass
class QueryRow:
    """Structured helper object used by the report phase2c backfill targets workflow."""
    query_id: str
    user_input: str
    persona: str
    expected_query_type: str
    expected_document_family: str
    has_reference: bool
    has_reference_contexts: bool


def _clean_text(value: Any) -> str:
    """Normalize raw text into a simpler form that is easier to compare or display."""
    if value is None:
        return ""
    return str(value).strip()


def load_queries(path: Path) -> list[QueryRow]:
    """Load the data needed for the report phase2c backfill targets workflow."""
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)

    if isinstance(raw, dict):
        if "queries" in raw:
            raw = raw["queries"]
        elif "samples" in raw:
            raw = raw["samples"]
        else:
            raw = list(raw.values())

    rows: list[QueryRow] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        rows.append(
            QueryRow(
                query_id=_clean_text(item.get("query_id") or item.get("id")),
                user_input=_clean_text(item.get("user_input") or item.get("query")),
                persona=_clean_text(item.get("persona")) or "Unknown",
                expected_query_type=_clean_text(
                    item.get("expected_query_type") or item.get("query_type") or "SEMANTIC"
                ),
                expected_document_family=_clean_text(
                    item.get("expected_document_family") or item.get("document_family")
                ),
                has_reference=bool(_clean_text(item.get("reference"))),
                has_reference_contexts=bool(item.get("reference_contexts")),
            )
        )
    return rows


def parse_args() -> argparse.Namespace:
    """Collect command-line options so the script can decide what work to run."""
    parser = argparse.ArgumentParser(
        description="Report live Phase 2C backfill targets for the production query corpus",
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=DEFAULT_QUERIES,
        help="Path to the production query JSON",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=15,
        help="Number of high-value missing-context targets to print",
    )
    return parser.parse_args()


def main() -> int:
    """Parse command-line inputs and run the main report phase2c backfill targets workflow."""
    args = parse_args()
    rows = load_queries(args.queries)

    eligible = [
        row
        for row in rows
        if row.query_id and row.user_input and row.has_reference_contexts
    ]
    full = [
        row
        for row in rows
        if row.query_id and row.user_input and row.has_reference_contexts and row.has_reference
    ]
    eligible_missing_reference = [
        row for row in eligible if not row.has_reference
    ]
    missing_contexts = [
        row
        for row in rows
        if row.query_id and row.user_input and not row.has_reference_contexts
    ]

    print("=" * 72)
    print("  PHASE 2C BACKFILL TARGET REPORT")
    print("=" * 72)
    print(f"Query file: {args.queries.name}")
    print(f"Total query rows: {len(rows)}")
    print(f"Retrieval-side eligible now: {len(eligible)}/{len(rows)}")
    print(f"Fully Phase 2C enriched: {len(full)}/{len(rows)}")
    print(
        "Eligible now but still missing `reference`: "
        f"{len(eligible_missing_reference)}/{len(rows)}"
    )
    print(
        "Blocked for retrieval-side metrics because `reference_contexts` are missing: "
        f"{len(missing_contexts)}/{len(rows)}"
    )
    print()

    if eligible_missing_reference:
        print("Fastest wins: add only `reference`")
        for row in eligible_missing_reference:
            print(
                f"  - {row.query_id} | {row.persona} | "
                f"{row.expected_query_type} | {row.expected_document_family}"
            )
        print()

    print("Missing `reference_contexts` by query type:")
    for key, count in Counter(row.expected_query_type for row in missing_contexts).most_common():
        print(f"  - {key}: {count}")
    print()

    print("Missing `reference_contexts` by family:")
    for key, count in Counter(
        row.expected_document_family for row in missing_contexts
    ).most_common():
        print(f"  - {key}: {count}")
    print()

    print("Recommended starting set:")
    sorted_targets = sorted(
        missing_contexts,
        key=lambda row: (
            QUERY_TYPE_PRIORITY.get(row.expected_query_type, 99),
            FAMILY_PRIORITY.get(row.expected_document_family, 99),
            row.persona,
            row.query_id,
        ),
    )
    for row in sorted_targets[: args.limit]:
        print(
            f"  - {row.query_id} | {row.persona} | {row.expected_query_type} | "
            f"{row.expected_document_family} | {row.user_input}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
