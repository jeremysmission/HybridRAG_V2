"""Lane 2 follow-on targeted probe: prove the new extractor on the Spares family.

The default logistics OR-clause in tiered_extract.py matches PR&PO and BOM
patterns first via LanceDB's storage order, so a bounded ``--table-limit``
never reaches Spares chunks. This probe bypasses the default list and
scans ONLY ``Initial Spares`` / ``Spares`` paths so per-family evidence
is honest.

Dry-run. Writes a JSON audit artifact next to the main pilot audit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

V2_ROOT = Path(r"C:\HybridRAG_V2")
sys.path.insert(0, str(V2_ROOT))

from scripts.tiered_extract import _stream_logistics_tables  # noqa: E402
from src.store.entity_store import EntityStore  # noqa: E402
from src.store.lance_store import LanceStore  # noqa: E402

LANCE_DIR = V2_ROOT / "data" / "index" / "lancedb"
DEFAULT_ENTITY_DB = (
    V2_ROOT
    / "data"
    / "index"
    / "clean"
    / "tier1_clean_20260413"
    / "entities.sqlite3"
)
DEFAULT_OUT_PATH = V2_ROOT / "docs" / "lane2_followon_spares_probe_2026-04-13.json"


def main() -> None:
    """Parse command-line inputs and run the main lane2 spares probe workflow."""
    parser = argparse.ArgumentParser(description="Lane 2 spares-only probe.")
    parser.add_argument(
        "--entity-db",
        default=str(DEFAULT_ENTITY_DB),
        help="Target entity store path (staged copy for write runs).",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT_PATH),
        help="Audit JSON output path.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Max chunks to scan.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write rows into the entity store (default: dry-run).",
    )
    args = parser.parse_args()

    store = LanceStore(str(LANCE_DIR))
    entity_store = EntityStore(str(args.entity_db))
    print(f"  Lance: {store.count():,} chunks")
    print(f"  Entity DB: {args.entity_db}")
    print(f"  Mode: {'WRITE' if args.write else 'DRY-RUN'}")

    # Narrow to Spares family paths only — not the default logistics OR.
    # We intentionally pass a non-empty list so _stream_logistics_tables
    # does not fall back to LOGISTICS_TABLE_SOURCE_PATTERNS.
    spares_patterns = ["Initial Spares", "Recommended Spares", "Spares"]

    result = _stream_logistics_tables(
        store=store,
        entity_store=entity_store,
        limit=args.limit,
        dry_run=not args.write,
        source_patterns=spares_patterns,
    )
    print("Spares-only dry-run result:")
    for key in (
        "scanned_chunks",
        "candidate_chunks",
        "matched_chunks",
        "raw_row_count",
        "family_candidate_chunks",
        "family_row_counts",
        "family_source_counts",
    ):
        print(f"  {key}: {result.get(key)}")

    out_path = Path(args.out)
    out_path.write_text(
        json.dumps(
            {
                "source_patterns": spares_patterns,
                "limit": args.limit,
                "dry_run": not args.write,
                "entity_db": str(args.entity_db),
                "result": {
                    k: (dict(v) if hasattr(v, "items") else v)
                    for k, v in result.items()
                },
            },
            indent=2,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(f"  wrote {out_path}")
    entity_store.close()
    store.close()


if __name__ == "__main__":
    main()
