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
the GLiNER model footprint, not with corpus size. The only state kept
across the Tier 1 and Tier 2 passes is a set of Tier 1 hit chunk IDs
(``tier1_hit_chunk_ids``) — a few million short strings in the worst
case, still comfortably under a gigabyte.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
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
from src.store.relationship_store import RelationshipStore, Relationship

DIVIDER = "=" * 60


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


def load_chunks(store: LanceStore, limit: int = 0) -> list[dict]:
    """Load chunks from LanceDB for extraction.

    WARNING: This loads ALL chunks into memory. For 10M+ corpora, use
    iter_chunk_batches() instead to stream in batches.
    """
    tbl = store._table
    if tbl is None:
        return []
    columns = ["chunk_id", "text", "source_path"]
    if limit > 0:
        result = tbl.search().select(columns).limit(limit).to_arrow()
    else:
        result = tbl.search().select(columns).limit(store.count()).to_arrow()
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
        reader = (
            tbl.search()
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
        all_chunks = load_chunks(store, limit=limit)
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
    extractor = RegexPreExtractor(part_patterns=part_patterns)
    event_parser = EventBlockParser(part_patterns=part_patterns)
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


def _resolve_gliner_device(device: str) -> str | None:
    """Pick a CUDA device for GLiNER or return None if Tier 2 must abort."""
    import torch
    resolved = device
    if "cuda" in device:
        if not torch.cuda.is_available():
            print(f"  ERROR: CUDA requested ({device}) but not available. Aborting Tier 2.")
            print("  GLiNER on CPU is too slow for production. Fix CUDA or skip Tier 2.")
            return None
        requested_idx = int(device.split(":")[1]) if ":" in device else 0
        if requested_idx >= torch.cuda.device_count():
            resolved = "cuda:0"
            print(f"  NOTE: {device} not available (only {torch.cuda.device_count()} GPU(s)). Using {resolved}.")
        elif torch.cuda.device_count() > 1 and device == "cuda:1":
            free_0 = torch.cuda.mem_get_info(0)[0]
            free_1 = torch.cuda.mem_get_info(1)[0]
            if free_0 > free_1 * 1.5:
                resolved = "cuda:0"
                print(f"  NOTE: GPU 0 has significantly more free VRAM ({free_0/1e9:.1f}GB vs {free_1/1e9:.1f}GB). Using {resolved}.")
    return resolved


def run_tier2_gliner(
    store: LanceStore,
    tier1_hit_chunk_ids: set[str],
    device: str,
    model_name: str,
    min_chunk_len: int,
    min_confidence: float,
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
        Set of chunk_ids that produced at least one Tier 1 entity. Passed
        through but not currently used for filtering (see
        ``_is_tier2_candidate`` docstring for rationale).
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
    list[Entity]: de-duplication happens in the caller against the
    cross-tier ``seen`` set, so this function does not dedupe itself.
    """
    if gliner_model is None:
        try:
            from gliner import GLiNER
        except ImportError:
            print("  GLiNER not installed -- skipping Tier 2")
            return []

        resolved_device = _resolve_gliner_device(device)
        if resolved_device is None:
            return []

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

    labels = ["PERSON", "ORGANIZATION", "SITE", "FAILURE_MODE", "DATE"]
    label_map = {
        "PERSON": "PERSON",
        "ORGANIZATION": "ORG",
        "SITE": "SITE",
        "FAILURE_MODE": "PART",
        "DATE": "DATE",
    }

    all_entities: list[Entity] = []
    pending: list[dict] = []
    scanned = 0
    candidates = 0

    def flush_pending() -> None:
        """Run GLiNER on the pending batch and append extracted entities."""
        if not pending:
            return
        texts = [c["text"][:512] for c in pending]  # GLiNER works best on shorter text
        try:
            batch_results = model.batch_predict_entities(
                texts, labels, threshold=min_confidence, flat_ner=True,
            )
        except Exception as e:
            print(f"  GLiNER batch error at scanned={scanned:,}: {e}")
            pending.clear()
            return
        for chunk, entities in zip(pending, batch_results):
            for ent in entities:
                v2_type = label_map.get(ent["label"], ent["label"])
                all_entities.append(Entity(
                    entity_type=v2_type,
                    text=ent["text"].strip(),
                    raw_text=ent["text"],
                    confidence=ent["score"],
                    chunk_id=chunk["chunk_id"],
                    source_path=chunk["source_path"],
                    context="",
                ))
        pending.clear()

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
                f"candidates {candidates:,}, entities {len(all_entities):,}"
            )

    # Drain any remainder
    flush_pending()

    print(
        f"  Tier 2 filter: {scanned:,} scanned -> {candidates:,} candidates "
        f"({scanned - candidates:,} skipped by filter)"
    )

    return all_entities


def main() -> None:
    parser = argparse.ArgumentParser(description="Tiered entity extraction.")
    parser.add_argument("--tier", type=int, default=1, choices=[1, 2, 3],
                       help="Max tier to run (1=regex, 2=+GLiNER, 3=+LLM).")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--limit", type=int, default=0, help="Max chunks to process (0=all).")
    parser.add_argument("--benchmark", action="store_true",
                       help="Benchmark GLiNER CPU vs GPU on 1000 chunks.")
    parser.add_argument("--dry-run", action="store_true", help="Count only, don't write.")
    args = parser.parse_args()

    t0 = time.perf_counter()

    config = load_config(args.config)
    store = LanceStore(str(V2_ROOT / config.paths.lance_db))
    entity_store = EntityStore(str(V2_ROOT / config.paths.entity_db))
    rel_store = RelationshipStore(str(V2_ROOT / config.paths.entity_db).replace(
        "entities.sqlite3", "relationships.sqlite3"
    ))

    print(DIVIDER)
    print("  HybridRAG V2 -- Tiered Entity Extraction")
    print(DIVIDER)
    print(f"  Store:       {store.count():,} chunks")
    print(f"  Entities:    {entity_store.count_entities():,} existing")
    print(f"  Rels:        {rel_store.count():,} existing")
    print(f"  Max tier:    {args.tier}")
    print(f"  Limit:       {args.limit or 'all'}")
    print(f"  Threads:     {config.extraction.max_concurrent}")
    print(f"  Dry run:     {args.dry_run}")

    # --- Tier 1: Regex + Event Blocks + Relationships (streaming) ---
    total_chunks = store.count()
    if args.limit > 0:
        total_chunks = min(total_chunks, args.limit)
    print(f"  Total:       {total_chunks:,} chunks")
    print()

    print("  [TIER 1] Regex + event block + relationship extraction (streaming)...")
    t1_start = time.perf_counter()

    extractor = RegexPreExtractor(part_patterns=config.extraction.part_patterns)
    event_parser = EventBlockParser(part_patterns=config.extraction.part_patterns)
    rel_extractor = RegexRelationshipExtractor()

    seen: set = set()
    unique_t1: list[Entity] = []
    seen_rels: set = set()
    unique_rels: list[Relationship] = []
    chunks_processed = 0
    # Hit-set is all we carry across to Tier 2. Never the chunks themselves —
    # that's what blew up RAM to 57 GB in the old design (see module docstring).
    tier1_hit_chunk_ids: set[str] = set()

    for batch in iter_chunk_batches(store, batch_size=10000, limit=args.limit):
        for chunk in batch:
            text = chunk["text"]
            cid = chunk["chunk_id"]
            src = chunk["source_path"]

            entities = extractor.extract(text=text, chunk_id=cid, source_path=src)
            block_entities, block_rels = event_parser.parse(text=text, chunk_id=cid, source_path=src)
            co_rels = rel_extractor.extract(text=text, chunk_id=cid, source_path=src)

            chunk_had_hit = False
            for e in entities + block_entities:
                key = (e.chunk_id, e.entity_type, e.text)
                if key not in seen:
                    seen.add(key)
                    unique_t1.append(e)
                    chunk_had_hit = True
            if chunk_had_hit:
                tier1_hit_chunk_ids.add(cid)

            for r in block_rels + co_rels:
                key = (r.subject_text, r.predicate, r.object_text, r.chunk_id)
                if key not in seen_rels:
                    seen_rels.add(key)
                    unique_rels.append(r)

        chunks_processed += len(batch)
        elapsed = time.perf_counter() - t1_start
        rate = chunks_processed / max(elapsed, 0.001)
        print(f"  Tier 1: {chunks_processed:,} / {total_chunks:,} chunks "
              f"({rate:,.0f} chunks/sec, {len(unique_t1):,} entities, {len(unique_rels):,} rels)")

    t1_elapsed = time.perf_counter() - t1_start

    from collections import Counter
    t1_types = Counter(e.entity_type for e in unique_t1)
    t1_preds = Counter(r.predicate for r in unique_rels)
    print(f"  [TIER 1] {len(unique_t1):,} entities from {len(tier1_hit_chunk_ids):,} chunks ({t1_elapsed:.2f}s)")
    print(f"           Types: {dict(t1_types)}")
    print(f"           Rels:  {len(unique_rels):,} -- {dict(t1_preds)}")
    print(f"           Rate: {chunks_processed/max(t1_elapsed, 0.001):,.0f} chunks/sec")
    print()

    all_entities = list(unique_t1)
    all_rels = list(unique_rels)

    # --- Tier 2: GLiNER (second streaming pass over the store) ---
    if args.tier >= 2:
        print(f"  [TIER 2] GLiNER extraction via second streaming pass...")
        t2_start = time.perf_counter()
        tier2_entities = run_tier2_gliner(
            store=store,
            tier1_hit_chunk_ids=tier1_hit_chunk_ids,
            device=config.extraction.gliner_device,
            model_name=config.extraction.gliner_model,
            min_chunk_len=config.extraction.gliner_min_chunk_len,
            min_confidence=config.extraction.min_confidence,
            limit=args.limit,
        )
        t2_elapsed = time.perf_counter() - t2_start

        # Dedup against the cross-tier seen set
        new_t2_count = 0
        for e in tier2_entities:
            key = (e.chunk_id, e.entity_type, e.text)
            if key not in seen:
                seen.add(key)
                all_entities.append(e)
                new_t2_count += 1

        t2_types = Counter(e.entity_type for e in tier2_entities)
        print(f"  [TIER 2] {len(tier2_entities):,} entities raw, {new_t2_count:,} new after dedup ({t2_elapsed:.1f}s)")
        print(f"           Types: {dict(t2_types)}")
        print()

    # --- Tier 3: LLM ---
    if args.tier >= 3:
        print("  [TIER 3] LLM extraction (not yet implemented -- reserved for flagged items)")
        print()

    # --- Store ---
    if not args.dry_run and all_entities:
        before_e = entity_store.count_entities()
        inserted_e = entity_store.insert_entities(all_entities)
        after_e = entity_store.count_entities()
        print(f"  Entities:    {inserted_e:,} new (before={before_e:,}, after={after_e:,})")

    if not args.dry_run and all_rels:
        before_r = rel_store.count()
        inserted_r = rel_store.insert_relationships(all_rels)
        after_r = rel_store.count()
        print(f"  Rels:        {inserted_r:,} new (before={before_r:,}, after={after_r:,})")

    if args.dry_run:
        print(f"  DRY RUN:     would insert up to {len(all_entities):,} entities, {len(all_rels):,} rels")

    total_types = Counter(e.entity_type for e in all_entities)
    total_preds = Counter(r.predicate for r in all_rels)
    print()
    print(DIVIDER)
    print(f"  Total entities:      {len(all_entities):,}")
    print(f"  Entity breakdown:    {dict(total_types)}")
    print(f"  Total relationships: {len(all_rels):,}")
    print(f"  Rel breakdown:       {dict(total_preds)}")
    print(f"  Total time:          {time.perf_counter()-t0:.1f}s")
    print(DIVIDER)

    store.close()
    rel_store.close()


if __name__ == "__main__":
    main()
