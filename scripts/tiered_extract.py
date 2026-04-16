"""
Tiered entity extraction — regex (fast) + GLiNER (GPU) + LLM (expensive).

Tier 1 (regex): Parts, POs, dates, emails, serials — runs on every chunk instantly.
Tier 2 (GLiNER): Persons, orgs, sites, failure modes — on filtered subset, GPU.
Tier 3 (LLM): Complex relationships — reserved for flagged items.

Usage:
    .venv\\Scripts\\python.exe scripts/tiered_extract.py --tier 1              # regex only
    .venv\\Scripts\\python.exe scripts/tiered_extract.py --tier 2              # regex + GLiNER
    .venv\\Scripts\\python.exe scripts/tiered_extract.py --tier 1 --limit 1000 # first 1000 chunks
    .venv\\Scripts\\python.exe scripts/tiered_extract.py --tier 2 --benchmark  # CPU vs GPU on 1000

Time estimates (primary workstation, 49K chunks):
    Tier 1 only:   ~2 seconds
    Tier 1 + 2:    ~5 minutes (GLiNER on GPU, filtered subset)
    Tier 1 + 2 + 3: hours (LLM on flagged items only)

Memory strategy
---------------
Both Tier 1 and Tier 2 stream the corpus with ``iter_chunk_batches`` — the
store is scanned twice (once per tier) instead of holding every chunk in
RAM between passes.

An earlier version accumulated every chunk into an
``all_chunks_for_tier2`` list during Tier 1 so Tier 2 could filter and
process them later. On the 10.4M-chunk corpus that drove peak RAM past
57 GB on a 64 GB host and made Tier 2 impossible on any laptop or work
workstation.

Streaming twice costs us a second scan over LanceDB (seconds on primary workstation)
and gives us a hard memory ceiling that scales with ``batch_size`` and
the GLiNER model footprint, not with corpus size. Tier 1 entities are
persisted before Tier 2 begins, and Tier 2 flushes bounded batches to
SQLite while it streams, so entity retention no longer scales with the
full corpus.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.config.schema import load_config
from src.store.lance_store import LanceStore
from src.store.entity_store import EntityStore, Entity
from src.extraction.entity_extractor import (
    RegexPreExtractor,
    EventBlockParser,
    RegexRelationshipExtractor,
)
from src.extraction.tabular_substrate import (
    DeterministicTableExtractor,
    detect_logistics_table_families,
    pick_primary_logistics_family,
)
from src.store.relationship_store import (
    RelationshipStore,
    Relationship,
    resolve_relationship_db_path,
)

DIVIDER = "=" * 60
TIER1_ENTITY_FLUSH_SIZE = 1000
TIER1_REL_FLUSH_SIZE = 1000
TABLE_ROW_FLUSH_SIZE = 500
TIER2_PROMOTION_TYPES = {"PERSON", "ORG", "SITE"}
LOGISTICS_TABLE_SOURCE_PATTERNS = (
    "Packing List",
    "BOM",
    "PR & PO",
    "Space Report",
    "DD250",
    "Calibration",
    "Spares",
    "Received",
)


def _assert_streaming_api_available() -> None:
    """Fail fast if the lancedb streaming API needed for bounded-memory
    chunk iteration is missing from the installed package.

    The Tier 2 memory fix depends on ``lancedb.SearchBuilder.to_batches``,
    which has been part of ``lancedb`` itself since v0.21 — no optional
    ``pylance`` / ``lance`` dependency. This check is here so a future
    version bump or a broken install surfaces the problem with a clear
    message instead of silently degrading into a corpus-scale
    materialization via the opt-in fallback path.

    Raises
    ------
    RuntimeError
        If ``lancedb`` is not importable or its query builder does not
        expose ``to_batches``.
    """
    try:
        import lancedb  # noqa: F401
        from lancedb.query import LanceQueryBuilder
    except ImportError as e:
        raise RuntimeError(
            "lancedb is required for streaming chunk iteration. "
            "Install with: pip install 'lancedb>=0.30'"
        ) from e
    if not hasattr(LanceQueryBuilder, "to_batches"):
        raise RuntimeError(
            "The installed lancedb lacks LanceQueryBuilder.to_batches, "
            "which is required for bounded-memory streaming. "
            "Upgrade with: pip install --upgrade 'lancedb>=0.30'"
        )


# Validate at import time so any environment regression trips immediately
# instead of waiting for the first streaming call.
_assert_streaming_api_available()


def load_chunks(
    store: LanceStore,
    limit: int = 0,
    where_sql: str | None = None,
) -> list[dict]:
    """Load chunks from LanceDB for extraction.

    WARNING: This loads ALL chunks into memory. For 10M+ corpora, use
    iter_chunk_batches() instead to stream in batches.
    """
    tbl = store._table
    if tbl is None:
        return []
    columns = ["chunk_id", "text", "source_path"]
    search = tbl.search()
    if where_sql:
        search = search.where(where_sql)
    if limit > 0:
        result = search.select(columns).limit(limit).to_arrow()
    else:
        result = search.select(columns).limit(store.count()).to_arrow()
    chunks = []
    for i in range(result.num_rows):
        chunks.append({
            "chunk_id": str(result.column("chunk_id")[i]),
            "text": str(result.column("text")[i]),
            "source_path": str(result.column("source_path")[i]),
        })
    return chunks


def iter_chunk_batches(
    store: LanceStore,
    batch_size: int = 10000,
    limit: int = 0,
    allow_load_fallback: bool = False,
    where_sql: str | None = None,
):
    """Stream chunks from LanceDB in batches without loading all into memory.

    Yields lists of chunk dicts, each up to ``batch_size``. Peak memory is
    roughly ``batch_size * avg_chunk_size`` plus a single Arrow record batch,
    regardless of corpus size.

    Streaming path
    --------------
    Uses the lancedb ``SearchBuilder.to_batches(batch_size)`` API, which
    returns a ``pyarrow.RecordBatchReader`` — a true streaming iterator
    that pulls one Arrow record batch at a time from disk. This API is
    part of ``lancedb`` itself and does NOT require the optional
    ``pylance`` package.

    Raises
    ------
    RuntimeError
        If the lancedb streaming API is unavailable on this store (e.g.
        an older lancedb version without ``to_batches``). Callers who
        know their data is small and can tolerate loading everything into
        memory must opt in explicitly via ``allow_load_fallback=True``.

    Notes
    -----
    This function intentionally does NOT silently fall back to
    ``load_chunks`` on failure. On the 10.4M chunk production corpus, a
    silent fallback reintroduces the 57 GB RAM regression the Tier 2
    streaming rewrite exists to prevent. Fail loud, fix the environment,
    or opt in with eyes open.

    Round 2 (commit 4e22347) used ``tbl.to_lance().scanner(...)`` which
    requires the optional ``pylance`` package. On hosts without pylance
    the call raised and an old silent ``except Exception`` fell through
    to ``load_chunks`` — producing a "passing" 100K memory test that was
    actually running the full-load path. QA caught it; this revision
    removes the silent fallback and switches to the dependency-free
    ``SearchBuilder.to_batches`` API.

    Parameters
    ----------
    store:
        Open LanceStore to stream from.
    batch_size:
        Rows per Arrow record batch yielded.
    limit:
        Max chunks to yield total (0 = unlimited). Matches the CLI
        ``--limit`` flag end-to-end.
    allow_load_fallback:
        If True and the streaming API raises, fall back to ``load_chunks``
        (which materializes the entire result set). Default: False.
        Only set this to True for small stores (< 100K chunks) where the
        memory cost is acceptable, e.g. short-lived unit tests.
    where_sql:
        Optional SQL-like filter passed to LanceDB ``where(...)`` before
        batching. Used by the logistics-first table pilot so it scans only
        known table-heavy source families instead of the whole corpus.
    """
    tbl = store._table
    if tbl is None:
        return
    columns = ["chunk_id", "text", "source_path"]

    # Decide how many rows the SearchBuilder should surface. LanceDB's
    # search() always applies a limit; passing store.count() (or --limit)
    # as the cap is fine because to_batches still streams in batch_size
    # chunks and never materializes the whole set at once.
    total_rows = store.count()
    if limit > 0:
        total_rows = min(total_rows, limit)
    if total_rows <= 0:
        return

    try:
        search = tbl.search()
        if where_sql:
            search = search.where(where_sql)
        reader = (
            search
            .select(columns)
            .limit(total_rows)
            .to_batches(batch_size)
        )
    except Exception as e:
        if not allow_load_fallback:
            raise RuntimeError(
                "LanceDB streaming API unavailable and "
                "allow_load_fallback=False. Refusing to silently load the "
                "full store into memory (Round-3 Tier 2 memory fix — see "
                f"module docstring). Original error: {e!r}"
            ) from e
        # Explicit opt-in path for callers who know their data is small.
        all_chunks = load_chunks(store, limit=limit, where_sql=where_sql)
        for i in range(0, len(all_chunks), batch_size):
            yield all_chunks[i:i + batch_size]
        return

    yielded = 0
    for arrow_batch in reader:
        n = arrow_batch.num_rows
        if n == 0:
            continue
        cid_col = arrow_batch.column("chunk_id")
        text_col = arrow_batch.column("text")
        src_col = arrow_batch.column("source_path")
        chunks = [
            {
                "chunk_id": str(cid_col[i]),
                "text": str(text_col[i]),
                "source_path": str(src_col[i]),
            }
            for i in range(n)
        ]
        if limit > 0 and yielded + len(chunks) > limit:
            chunks = chunks[: limit - yielded]
        if chunks:
            yield chunks
            yielded += len(chunks)
        if limit > 0 and yielded >= limit:
            return


def run_tier1(
    chunks: list[dict],
    part_patterns: list[str],
    max_concurrent: int,
) -> tuple[list[Entity], list[Relationship]]:
    """Tier 1: Regex + event block + relationship extraction. Threaded."""
    extractor = RegexPreExtractor(
        part_patterns=part_patterns,
        security_standard_exclude_patterns=config.extraction.security_standard_exclude_patterns,
    )
    event_parser = EventBlockParser(
        part_patterns=part_patterns,
        security_standard_exclude_patterns=config.extraction.security_standard_exclude_patterns,
    )
    rel_extractor = RegexRelationshipExtractor()
    all_entities: list[Entity] = []
    all_rels: list[Relationship] = []

    def extract_one(chunk: dict) -> tuple[list[Entity], list[Relationship]]:
        text = chunk["text"]
        cid = chunk["chunk_id"]
        src = chunk["source_path"]

        entities = extractor.extract(text=text, chunk_id=cid, source_path=src)
        block_entities, block_rels = event_parser.parse(text=text, chunk_id=cid, source_path=src)
        co_rels = rel_extractor.extract(text=text, chunk_id=cid, source_path=src)

        entities.extend(block_entities)
        block_rels.extend(co_rels)
        return entities, block_rels

    with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
        futures = {pool.submit(extract_one, c): c for c in chunks}
        for future in as_completed(futures):
            try:
                ents, rels = future.result()
                all_entities.extend(ents)
                all_rels.extend(rels)
            except Exception:
                pass  # skip errors silently for regex

    return all_entities, all_rels


def _stream_tier1(
    store: LanceStore,
    entity_store: EntityStore,
    rel_store: RelationshipStore,
    extractor: RegexPreExtractor,
    event_parser: EventBlockParser,
    rel_extractor: RegexRelationshipExtractor,
    *,
    limit: int = 0,
    batch_size: int = 10000,
    dry_run: bool = False,
    entity_flush_size: int = TIER1_ENTITY_FLUSH_SIZE,
    rel_flush_size: int = TIER1_REL_FLUSH_SIZE,
    on_progress=None,
) -> dict[str, object]:
    """Stream Tier 1 with bounded flush buffers.

    The extractor paths still dedup in-memory by candidate key so the
    per-run semantics match the old full-corpus accumulator, but entity
    and relationship objects are flushed incrementally instead of being
    retained until the end of the scan.
    """

    seen_entities: set[tuple[str, str, str]] = set()
    seen_rels: set[tuple[str, str, str, str]] = set()
    entity_buffer: list[Entity] = []
    rel_buffer: list[Relationship] = []
    raw_entity_count = 0
    raw_rel_count = 0
    inserted_entity_count = 0
    inserted_rel_count = 0
    inserted_entity_types: Counter[str] = Counter()
    inserted_rel_preds: Counter[str] = Counter()
    t1_types: Counter[str] = Counter()
    t1_preds: Counter[str] = Counter()
    chunks_processed = 0

    def flush_entities(force: bool = False) -> None:
        nonlocal inserted_entity_count
        if not entity_buffer:
            return
        if dry_run:
            entity_buffer.clear()
            return
        if not force and len(entity_buffer) < entity_flush_size:
            return
        before_count, before_types = _entity_store_counts(entity_store)
        entity_store.insert_entities(entity_buffer)
        after_count, after_types = _entity_store_counts(entity_store)
        inserted_entity_count += after_count - before_count
        inserted_entity_types.update(_counter_delta(after_types, before_types))
        entity_buffer.clear()

    def flush_relationships(force: bool = False) -> None:
        nonlocal inserted_rel_count
        if not rel_buffer:
            return
        if dry_run:
            rel_buffer.clear()
            return
        if not force and len(rel_buffer) < rel_flush_size:
            return
        before_count = rel_store.count()
        before_preds = rel_store.predicate_summary()
        rel_store.insert_relationships(rel_buffer)
        after_count = rel_store.count()
        after_preds = rel_store.predicate_summary()
        inserted_rel_count += after_count - before_count
        inserted_rel_preds.update(_counter_delta(Counter(after_preds), Counter(before_preds)))
        rel_buffer.clear()

    for batch in iter_chunk_batches(store, batch_size=batch_size, limit=limit):
        for chunk in batch:
            text = chunk["text"]
            cid = chunk["chunk_id"]
            src = chunk["source_path"]

            entities = extractor.extract(text=text, chunk_id=cid, source_path=src)
            block_entities, block_rels = event_parser.parse(text=text, chunk_id=cid, source_path=src)
            co_rels = rel_extractor.extract(text=text, chunk_id=cid, source_path=src)

            for e in entities + block_entities:
                key = (e.chunk_id, e.entity_type, e.text)
                if key in seen_entities:
                    continue
                seen_entities.add(key)
                entity_buffer.append(e)
                raw_entity_count += 1
                t1_types[e.entity_type] += 1
                if len(entity_buffer) >= entity_flush_size:
                    flush_entities(force=True)

            for r in block_rels + co_rels:
                key = (r.subject_text, r.predicate, r.object_text, r.chunk_id)
                if key in seen_rels:
                    continue
                seen_rels.add(key)
                rel_buffer.append(r)
                raw_rel_count += 1
                t1_preds[r.predicate] += 1
                if len(rel_buffer) >= rel_flush_size:
                    flush_relationships(force=True)

        chunks_processed += len(batch)
        if on_progress is not None:
            on_progress(
                chunks_processed,
                raw_entity_count,
                raw_rel_count,
                len(entity_buffer),
                len(rel_buffer),
            )

    flush_entities(force=True)
    flush_relationships(force=True)

    return {
        "chunks_processed": chunks_processed,
        "raw_entity_count": raw_entity_count,
        "raw_relationship_count": raw_rel_count,
        "entity_types": t1_types,
        "relationship_preds": t1_preds,
        "inserted_entity_count": inserted_entity_count,
        "inserted_relationship_count": inserted_rel_count,
        "inserted_entity_types": inserted_entity_types,
        "inserted_relationship_preds": inserted_rel_preds,
        "entity_buffer_size": len(entity_buffer),
        "relationship_buffer_size": len(rel_buffer),
    }


def _is_tier2_candidate(chunk: dict, min_chunk_len: int) -> bool:
    """Return True if a chunk is worth sending to GLiNER.

    Filter criteria (cheap, applied during streaming):
      - Stripped length >= min_chunk_len
      - Alphabetic-character ratio >= 0.3 (rejects pure numeric / whitespace
        / symbolic chunks like spreadsheet cell dumps where GLiNER finds
        nothing useful)

    The "already well-covered by Tier 1" concept exists in the task doc
    but is intentionally not applied here: Tier 1 (PART / PO / DATE /
    CONTACT) and Tier 2 (PERSON / ORG / SITE / FAILURE_MODE) target
    disjoint entity types, so a Tier 1 hit is not evidence that Tier 2
    would be redundant on the same chunk. ``tier1_hit_chunk_ids`` is
    still passed through ``run_tier2_gliner`` for future use (e.g.
    confidence boosting) but does not gate candidate selection today.
    """
    text = chunk["text"].strip()
    if len(text) < min_chunk_len:
        return False
    alpha_ratio = sum(1 for ch in text if ch.isalpha()) / max(len(text), 1)
    return alpha_ratio >= 0.3


from src.util.gpu_resolver import resolve_gliner_device as _resolve_gliner_device  # noqa: E402


def _is_cuda_oom(exc: Exception) -> bool:
    """Return True when an exception is clearly a CUDA OOM condition."""
    message = str(exc).lower()
    return "out of memory" in message and "cuda" in message


def _entity_store_counts(entity_store: EntityStore) -> tuple[int, Counter[str]]:
    """Return total entity rows plus per-type counts from SQLite."""
    rows = entity_store._conn.execute(
        """
        SELECT entity_type, COUNT(*)
        FROM entities
        GROUP BY entity_type
        """
    ).fetchall()
    type_counts = Counter({entity_type: int(count) for entity_type, count in rows})
    return sum(type_counts.values()), type_counts


def _counter_delta(after: Counter[str], before: Counter[str]) -> Counter[str]:
    """Return positive per-key deltas between two counters."""
    return Counter({
        key: count - before.get(key, 0)
        for key, count in after.items()
        if count - before.get(key, 0) > 0
    })


def _table_row_count(entity_store: EntityStore) -> int:
    """Return the current extracted-table row count."""
    return entity_store.count_table_rows()


def _counts_snapshot(entity_store: EntityStore, rel_store: RelationshipStore) -> dict[str, object]:
    """Capture current structured-store counts for audit artifacts."""
    entity_total, entity_types = _entity_store_counts(entity_store)
    return {
        "entity_count": entity_total,
        "entity_types": dict(entity_types),
        "table_row_count": _table_row_count(entity_store),
        "relationship_count": rel_store.count(),
        "predicate_counts": rel_store.predicate_summary(),
    }


def _looks_like_clean_tier1_baseline(entity_db_path: Path) -> bool:
    """Detect the known clean Tier 1 baseline path so we do not mutate it casually."""
    haystack = str(entity_db_path).replace("\\", "/").lower()
    return haystack.endswith("/data/index/clean/tier1_clean_20260413/entities.sqlite3")


def _resolve_runtime_store_paths(
    entity_db_path: str | Path,
    *,
    stage_dir: str | None = None,
    materialize_stage: bool = False,
) -> tuple[Path, Path, str | None]:
    """
    Resolve entity/relationship store paths, optionally staging a writable copy.

    ``stage_dir`` is the audited promotion path: copy the baseline stores to a
    new directory, mutate that stage, then audit before any later promotion.
    """
    entity_path = Path(entity_db_path)
    relationship_path = resolve_relationship_db_path(entity_path)

    if not stage_dir:
        return entity_path, relationship_path, None

    stage_root = Path(stage_dir)
    if not stage_root.is_absolute():
        stage_root = V2_ROOT / stage_root
    stage_entity_path = stage_root / "entities.sqlite3"
    stage_relationship_path = stage_root / "relationships.sqlite3"

    if materialize_stage:
        if stage_entity_path.exists() or stage_relationship_path.exists():
            raise SystemExit(
                f"Refusing to reuse populated stage dir {stage_root}. "
                "Choose a fresh --stage-dir so the audit stays attributable."
            )
        stage_root.mkdir(parents=True, exist_ok=True)
        if entity_path.exists():
            shutil.copy2(entity_path, stage_entity_path)
        if relationship_path.exists():
            shutil.copy2(relationship_path, stage_relationship_path)

    return stage_entity_path, stage_relationship_path, str(stage_root)


def _build_logistics_table_where_sql(source_patterns: list[str]) -> str:
    """Build a LanceDB ``where`` clause for the logistics-first pilot."""
    clauses = []
    for pattern in source_patterns:
        escaped = pattern.replace("'", "''")
        clauses.append(f"source_path LIKE '%{escaped}%'")
    return " OR ".join(clauses)


def _stream_logistics_tables(
    store: LanceStore,
    entity_store: EntityStore,
    *,
    limit: int = 0,
    dry_run: bool = False,
    batch_size: int = 5000,
    row_flush_size: int = TABLE_ROW_FLUSH_SIZE,
    source_patterns: list[str] | None = None,
    on_progress=None,
) -> dict[str, object]:
    """
    Recover deterministic table rows from logistics-heavy source families.

    This keeps table promotion narrow and measurable: spreadsheets, packing
    lists, BOMs, received-PO records, DD250s, calibration logs, and spares
    reports.
    """
    extractor = DeterministicTableExtractor()
    row_buffer = []
    scanned_chunks = 0
    candidate_chunks = 0
    matched_chunks = 0
    raw_row_count = 0
    inserted_row_count = 0
    family_candidate_chunks: Counter[str] = Counter()
    family_row_counts: Counter[str] = Counter()
    family_source_paths: defaultdict[str, set[str]] = defaultdict(set)
    source_patterns = source_patterns or list(LOGISTICS_TABLE_SOURCE_PATTERNS)
    where_sql = _build_logistics_table_where_sql(source_patterns)

    def flush_rows(force: bool = False) -> None:
        nonlocal inserted_row_count
        if not row_buffer:
            return
        if dry_run:
            row_buffer.clear()
            return
        if not force and len(row_buffer) < row_flush_size:
            return
        before = _table_row_count(entity_store)
        entity_store.insert_table_rows(row_buffer)
        after = _table_row_count(entity_store)
        inserted_row_count += after - before
        row_buffer.clear()

    for batch in iter_chunk_batches(
        store,
        batch_size=batch_size,
        limit=limit,
        where_sql=where_sql,
    ):
        for chunk in batch:
            scanned_chunks += 1
            families = detect_logistics_table_families(chunk["source_path"], chunk["text"])
            primary_family = pick_primary_logistics_family(families)
            if primary_family is None:
                continue

            candidate_chunks += 1
            family_candidate_chunks[primary_family] += 1
            rows = extractor.extract(
                text=chunk["text"],
                chunk_id=chunk["chunk_id"],
                source_path=chunk["source_path"],
            )
            if not rows:
                continue

            matched_chunks += 1
            raw_row_count += len(rows)
            family_row_counts[primary_family] += len(rows)
            family_source_paths[primary_family].add(chunk["source_path"])
            row_buffer.extend(rows)
            if len(row_buffer) >= row_flush_size:
                flush_rows(force=True)

        if on_progress is not None:
            on_progress(
                scanned_chunks,
                candidate_chunks,
                raw_row_count,
                len(row_buffer),
            )

    flush_rows(force=True)

    return {
        "scanned_chunks": scanned_chunks,
        "candidate_chunks": candidate_chunks,
        "matched_chunks": matched_chunks,
        "raw_row_count": raw_row_count,
        "inserted_row_count": inserted_row_count,
        "family_candidate_chunks": dict(family_candidate_chunks),
        "family_row_counts": dict(family_row_counts),
        "family_source_counts": {
            family: len(source_paths)
            for family, source_paths in family_source_paths.items()
        },
        "source_patterns": source_patterns,
    }


def _write_audit_json(audit_report: dict[str, object], output_path: str | None) -> str | None:
    """Persist the structured audit artifact when requested."""
    if not output_path:
        return None
    path = Path(output_path)
    if not path.is_absolute():
        path = V2_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit_report, indent=2), encoding="utf-8", newline="\n")
    return str(path)


def _stream_tier2_gliner(
    store: LanceStore,
    device: str,
    model_name: str,
    min_chunk_len: int,
    min_confidence: float,
    allowed_types: set[str] | None = None,
    limit: int = 0,
    stream_batch_size: int = 10000,
    gliner_batch_size: int = 8,
    progress_every: int = 500,
    gliner_model=None,
    on_entity_batch=None,
) -> dict[str, object]:
    """Shared Tier 2 streaming path used by both production and tests."""
    if gliner_model is None:
        try:
            from gliner import GLiNER
        except ImportError:
            print("  GLiNER not installed -- skipping Tier 2")
            return {
                "scanned": 0,
                "candidates": 0,
                "raw_count": 0,
                "type_counts": Counter(),
            }

        resolved_device = _resolve_gliner_device(device)
        if resolved_device is None:
            return {
                "scanned": 0,
                "candidates": 0,
                "raw_count": 0,
                "type_counts": Counter(),
            }

        print(f"  Loading GLiNER model: {model_name} on {resolved_device}")
        model = GLiNER.from_pretrained(model_name)
        if "cuda" in resolved_device:
            import torch
            gpu_idx = int(resolved_device.split(":")[1]) if ":" in resolved_device else 0
            model = model.to(resolved_device)
            print(f"  GLiNER on {resolved_device}: {torch.cuda.get_device_name(gpu_idx)}")
            free, total = torch.cuda.mem_get_info(gpu_idx)
            print(f"  VRAM after model load: {free/1e9:.1f}GB free / {total/1e9:.1f}GB total")
    else:
        model = gliner_model
        resolved_device = device

    labels = ["PERSON", "ORGANIZATION", "SITE", "FAILURE_MODE", "DATE"]
    label_map = {
        "PERSON": "PERSON",
        "ORGANIZATION": "ORG",
        "SITE": "SITE",
        "FAILURE_MODE": "PART",
        "DATE": "DATE",
    }

    pending: list[dict] = []
    scanned = 0
    candidates = 0
    raw_count = 0
    type_counts: Counter[str] = Counter()

    def flush_pending() -> None:
        """Run GLiNER on the pending batch and emit extracted entities."""
        nonlocal raw_count
        if not pending:
            return

        texts = [c["text"][:512] for c in pending]  # GLiNER works best on shorter text
        pending_size = len(pending)
        try:
            batch_results = model.batch_predict_entities(
                texts, labels, threshold=min_confidence, flat_ner=True,
            )
        except Exception as e:
            pending.clear()
            if _is_cuda_oom(e):
                oom_detail = (
                    f"  GLiNER CUDA OOM at scanned={scanned:,}, candidates={candidates:,}, "
                    f"pending_batch={pending_size:,}, device={resolved_device}, model={model_name}"
                )
                if "cuda" in resolved_device:
                    import torch
                    gpu_idx = int(resolved_device.split(":")[1]) if ":" in resolved_device else 0
                    free, total = torch.cuda.mem_get_info(gpu_idx)
                    allocated = torch.cuda.memory_allocated(gpu_idx)
                    reserved = torch.cuda.memory_reserved(gpu_idx)
                    max_allocated = torch.cuda.max_memory_allocated(gpu_idx)
                    max_reserved = torch.cuda.max_memory_reserved(gpu_idx)
                    oom_detail += (
                        f", free={free/1e9:.2f}GB/{total/1e9:.2f}GB"
                        f", allocated={allocated/1e9:.2f}GB"
                        f", reserved={reserved/1e9:.2f}GB"
                        f", max_allocated={max_allocated/1e9:.2f}GB"
                        f", max_reserved={max_reserved/1e9:.2f}GB"
                    )
                    torch.cuda.empty_cache()
                raise RuntimeError(f"{oom_detail}. Aborting Tier 2 instead of retrying a failed batch.") from e

            print(f"  GLiNER batch error at scanned={scanned:,}: {e}")
            return

        entity_batch: list[Entity] = []
        for chunk, entities in zip(pending, batch_results):
            for ent in entities:
                v2_type = label_map.get(ent["label"], ent["label"])
                if allowed_types is not None and v2_type not in allowed_types:
                    continue
                entity_batch.append(Entity(
                    entity_type=v2_type,
                    text=ent["text"].strip(),
                    raw_text=ent["text"],
                    confidence=ent["score"],
                    chunk_id=chunk["chunk_id"],
                    source_path=chunk["source_path"],
                    context="",
                ))
        pending.clear()

        raw_count += len(entity_batch)
        type_counts.update(e.entity_type for e in entity_batch)
        if on_entity_batch is not None:
            on_entity_batch(entity_batch)

    # Second streaming pass — this is the whole point of the redesign.
    # iter_chunk_batches yields one list[dict] at a time; we keep only
    # the current stream batch plus the GLiNER pending batch in memory.
    for batch in iter_chunk_batches(store, batch_size=stream_batch_size, limit=limit):
        for chunk in batch:
            scanned += 1
            if not _is_tier2_candidate(chunk, min_chunk_len):
                continue
            candidates += 1
            pending.append(chunk)
            if len(pending) >= gliner_batch_size:
                flush_pending()
        # Progress log cadence — per-batch, not per-chunk
        if progress_every and scanned % progress_every < stream_batch_size:
            print(
                f"  GLiNER progress: scanned {scanned:,}, "
                f"candidates {candidates:,}, entities {raw_count:,}"
            )

    # Drain any remainder
    flush_pending()

    print(
        f"  Tier 2 filter: {scanned:,} scanned -> {candidates:,} candidates "
        f"({scanned - candidates:,} skipped by filter)"
    )
    return {
        "scanned": scanned,
        "candidates": candidates,
        "raw_count": raw_count,
        "type_counts": type_counts,
    }


def run_tier2_gliner(
    store: LanceStore,
    tier1_hit_chunk_ids: set[str],
    device: str,
    model_name: str,
    min_chunk_len: int,
    min_confidence: float,
    allowed_types: set[str] | None = None,
    limit: int = 0,
    stream_batch_size: int = 10000,
    gliner_batch_size: int = 8,
    progress_every: int = 500,
    gliner_model=None,
) -> list[Entity]:
    """Tier 2: GLiNER over a fresh streaming pass of the store.

    This function does NOT take a list of pre-loaded chunks. It opens a
    second streaming pass over ``store`` (respecting ``limit``) and filters
    candidates inline via ``_is_tier2_candidate``. Only the ``pending``
    GLiNER batch (<= ``gliner_batch_size``) and the accumulated Entity
    list live in memory — corpus-size data never does.

    Parameters
    ----------
    store:
        A LanceStore to stream from. Must already be open.
    tier1_hit_chunk_ids:
        Compatibility-only parameter kept for the test harness and the
        frozen GUI import path. The production Tier 2 path no longer
        carries a corpus-scale Tier 1 hit set across passes.
    device:
        Requested CUDA device (e.g. ``cuda:1``).
    model_name:
        HuggingFace model id for GLiNER.
    min_chunk_len:
        Minimum stripped text length to send to GLiNER.
    min_confidence:
        GLiNER score threshold.
    limit:
        Max chunks to scan (0 = all). Matches the CLI --limit flag.
    stream_batch_size:
        Rows pulled per LanceDB scan batch.
    gliner_batch_size:
        Candidates per GLiNER forward pass.
    progress_every:
        Log cadence in scanned-chunk units.
    gliner_model:
        Optional pre-loaded model. When supplied, the function skips
        the ``GLiNER.from_pretrained(...) / .to(device)`` load path.
        Used by tests to inject a fake model without importing the real
        GLiNER package.

    Returns
    -------
    list[Entity]: compatibility wrapper used by tests. Production code
    uses ``_stream_tier2_gliner`` directly so entities can be flushed in
    bounded SQLite batches instead of being retained for the full corpus.
    """
    all_entities: list[Entity] = []
    def collect_entities(entity_batch: list[Entity]) -> None:
        all_entities.extend(entity_batch)

    _stream_tier2_gliner(
        store=store,
        device=device,
        model_name=model_name,
        min_chunk_len=min_chunk_len,
        min_confidence=min_confidence,
        allowed_types=allowed_types,
        limit=limit,
        stream_batch_size=stream_batch_size,
        gliner_batch_size=gliner_batch_size,
        progress_every=progress_every,
        gliner_model=gliner_model,
        on_entity_batch=collect_entities,
    )

    return all_entities


def main() -> None:
    """Parse command-line inputs and run the main tiered extract workflow."""
    parser = argparse.ArgumentParser(description="Tiered entity extraction.")
    parser.add_argument("--tier", type=int, default=1, choices=[1, 2, 3],
                       help="Max tier to run (1=regex, 2=+GLiNER, 3=+LLM).")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--limit", type=int, default=0, help="Max chunks to process (0=all).")
    parser.add_argument(
        "--table-mode",
        choices=["off", "logistics"],
        default="off",
        help="Optional deterministic table extraction pass.",
    )
    parser.add_argument(
        "--table-limit",
        type=int,
        default=0,
        help="Max table-candidate chunks to process for the table pilot (0=all matching sources).",
    )
    parser.add_argument(
        "--table-source-like",
        action="append",
        default=[],
        help="Additional source_path LIKE fragment for the logistics table pilot. Repeatable.",
    )
    parser.add_argument(
        "--stage-dir",
        default="",
        help="Optional staged entity/relationship store directory for audited Tier 2 or table promotion.",
    )
    parser.add_argument(
        "--allow-baseline-write",
        action="store_true",
        help="Permit Tier 2 or table writes directly into the clean Tier 1 baseline store.",
    )
    parser.add_argument(
        "--audit-json",
        default="",
        help="Optional path for a JSON audit artifact summarizing before/after counts and phase deltas.",
    )
    parser.add_argument("--benchmark", action="store_true",
                       help="Benchmark GLiNER CPU vs GPU on 1000 chunks.")
    parser.add_argument("--dry-run", action="store_true", help="Count only, don't write.")
    args = parser.parse_args()

    t0 = time.perf_counter()

    config = load_config(args.config)
    needs_guard = args.tier >= 2 or args.table_mode != "off"
    baseline_entity_path = Path(config.paths.entity_db)
    stage_dir = args.stage_dir if args.stage_dir and not args.dry_run else None

    if (
        needs_guard
        and not args.dry_run
        and stage_dir is None
        and _looks_like_clean_tier1_baseline(baseline_entity_path)
        and not args.allow_baseline_write
    ):
        raise SystemExit(
            "Refusing to mutate the clean Tier 1 baseline with Tier 2 or table promotion. "
            "Use --dry-run to audit, or --stage-dir to materialize a staged copy, or "
            "--allow-baseline-write if you explicitly intend to overwrite the baseline."
        )

    runtime_entity_path, runtime_relationship_path, materialized_stage_dir = _resolve_runtime_store_paths(
        baseline_entity_path,
        stage_dir=stage_dir,
        materialize_stage=bool(stage_dir),
    )

    store = LanceStore(config.paths.lance_db)
    entity_store = EntityStore(str(runtime_entity_path))
    rel_store = RelationshipStore(runtime_relationship_path)
    before_snapshot = _counts_snapshot(entity_store, rel_store)
    audit_report: dict[str, object] = {
        "config_path": str(Path(args.config).resolve()),
        "tier": args.tier,
        "dry_run": args.dry_run,
        "table_mode": args.table_mode,
        "table_limit": args.table_limit,
        "table_source_like": args.table_source_like,
        "baseline_entity_path": str(baseline_entity_path),
        "baseline_relationship_path": str(resolve_relationship_db_path(baseline_entity_path)),
        "runtime_entity_path": str(runtime_entity_path),
        "runtime_relationship_path": str(runtime_relationship_path),
        "stage_dir": materialized_stage_dir,
        "before": before_snapshot,
    }

    print(DIVIDER)
    print("  HybridRAG V2 -- Tiered Entity Extraction")
    print(DIVIDER)
    print(f"  Store:       {store.count():,} chunks")
    print(f"  Entity DB:   {runtime_entity_path}")
    print(f"  Rel DB:      {runtime_relationship_path}")
    if materialized_stage_dir:
        print(f"  Stage dir:   {materialized_stage_dir}")
    print(f"  Entities:    {before_snapshot['entity_count']:,} existing")
    print(f"  Tables:      {before_snapshot['table_row_count']:,} existing")
    print(f"  Rels:        {before_snapshot['relationship_count']:,} existing")
    print(f"  Max tier:    {args.tier}")
    print(f"  Limit:       {args.limit or 'all'}")
    print(f"  Table mode:  {args.table_mode}")
    print(f"  Threads:     {config.extraction.max_concurrent}")
    print(f"  Dry run:     {args.dry_run}")
    if args.benchmark:
        print("  NOTE: benchmark flag is reserved; the audited extraction path runs normally.")

    # --- Tier 1: Regex + Event Blocks + Relationships (streaming) ---
    total_chunks = store.count()
    if args.limit > 0:
        total_chunks = min(total_chunks, args.limit)
    print(f"  Total:       {total_chunks:,} chunks")
    print()

    print("  [TIER 1] Regex + event block + relationship extraction (streaming)...")
    t1_start = time.perf_counter()

    extractor = RegexPreExtractor(
        part_patterns=config.extraction.part_patterns,
        security_standard_exclude_patterns=config.extraction.security_standard_exclude_patterns,
    )
    event_parser = EventBlockParser(
        part_patterns=config.extraction.part_patterns,
        security_standard_exclude_patterns=config.extraction.security_standard_exclude_patterns,
    )
    rel_extractor = RegexRelationshipExtractor()
    def _tier1_progress(
        chunks_done: int,
        entity_total: int,
        rel_total: int,
        entity_buffer_size: int,
        rel_buffer_size: int,
    ) -> None:
        elapsed = time.perf_counter() - t1_start
        rate = chunks_done / max(elapsed, 0.001)
        print(
            f"  Tier 1: {chunks_done:,} / {total_chunks:,} chunks "
            f"({rate:,.0f} chunks/sec, {entity_total:,} entities, {rel_total:,} rels; "
            f"buffered {entity_buffer_size:,}/{rel_buffer_size:,})"
        )

    t1_result = _stream_tier1(
        store=store,
        entity_store=entity_store,
        rel_store=rel_store,
        extractor=extractor,
        event_parser=event_parser,
        rel_extractor=rel_extractor,
        limit=args.limit,
        batch_size=10000,
        dry_run=args.dry_run,
        on_progress=_tier1_progress,
    )

    t1_elapsed = time.perf_counter() - t1_start
    t1_entity_total = int(t1_result["raw_entity_count"])
    t1_rel_total = int(t1_result["raw_relationship_count"])
    t1_types = Counter(t1_result["entity_types"])
    t1_preds = Counter(t1_result["relationship_preds"])
    t1_inserted_rel_total = int(t1_result["inserted_relationship_count"])
    t1_inserted_entity_total = int(t1_result["inserted_entity_count"])
    audit_report["tier1"] = {
        "chunks_processed": int(t1_result["chunks_processed"]),
        "raw_entity_count": t1_entity_total,
        "raw_relationship_count": t1_rel_total,
        "inserted_entity_count": t1_inserted_entity_total,
        "inserted_relationship_count": t1_inserted_rel_total,
        "entity_types": dict(t1_types),
        "relationship_predicates": dict(t1_preds),
        "inserted_entity_types": dict(Counter(t1_result["inserted_entity_types"])),
        "inserted_relationship_predicates": dict(Counter(t1_result["inserted_relationship_preds"])),
    }
    print(f"  [TIER 1] {t1_entity_total:,} entities ({t1_elapsed:.2f}s)")
    print(f"           Types: {dict(t1_types)}")
    print(f"           Rels:  {t1_rel_total:,} -- {dict(t1_preds)}")
    print(f"           Rate: {int(t1_result['chunks_processed'])/max(t1_elapsed, 0.001):,.0f} chunks/sec")
    print()

    total_entity_count = t1_entity_total if args.dry_run else t1_inserted_entity_total
    total_types = Counter(t1_types) if args.dry_run else Counter(t1_result["inserted_entity_types"])
    if not args.dry_run:
        print(
            f"  [TIER 1] persisted {t1_inserted_entity_total:,} entities "
            f"and {t1_inserted_rel_total:,} relationships"
        )
        print()

    # --- Logistics-first deterministic table pilot ---
    table_raw_count = 0
    table_inserted_count = 0
    if args.table_mode == "logistics":
        table_limit = args.table_limit or 0
        table_source_patterns = list(LOGISTICS_TABLE_SOURCE_PATTERNS)
        if args.table_source_like:
            table_source_patterns.extend(args.table_source_like)

        print("  [TABLES] Logistics-first deterministic table extraction...")
        table_start = time.perf_counter()

        def _table_progress(
            scanned_chunks: int,
            candidate_chunks: int,
            row_total: int,
            buffered_rows: int,
        ) -> None:
            elapsed = time.perf_counter() - table_start
            rate = scanned_chunks / max(elapsed, 0.001)
            print(
                f"  Tables: {scanned_chunks:,} candidate chunks scanned "
                f"({rate:,.0f} chunks/sec, {candidate_chunks:,} family hits, "
                f"{row_total:,} rows; buffered {buffered_rows:,})"
            )

        table_result = _stream_logistics_tables(
            store=store,
            entity_store=entity_store,
            limit=table_limit,
            dry_run=args.dry_run,
            source_patterns=table_source_patterns,
            on_progress=_table_progress,
        )
        table_elapsed = time.perf_counter() - table_start
        table_raw_count = int(table_result["raw_row_count"])
        table_inserted_count = (
            int(table_result["inserted_row_count"]) if not args.dry_run else 0
        )
        audit_report["table_pilot"] = {
            "scanned_chunks": int(table_result["scanned_chunks"]),
            "candidate_chunks": int(table_result["candidate_chunks"]),
            "matched_chunks": int(table_result["matched_chunks"]),
            "raw_row_count": table_raw_count,
            "inserted_row_count": table_inserted_count,
            "family_candidate_chunks": dict(table_result["family_candidate_chunks"]),
            "family_row_counts": dict(table_result["family_row_counts"]),
            "family_source_counts": dict(table_result["family_source_counts"]),
            "source_patterns": list(table_result["source_patterns"]),
            "duration_seconds": round(table_elapsed, 2),
        }
        print(
            f"  [TABLES] {table_raw_count:,} rows raw, {table_inserted_count:,} new after dedup "
            f"({table_elapsed:.1f}s)"
        )
        print(f"           Family rows: {dict(table_result['family_row_counts'])}")
        print()

    # --- Tier 2: GLiNER (second streaming pass over the store) ---
    t2_raw_count = 0
    t2_types: Counter[str] = Counter()
    t2_new_count = 0
    if args.tier >= 2:
        print("  [TIER 2] GLiNER extraction via second streaming pass...")
        print(f"           Promotion types: {sorted(TIER2_PROMOTION_TYPES)}")
        t2_start = time.perf_counter()
        tier2_flush_buffer: list[Entity] = []
        tier2_store_flush_size = 1000

        def handle_tier2_batch(entity_batch: list[Entity]) -> None:
            if args.dry_run:
                return
            tier2_flush_buffer.extend(entity_batch)
            if len(tier2_flush_buffer) >= tier2_store_flush_size:
                entity_store.insert_entities(tier2_flush_buffer)
                tier2_flush_buffer.clear()

        before_t2_e, before_t2_types = _entity_store_counts(entity_store) if not args.dry_run else (0, Counter())
        t2_result = _stream_tier2_gliner(
            store=store,
            device=config.extraction.gliner_device,
            model_name=config.extraction.gliner_model,
            min_chunk_len=config.extraction.gliner_min_chunk_len,
            min_confidence=config.extraction.min_confidence,
            allowed_types=TIER2_PROMOTION_TYPES,
            limit=args.limit,
            on_entity_batch=handle_tier2_batch,
        )
        if not args.dry_run and tier2_flush_buffer:
            entity_store.insert_entities(tier2_flush_buffer)
            tier2_flush_buffer.clear()
        t2_elapsed = time.perf_counter() - t2_start

        t2_raw_count = int(t2_result["raw_count"])
        t2_types = Counter(t2_result["type_counts"])
        if not args.dry_run:
            after_t2_e, after_t2_types = _entity_store_counts(entity_store)
            t2_new_count = after_t2_e - before_t2_e
            t2_new_types = _counter_delta(after_t2_types, before_t2_types)
            total_entity_count += t2_new_count
            total_types.update(t2_new_types)
        else:
            # Dry-run totals report raw pre-dedup counts. Tier 1 is already
            # seeded from t1_entity_total / t1_types (raw regex output) at
            # the `total_entity_count = t1_entity_total if args.dry_run ...`
            # init above, so Tier 2 must also contribute its raw counts or
            # the final DRY RUN summary silently drops everything Tier 2
            # would have emitted. Keeping both tiers on the same "raw"
            # footing makes the DRY RUN totals internally consistent with
            # the "[TIER 2] N entities raw" line printed just below.
            total_entity_count += t2_raw_count
            total_types.update(t2_types)

        audit_report["tier2"] = {
            "allowed_types": sorted(TIER2_PROMOTION_TYPES),
            "scanned_chunks": int(t2_result["scanned"]),
            "candidate_chunks": int(t2_result["candidates"]),
            "raw_entity_count": t2_raw_count,
            "new_entity_count": t2_new_count,
            "type_counts": dict(t2_types),
            "duration_seconds": round(t2_elapsed, 2),
        }
        print(f"  [TIER 2] {t2_raw_count:,} entities raw, {t2_new_count:,} new after dedup ({t2_elapsed:.1f}s)")
        print(f"           Types: {dict(t2_types)}")
        print()

    # --- Tier 3: LLM ---
    if args.tier >= 3:
        print("  [TIER 3] LLM extraction (not yet implemented -- reserved for flagged items)")
        print()

    total_relationship_count = t1_rel_total if args.dry_run else t1_inserted_rel_total
    total_preds = Counter(t1_preds) if args.dry_run else Counter(t1_result["inserted_relationship_preds"])
    final_table_total = table_raw_count if args.dry_run else _table_row_count(entity_store)

    if args.dry_run:
        print(
            f"  DRY RUN:     would extract up to {total_entity_count:,} raw "
            f"entities (pre-dedup; Tier 1 + Tier 2 raw), {t1_rel_total:,} rels, "
            f"{table_raw_count:,} table rows"
        )

    total_label = "Total entities (raw, pre-dedup)" if args.dry_run else "Total entities (inserted)"
    breakdown_label = "Entity breakdown (raw)" if args.dry_run else "Entity breakdown (inserted)"
    after_snapshot = _counts_snapshot(entity_store, rel_store)
    audit_report["after"] = after_snapshot
    audit_report["duration_seconds"] = round(time.perf_counter() - t0, 2)
    print()
    print(DIVIDER)
    print(f"  {total_label}: {total_entity_count:,}")
    print(f"  {breakdown_label}: {dict(total_types)}")
    print(f"  Total table rows:    {final_table_total:,}")
    print(f"  Total relationships: {total_relationship_count:,}")
    print(f"  Rel breakdown:       {dict(total_preds)}")
    print(f"  Total time:          {time.perf_counter()-t0:.1f}s")
    print(DIVIDER)

    audit_json_path = _write_audit_json(audit_report, args.audit_json or None)
    if audit_json_path:
        print(f"  Audit JSON:          {audit_json_path}")

    store.close()
    entity_store.close()
    rel_store.close()


if __name__ == "__main__":
    main()
