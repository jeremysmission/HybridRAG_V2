"""
Populate failure_events.db from existing V2 substrate.

Two-pass strategy:
  PASS 1 (fast) — derive from retrieval_metadata.sqlite3 alone.
    Emits path-derived candidates with system + year + site. No part_number.
  PASS 2 (optional, heavier) — sample chunks from LanceDB that match
    failure-signal keywords, extract part_numbers, insert richer rows.

PASS 1 runs from source_metadata alone (fast, ~seconds).
PASS 2 requires LanceDB and runs for minutes on a GPU.

Usage:
    python scripts/populate_failure_events.py                    # pass 1 only
    python scripts/populate_failure_events.py --pass2            # + chunk pass
    python scripts/populate_failure_events.py --pass2 --limit N  # cap chunk rows
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

from src.store.failure_events_store import FailureEventsStore, resolve_failure_events_db_path
from src.store.retrieval_metadata_store import resolve_retrieval_metadata_db_path
from src.extraction.failure_event_extractor import (
    populate_from_path_derived,
    extract_chunk_events_from_iter,
)

logger = logging.getLogger("populate_failure_events")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def run_pass1(lance_db_path: str | Path) -> dict:
    """Populate failure_events from source_metadata alone (path-derived)."""
    meta_db = resolve_retrieval_metadata_db_path(lance_db_path)
    if not meta_db.exists():
        raise FileNotFoundError(f"retrieval_metadata.sqlite3 not found at {meta_db}")
    fe_db = resolve_failure_events_db_path(Path(lance_db_path).parent)
    logger.info("Pass 1 source:       %s", meta_db)
    logger.info("Pass 1 destination:  %s", fe_db)
    store = FailureEventsStore(fe_db)
    start = time.perf_counter()
    stats = populate_from_path_derived(meta_db, store)
    stats["elapsed_sec"] = round(time.perf_counter() - start, 2)
    stats["coverage"] = store.coverage_summary()
    store.close()
    return stats


def run_pass2(
    lance_db_path: str | Path,
    *,
    limit: int | None = None,
    require_failure_signal: bool = True,
) -> dict:
    """
    Populate failure_events from LanceDB chunk sample.

    Samples chunks whose source_path references monitoring system or legacy monitoring system (the two
    systems in canonical_aliases.yaml) and runs failure-signal + part_number
    regex against chunk text.
    """
    from src.store.lance_store import LanceStore

    lance = LanceStore(str(lance_db_path))
    fe_db = resolve_failure_events_db_path(Path(lance_db_path).parent)
    store = FailureEventsStore(fe_db)
    logger.info("Pass 2 lance_db:     %s", lance_db_path)
    logger.info("Pass 2 destination:  %s", fe_db)

    def _iter_candidate_chunks():
        tbl = getattr(lance, "_table", None)
        if tbl is None:
            logger.warning("LanceStore._table unavailable — skipping pass 2")
            return
        # Strategy 1: pylance scanner (fastest, streaming).
        try:
            scanner = tbl.to_lance().scanner(
                columns=["chunk_id", "text", "source_path"],
                batch_size=4096,
            )
            scanned = 0
            matched = 0
            for batch in scanner.to_batches():
                chunk_ids = batch.column("chunk_id").to_pylist()
                texts = batch.column("text").to_pylist()
                source_paths = batch.column("source_path").to_pylist()
                for cid, txt, sp in zip(chunk_ids, texts, source_paths):
                    scanned += 1
                    sp_lower = (sp or "").lower()
                    if "monitoring system" not in sp_lower and "legacy monitoring system" not in sp_lower:
                        continue
                    matched += 1
                    if limit and matched > int(limit):
                        logger.info("Pass 2 limit reached at %d matched", limit)
                        return
                    yield {
                        "source_path": sp, "chunk_id": cid, "text": txt or "",
                        "site_token": "", "incident_id": "", "source_doc_hash": "",
                    }
                    if matched % 5000 == 0:
                        logger.info("Pass 2 (scanner): scanned=%d matched=%d", scanned, matched)
            logger.info("Pass 2 (scanner) complete: scanned=%d matched=%d", scanned, matched)
            return
        except Exception as e:
            logger.warning("pylance scanner unavailable (%s) — falling back to LanceDB search API", e)
        # Strategy 2: LanceDB search().where().limit() (no pylance dep).
        try:
            total = tbl.count_rows()
            logger.info("Pass 2 (search API): total chunks=%d", total)
            # Use where() to filter server-side; fall back to full scan if where fails.
            batch_size = 8192
            matched = 0
            offset = 0
            while offset < total:
                end = min(offset + batch_size, total)
                try:
                    rows = (
                        tbl.search()
                        .where(
                            "lower(source_path) LIKE '%monitoring system%' "
                            "OR lower(source_path) LIKE '%legacy monitoring system%'"
                        )
                        .select(["chunk_id", "text", "source_path"])
                        .limit(batch_size)
                        .offset(offset)
                        .to_list()
                    )
                except Exception:
                    # Fallback: no server-side filter — filter in Python.
                    rows = (
                        tbl.search()
                        .select(["chunk_id", "text", "source_path"])
                        .limit(batch_size)
                        .offset(offset)
                        .to_list()
                    )
                if not rows:
                    break
                for row in rows:
                    sp = row.get("source_path") or ""
                    sp_lower = sp.lower()
                    if "monitoring system" not in sp_lower and "legacy monitoring system" not in sp_lower:
                        continue
                    matched += 1
                    if limit and matched > int(limit):
                        logger.info("Pass 2 (search) limit reached at %d matched", limit)
                        return
                    yield {
                        "source_path": sp,
                        "chunk_id": row.get("chunk_id", ""),
                        "text": row.get("text") or "",
                        "site_token": "",
                        "incident_id": "",
                        "source_doc_hash": "",
                    }
                    if matched % 2500 == 0:
                        logger.info("Pass 2 (search): offset=%d matched=%d", offset, matched)
                offset += batch_size
            logger.info("Pass 2 (search) complete: matched=%d", matched)
        except Exception as e2:
            logger.warning("Pass 2 (search API) also failed: %s — skipping pass 2", e2)

    events = []
    inserted_total = 0
    for event in extract_chunk_events_from_iter(
        _iter_candidate_chunks(),
        require_failure_signal=require_failure_signal,
    ):
        events.append(event)
        if len(events) >= 2000:
            store.insert_many(events)
            inserted_total += len(events)
            events = []
    if events:
        store.insert_many(events)
        inserted_total += len(events)
    stats = {
        "pass2_inserted_attempted": inserted_total,
        "coverage": store.coverage_summary(),
    }
    store.close()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate failure_events.db")
    parser.add_argument("--lance-db", default="data/index/lancedb",
                        help="LanceDB path (default: data/index/lancedb)")
    parser.add_argument("--pass2", action="store_true",
                        help="Run chunk-derived pass in addition to path-derived pass 1")
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap number of chunks scanned in pass 2")
    parser.add_argument("--no-failure-signal-filter", action="store_true",
                        help="Accept all chunks in pass 2 (not just those with failure verbs)")
    args = parser.parse_args()

    logger.info("Running pass 1 (path-derived)...")
    stats1 = run_pass1(args.lance_db)
    logger.info("Pass 1 result: %s", stats1)

    stats2 = None
    if args.pass2:
        logger.info("Running pass 2 (chunk-derived)...")
        stats2 = run_pass2(
            args.lance_db,
            limit=args.limit,
            require_failure_signal=not args.no_failure_signal_filter,
        )
        logger.info("Pass 2 result: %s", stats2)

    print("PASS 1:", stats1)
    if stats2:
        print("PASS 2:", stats2)


if __name__ == "__main__":
    main()
