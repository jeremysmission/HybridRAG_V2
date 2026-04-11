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


def iter_chunk_batches(store: LanceStore, batch_size: int = 10000, limit: int = 0):
    """Stream chunks from LanceDB in batches without loading all into memory.

    Yields lists of chunk dicts, each up to batch_size.
    Total memory: ~batch_size * avg_chunk_size instead of entire corpus.
    """
    tbl = store._table
    if tbl is None:
        return
    columns = ["chunk_id", "text", "source_path"]
    try:
        scanner = tbl.to_lance().scanner(
            columns=columns,
            batch_size=batch_size,
        )
        yielded = 0
        for arrow_batch in scanner.to_batches():
            chunks = []
            for i in range(arrow_batch.num_rows):
                chunks.append({
                    "chunk_id": str(arrow_batch.column("chunk_id")[i]),
                    "text": str(arrow_batch.column("text")[i]),
                    "source_path": str(arrow_batch.column("source_path")[i]),
                })
            if limit > 0 and yielded + len(chunks) > limit:
                chunks = chunks[:limit - yielded]
            if chunks:
                yield chunks
                yielded += len(chunks)
            if limit > 0 and yielded >= limit:
                return
    except Exception:
        # Fallback to search-based loading if lance scanner not available
        all_chunks = load_chunks(store, limit=limit)
        for i in range(0, len(all_chunks), batch_size):
            yield all_chunks[i:i + batch_size]


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


def run_tier2_gliner(
    chunks: list[dict],
    tier1_chunk_ids: set[str],
    device: str,
    model_name: str,
    min_chunk_len: int,
    min_confidence: float,
    max_concurrent: int,
) -> list[Entity]:
    """Tier 2: GLiNER on filtered chunks (skip short, numeric, fully extracted)."""
    try:
        from gliner import GLiNER
    except ImportError:
        print("  GLiNER not installed -- skipping Tier 2")
        return []

    # Filter: skip short chunks, pure numeric, already well-extracted by T1
    filtered = []
    for c in chunks:
        text = c["text"].strip()
        if len(text) < min_chunk_len:
            continue
        # Skip pure numeric/whitespace
        alpha_ratio = sum(1 for ch in text if ch.isalpha()) / max(len(text), 1)
        if alpha_ratio < 0.3:
            continue
        filtered.append(c)

    print(f"  Tier 2 filter: {len(chunks)} -> {len(filtered)} chunks ({len(chunks)-len(filtered)} skipped)")

    # Load GLiNER with GPU auto-detection
    import torch
    resolved_device = device
    if "cuda" in device:
        if not torch.cuda.is_available():
            print(f"  ERROR: CUDA requested ({device}) but not available. Aborting Tier 2.")
            print(f"  GLiNER on CPU is too slow for production. Fix CUDA or skip Tier 2.")
            return []
        # Auto-resolve: if cuda:1 requested but only 1 GPU, fall back to cuda:0
        requested_idx = int(device.split(":")[1]) if ":" in device else 0
        if requested_idx >= torch.cuda.device_count():
            resolved_device = "cuda:0"
            print(f"  NOTE: {device} not available (only {torch.cuda.device_count()} GPU(s)). Using {resolved_device}.")
        # Pick the GPU with more free memory if no specific index was forced
        elif torch.cuda.device_count() > 1 and device == "cuda:1":
            free_0 = torch.cuda.mem_get_info(0)[0]
            free_1 = torch.cuda.mem_get_info(1)[0]
            if free_0 > free_1 * 1.5:
                resolved_device = "cuda:0"
                print(f"  NOTE: GPU 0 has significantly more free VRAM ({free_0/1e9:.1f}GB vs {free_1/1e9:.1f}GB). Using {resolved_device}.")

    print(f"  Loading GLiNER model: {model_name} on {resolved_device}")
    model = GLiNER.from_pretrained(model_name)
    if "cuda" in resolved_device:
        gpu_idx = int(resolved_device.split(":")[1]) if ":" in resolved_device else 0
        model = model.to(resolved_device)
        print(f"  GLiNER on {resolved_device}: {torch.cuda.get_device_name(gpu_idx)}")
        free, total = torch.cuda.mem_get_info(gpu_idx)
        print(f"  VRAM after model load: {free/1e9:.1f}GB free / {total/1e9:.1f}GB total")

    labels = ["PERSON", "ORGANIZATION", "SITE", "FAILURE_MODE", "DATE"]
    label_map = {
        "PERSON": "PERSON",
        "ORGANIZATION": "ORG",
        "SITE": "SITE",
        "FAILURE_MODE": "PART",
        "DATE": "DATE",
    }

    all_entities: list[Entity] = []
    batch_size = 8

    for i in range(0, len(filtered), batch_size):
        batch = filtered[i:i + batch_size]
        texts = [c["text"][:512] for c in batch]  # GLiNER works best on shorter text
        try:
            batch_results = model.batch_predict_entities(
                texts, labels, threshold=min_confidence, flat_ner=True,
            )
            for chunk, entities in zip(batch, batch_results):
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
        except Exception as e:
            print(f"  GLiNER batch error at {i}: {e}")

        if (i + batch_size) % 500 == 0:
            print(f"  GLiNER progress: {min(i+batch_size, len(filtered))}/{len(filtered)} chunks, {len(all_entities)} entities")

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

    seen = set()
    unique_t1 = []
    seen_rels = set()
    unique_rels = []
    chunks_processed = 0
    all_chunks_for_tier2 = [] if args.tier >= 2 else None

    for batch in iter_chunk_batches(store, batch_size=10000, limit=args.limit):
        for chunk in batch:
            text = chunk["text"]
            cid = chunk["chunk_id"]
            src = chunk["source_path"]

            entities = extractor.extract(text=text, chunk_id=cid, source_path=src)
            block_entities, block_rels = event_parser.parse(text=text, chunk_id=cid, source_path=src)
            co_rels = rel_extractor.extract(text=text, chunk_id=cid, source_path=src)

            for e in entities + block_entities:
                key = (e.chunk_id, e.entity_type, e.text)
                if key not in seen:
                    seen.add(key)
                    unique_t1.append(e)

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

        # Keep chunks in memory only if Tier 2 needs them
        if all_chunks_for_tier2 is not None:
            all_chunks_for_tier2.extend(batch)

    t1_elapsed = time.perf_counter() - t1_start

    tier1_chunk_ids = {e.chunk_id for e in unique_t1}
    from collections import Counter
    t1_types = Counter(e.entity_type for e in unique_t1)
    t1_preds = Counter(r.predicate for r in unique_rels)
    print(f"  [TIER 1] {len(unique_t1):,} entities from {len(tier1_chunk_ids):,} chunks ({t1_elapsed:.2f}s)")
    print(f"           Types: {dict(t1_types)}")
    print(f"           Rels:  {len(unique_rels):,} -- {dict(t1_preds)}")
    print(f"           Rate: {chunks_processed/max(t1_elapsed, 0.001):,.0f} chunks/sec")
    print()

    all_entities = list(unique_t1)
    all_rels = list(unique_rels)

    # --- Tier 2: GLiNER ---
    if args.tier >= 2:
        if all_chunks_for_tier2 is None or len(all_chunks_for_tier2) == 0:
            print("  [TIER 2] No chunks available for GLiNER (streaming mode). Re-loading for Tier 2...")
            all_chunks_for_tier2 = load_chunks(store, limit=args.limit)
        print(f"  [TIER 2] GLiNER extraction on {len(all_chunks_for_tier2):,} chunks...")
        t2_start = time.perf_counter()
        tier2_entities = run_tier2_gliner(
            chunks=all_chunks_for_tier2,
            tier1_chunk_ids=tier1_chunk_ids,
            device=config.extraction.gliner_device,
            model_name=config.extraction.gliner_model,
            min_chunk_len=config.extraction.gliner_min_chunk_len,
            min_confidence=config.extraction.min_confidence,
            max_concurrent=config.extraction.max_concurrent,
        )
        t2_elapsed = time.perf_counter() - t2_start

        # Dedup
        for e in tier2_entities:
            key = (e.chunk_id, e.entity_type, e.text)
            if key not in seen:
                seen.add(key)
                all_entities.append(e)

        t2_types = Counter(e.entity_type for e in tier2_entities)
        print(f"  [TIER 2] {len(tier2_entities):,} entities ({t2_elapsed:.1f}s)")
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
