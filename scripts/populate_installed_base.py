"""
Populate installed_base.db from existing V2 substrate.

Two-pass strategy:
  PASS 1 (fast) — derive candidate installed-base docs from retrieval_metadata.
  PASS 2 (optional, heavier) — scan installed-base candidate chunks and extract
  part_number / serial_number / quantity rows.

Supports an explicit output DB path so a lane can isolate installed-base
experiments instead of writing straight into shared data/index/.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

from src.extraction.installed_base_extractor import (
    extract_chunk_installed_base_from_iter,
    is_installed_base_candidate_path,
    populate_from_path_derived_installed_base,
)
from src.extraction.installed_base_xlsx_parser import parse_candidate_workbooks
from src.store.installed_base_store import InstalledBaseStore, resolve_installed_base_db_path
from src.store.retrieval_metadata_store import resolve_retrieval_metadata_db_path

logger = logging.getLogger("populate_installed_base")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _resolve_output_db(lance_db_path: str | Path, output_db: str | Path | None) -> Path:
    if output_db:
        path = Path(output_db)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return resolve_installed_base_db_path(Path(lance_db_path).parent)


def run_pass1(lance_db_path: str | Path, *, output_db: str | Path | None = None) -> dict:
    meta_db = resolve_retrieval_metadata_db_path(lance_db_path)
    if not meta_db.exists():
        raise FileNotFoundError(f"retrieval_metadata.sqlite3 not found at {meta_db}")
    ib_db = _resolve_output_db(lance_db_path, output_db)
    logger.info("Pass 1 source:      %s", meta_db)
    logger.info("Pass 1 destination: %s", ib_db)
    store = InstalledBaseStore(ib_db)
    start = time.perf_counter()
    stats = populate_from_path_derived_installed_base(meta_db, store)
    stats["elapsed_sec"] = round(time.perf_counter() - start, 2)
    stats["coverage"] = store.coverage_summary()
    store.close()
    return stats


def run_xlsx_pass(
    lance_db_path: str | Path,
    *,
    output_db: str | Path | None = None,
    limit: int | None = None,
) -> dict:
    meta_db = resolve_retrieval_metadata_db_path(lance_db_path)
    if not meta_db.exists():
        raise FileNotFoundError(f"retrieval_metadata.sqlite3 not found at {meta_db}")
    ib_db = _resolve_output_db(lance_db_path, output_db)
    logger.info("XLSX source:        %s", meta_db)
    logger.info("XLSX destination:   %s", ib_db)
    store = InstalledBaseStore(ib_db)
    start = time.perf_counter()
    attempted = 0
    inserted = 0
    batch: list = []
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
    }
    store.close()
    return stats


def run_pass2(
    lance_db_path: str | Path,
    *,
    output_db: str | Path | None = None,
    limit: int | None = None,
) -> dict:
    from src.store.lance_store import LanceStore

    lance = LanceStore(str(lance_db_path))
    ib_db = _resolve_output_db(lance_db_path, output_db)
    store = InstalledBaseStore(ib_db)
    logger.info("Pass 2 lance_db:    %s", lance_db_path)
    logger.info("Pass 2 destination: %s", ib_db)

    def _iter_candidate_chunks():
        table = getattr(lance, "_table", None)
        if table is None:
            logger.warning("LanceStore._table unavailable — skipping pass 2")
            return
        matched = 0
        try:
            scanner = table.to_lance().scanner(
                columns=["chunk_id", "text", "source_path"],
                batch_size=4096,
            )
            for batch in scanner.to_batches():
                chunk_ids = batch.column("chunk_id").to_pylist()
                texts = batch.column("text").to_pylist()
                source_paths = batch.column("source_path").to_pylist()
                for chunk_id, text, source_path in zip(chunk_ids, texts, source_paths):
                    if not is_installed_base_candidate_path(source_path or ""):
                        continue
                    matched += 1
                    if limit and matched > int(limit):
                        logger.info("Pass 2 limit reached at %d matched", limit)
                        return
                    yield {
                        "chunk_id": chunk_id,
                        "text": text or "",
                        "source_path": source_path or "",
                        "site_token": "",
                        "source_doc_hash": "",
                    }
            return
        except Exception as exc:
            logger.warning("pylance scanner unavailable (%s) — falling back to search API", exc)
        try:
            total = table.count_rows()
            offset = 0
            batch_size = 4096
            while offset < total:
                rows = (
                    table.search()
                    .select(["chunk_id", "text", "source_path"])
                    .limit(batch_size)
                    .offset(offset)
                    .to_list()
                )
                if not rows:
                    break
                for row in rows:
                    if not is_installed_base_candidate_path(row.get("source_path") or ""):
                        continue
                    matched += 1
                    if limit and matched > int(limit):
                        logger.info("Pass 2 limit reached at %d matched", limit)
                        return
                    yield {
                        "chunk_id": row.get("chunk_id", ""),
                        "text": row.get("text") or "",
                        "source_path": row.get("source_path") or "",
                        "site_token": "",
                        "source_doc_hash": "",
                    }
                offset += batch_size
        except Exception as exc:
            logger.warning("Pass 2 search API failed: %s — skipping pass 2", exc)

    attempted = 0
    inserted = 0
    batch: list = []
    for row in extract_chunk_installed_base_from_iter(_iter_candidate_chunks()):
        attempted += 1
        batch.append(row)
        if len(batch) >= 2000:
            inserted += store.insert_many(batch)
            batch = []
    if batch:
        inserted += store.insert_many(batch)
    stats = {
        "pass2_rows_attempted": attempted,
        "pass2_rows_inserted": inserted,
        "coverage": store.coverage_summary(),
    }
    store.close()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate installed_base.db")
    parser.add_argument("--lance-db", default="data/index/lancedb")
    parser.add_argument("--output-db", default=None,
                        help="Optional explicit SQLite destination for isolated A/B runs")
    parser.add_argument("--no-xlsx", action="store_true",
                        help="Skip the direct xlsx parser pass")
    parser.add_argument("--xlsx-limit", type=int, default=None,
                        help="Cap candidate xlsx workbooks parsed")
    parser.add_argument("--pass2", action="store_true",
                        help="Run chunk-derived pass after path-derived pass")
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap matched chunks scanned in pass 2")
    args = parser.parse_args()

    logger.info("Running pass 1 (path-derived installed-base candidates)...")
    stats1 = run_pass1(args.lance_db, output_db=args.output_db)
    logger.info("Pass 1 result: %s", stats1)

    stats_xlsx = None
    if not args.no_xlsx:
        logger.info("Running xlsx pass (direct workbook rows)...")
        stats_xlsx = run_xlsx_pass(
            args.lance_db,
            output_db=args.output_db,
            limit=args.xlsx_limit,
        )
        logger.info("XLSX pass result: %s", stats_xlsx)

    stats2 = None
    if args.pass2:
        logger.info("Running pass 2 (chunk-derived installed-base rows)...")
        stats2 = run_pass2(args.lance_db, output_db=args.output_db, limit=args.limit)
        logger.info("Pass 2 result: %s", stats2)

    print("PASS 1:", stats1)
    if stats_xlsx:
        print("XLSX PASS:", stats_xlsx)
    if stats2:
        print("PASS 2:", stats2)


if __name__ == "__main__":
    main()
