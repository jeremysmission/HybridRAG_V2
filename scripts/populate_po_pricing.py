"""
Populate ``po_pricing.sqlite3`` from the local Lane-2 corpus stores.

The pricing pass stays deterministic and bounded:
  1. path-derived rows from retrieval_metadata source paths with explicit PO+price signals
  2. chunk-derived rows from PO / procurement / purchase-order documents in LanceDB
  3. optional lead-time backfill from the existing ``po_lifecycle`` substrate
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

from src.extraction.po_event_extractor import (
    POEventExtractor,
    is_po_candidate_source_path,
    populate_from_path_derived,
)
from src.store.lance_store import LanceStore
from src.store.po_lifecycle_store import resolve_po_lifecycle_db_path
from src.store.po_pricing_store import POPricingStore, resolve_po_pricing_db_path
from src.store.retrieval_metadata_store import derive_source_metadata, resolve_retrieval_metadata_db_path

logger = logging.getLogger("populate_po_pricing")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

PO_WHERE_SQL = (
    "po_number != '' "
    "OR lower(source_path) LIKE '%purchase order%' "
    "OR lower(source_path) LIKE '%purchase_order%' "
    "OR lower(source_path) LIKE '%\\\\purchases\\\\%' "
    "OR lower(source_path) LIKE '%\\\\procurement\\\\%' "
    "OR lower(source_path) LIKE '%\\\\shipments\\\\%' "
    "OR lower(source_path) LIKE '%\\\\contract%' "
    "OR lower(source_path) LIKE '%pr & po%' "
    "OR lower(source_path) LIKE '%pr&po%' "
    "OR lower(source_path) LIKE '%space report%' "
    "OR lower(source_path) LIKE '%dd250%' "
    "OR lower(source_path) LIKE '%dd 250%' "
    "OR lower(source_path) LIKE '%rcvd%' "
    "OR source_path LIKE '%PO %' "
    "OR source_path LIKE '%PO-%' "
    "OR source_path LIKE '%PO#%' "
    "OR source_path LIKE '%(PO %'"
)

LANCE_WHERE_SQL = (
    "lower(source_path) LIKE '%purchase order%' "
    "OR lower(source_path) LIKE '%purchase_order%' "
    "OR lower(source_path) LIKE '%\\\\purchases\\\\%' "
    "OR lower(source_path) LIKE '%\\\\procurement\\\\%' "
    "OR lower(source_path) LIKE '%\\\\shipments\\\\%' "
    "OR lower(source_path) LIKE '%\\\\contract%' "
    "OR lower(source_path) LIKE '%pr & po%' "
    "OR lower(source_path) LIKE '%pr&po%' "
    "OR lower(source_path) LIKE '%space report%' "
    "OR lower(source_path) LIKE '%dd250%' "
    "OR lower(source_path) LIKE '%dd 250%' "
    "OR lower(source_path) LIKE '%rcvd%' "
    "OR source_path LIKE '%PO %' "
    "OR source_path LIKE '%PO-%' "
    "OR source_path LIKE '%PO#%' "
    "OR source_path LIKE '%(PO %'"
)


def load_candidate_metadata(meta_db: str | Path) -> dict[str, object]:
    conn = sqlite3.connect(str(meta_db))
    conn.row_factory = sqlite3.Row
    metadata_by_path: dict[str, object] = {}
    try:
        cursor = conn.execute(
            f"""
            SELECT
                source_path,
                source_ext,
                cdrl_code,
                incident_id,
                po_number,
                contract_number,
                site_token,
                site_full_name,
                is_reference_did,
                is_filed_deliverable,
                shipment_mode,
                contract_period,
                program_name,
                document_type,
                document_category,
                source_doc_hash
            FROM source_metadata
            WHERE {PO_WHERE_SQL}
            """
        )
        for row in cursor.fetchall():
            row_map = dict(row)
            source_path = str(row_map.get("source_path") or "")
            metadata_by_path[source_path] = derive_source_metadata(source_path, row_map)
    finally:
        conn.close()
    return metadata_by_path


def iter_candidate_chunks(
    lance_db_path: str | Path,
    *,
    batch_size: int = 2048,
    limit: int | None = None,
):
    store = LanceStore(str(lance_db_path))
    tbl = store._table
    if tbl is None:
        return
    matched = 0
    try:
        search = (
            tbl.search()
            .where(LANCE_WHERE_SQL)
            .select(["chunk_id", "text", "source_path"])
            .limit(store.count())
            .to_batches(max(64, int(batch_size)))
        )
    except Exception:
        search = (
            tbl.search()
            .select(["chunk_id", "text", "source_path"])
            .limit(store.count())
            .to_batches(max(64, int(batch_size)))
        )
    for arrow_batch in search:
        if arrow_batch.num_rows == 0:
            continue
        chunk_ids = arrow_batch.column("chunk_id")
        texts = arrow_batch.column("text")
        paths = arrow_batch.column("source_path")
        for idx in range(arrow_batch.num_rows):
            source_path = str(paths[idx] or "")
            if not is_po_candidate_source_path(source_path):
                continue
            matched += 1
            if limit is not None and matched > int(limit):
                return
            yield {
                "chunk_id": str(chunk_ids[idx]),
                "text": str(texts[idx] or ""),
                "source_path": source_path,
            }


def sample_top_cost_rows(store: POPricingStore, *, limit: int = 5) -> list[dict]:
    return store.top_n_parts_by_cost(limit=limit)


def sample_longest_lead_rows(store: POPricingStore, *, limit: int = 5) -> list[dict]:
    return store.longest_lead_time_parts(limit=limit)


def remove_existing_store(db_path: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        target = Path(str(db_path) + suffix)
        if target.exists():
            target.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate po_pricing.sqlite3")
    parser.add_argument(
        "--lance-db",
        default="data/index/lancedb",
        help="LanceDB path (default: data/index/lancedb)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on candidate chunks to scan",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2048,
        help="Batch size for LanceDB streaming (default: 2048)",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete the existing po_pricing store before repopulating it",
    )
    args = parser.parse_args()

    meta_db = resolve_retrieval_metadata_db_path(args.lance_db)
    if not meta_db.exists():
        raise FileNotFoundError(f"retrieval_metadata.sqlite3 not found at {meta_db}")
    pricing_db = resolve_po_pricing_db_path(Path(args.lance_db).parent)
    lifecycle_db = resolve_po_lifecycle_db_path(Path(args.lance_db).parent)

    logger.info("Metadata source:     %s", meta_db)
    logger.info("Chunk source:        %s", args.lance_db)
    logger.info("Destination store:   %s", pricing_db)
    if args.rebuild:
        logger.info("Rebuild requested: removing existing store at %s", pricing_db)
        remove_existing_store(pricing_db)

    store = POPricingStore(pricing_db)
    extractor = POEventExtractor()
    metadata_by_path = load_candidate_metadata(meta_db)

    start = time.perf_counter()
    path_stats = populate_from_path_derived(meta_db, store)
    logger.info("Path-derived pass: %s", path_stats)

    scanned_chunks = 0
    matched_docs = 0
    emitted_rows = 0
    inserted_rows = 0
    docs_by_path: dict[str, dict[str, object]] = {}

    for chunk in iter_candidate_chunks(
        args.lance_db,
        batch_size=max(64, int(args.batch_size)),
        limit=args.limit,
    ):
        scanned_chunks += 1
        source_path = chunk["source_path"]
        doc_state = docs_by_path.setdefault(
            source_path,
            {"text_parts": [], "first_chunk_id": chunk["chunk_id"]},
        )
        doc_state["text_parts"].append(chunk["text"])
        if scanned_chunks % 5000 == 0:
            logger.info("Chunk aggregation progress: scanned=%d docs=%d", scanned_chunks, len(docs_by_path))

    batch = []
    for idx, (source_path, doc_state) in enumerate(docs_by_path.items(), start=1):
        metadata = metadata_by_path.get(source_path)
        source_doc_hash = getattr(metadata, "source_doc_hash", "") if metadata else ""
        combined_text = "\n".join(str(item) for item in doc_state["text_parts"])
        events = extractor.extract_from_chunk(
            text=combined_text,
            chunk_id=str(doc_state["first_chunk_id"]),
            source_path=source_path,
            source_doc_hash=source_doc_hash,
            metadata=metadata,
        )
        if not events:
            continue
        matched_docs += 1
        emitted_rows += len(events)
        batch.extend(events)
        if len(batch) >= 1000:
            inserted_rows += store.insert_many(batch)
            batch = []
        if idx % 500 == 0:
            logger.info(
                "Document extraction progress: docs=%d matched=%d emitted=%d",
                idx,
                matched_docs,
                emitted_rows,
            )
    if batch:
        inserted_rows += store.insert_many(batch)

    po_date_updates = store.backfill_po_dates_from_lifecycle(lifecycle_db)
    lead_time_updates = store.backfill_lead_time_days_from_lifecycle(lifecycle_db)
    coverage = store.coverage_summary()
    elapsed_sec = round(time.perf_counter() - start, 2)

    result = {
        "path_pass": path_stats,
        "chunk_pass": {
            "scanned_chunks": scanned_chunks,
            "candidate_docs": len(docs_by_path),
            "matched_docs": matched_docs,
            "emitted_rows": emitted_rows,
            "inserted_rows": inserted_rows,
        },
        "po_date_updates": po_date_updates,
        "lead_time_updates": lead_time_updates,
        "coverage": coverage,
        "top_cost_parts": sample_top_cost_rows(store),
        "longest_lead_parts": sample_longest_lead_rows(store),
        "elapsed_sec": elapsed_sec,
    }
    logger.info("Populate result: %s", result)
    print("PO_PRICING:", result)
    store.close()


if __name__ == "__main__":
    main()
