"""Populate installed_base substrate directly from validated xlsx families."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

from src.extraction.installed_base_xlsx_parser import parse_candidate_workbooks
from src.store.installed_base_store import InstalledBaseStore, resolve_installed_base_db_path
from src.store.retrieval_metadata_store import resolve_retrieval_metadata_db_path

logger = logging.getLogger("populate_installed_base_xlsx")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def run_xlsx_pass(
    lance_db_path: str | Path,
    *,
    output_db: str | Path | None = None,
    limit: int | None = None,
) -> dict:
    meta_db = resolve_retrieval_metadata_db_path(lance_db_path)
    if not meta_db.exists():
        raise FileNotFoundError(f"retrieval_metadata.sqlite3 not found at {meta_db}")
    ib_db = Path(output_db) if output_db else resolve_installed_base_db_path(Path(lance_db_path).parent)
    logger.info("XLSX source metadata: %s", meta_db)
    logger.info("XLSX destination DB: %s", ib_db)
    store = InstalledBaseStore(ib_db)
    start = time.perf_counter()
    attempted = 0
    inserted = 0
    batch = []
    for row in parse_candidate_workbooks(meta_db, limit=limit):
        attempted += 1
        batch.append(row)
        if len(batch) >= 500:
            inserted += store.insert_many(batch)
            batch = []
    if batch:
        inserted += store.insert_many(batch)
    stats = {
        "xlsx_rows_attempted": attempted,
        "xlsx_rows_inserted": inserted,
        "elapsed_sec": round(time.perf_counter() - start, 2),
        "coverage": store.coverage_summary(),
        "output_db": str(ib_db),
    }
    store.close()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate installed_base from xlsx families")
    parser.add_argument("--lance-db", default="data/index/lancedb", help="LanceDB path (default: data/index/lancedb)")
    parser.add_argument("--output-db", default=None, help="Optional isolated sqlite output path")
    parser.add_argument("--limit", type=int, default=None, help="Cap candidate xlsx files parsed")
    args = parser.parse_args()

    stats = run_xlsx_pass(args.lance_db, output_db=args.output_db, limit=args.limit)
    logger.info("XLSX populate result: %s", stats)
    print("XLSX PASS:", stats)


if __name__ == "__main__":
    main()
