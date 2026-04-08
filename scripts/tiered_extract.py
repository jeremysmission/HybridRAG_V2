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

Time estimates (Beast, 49K chunks):
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
from src.extraction.entity_extractor import RegexPreExtractor

DIVIDER = "=" * 60


def load_chunks(store: LanceStore, limit: int = 0) -> list[dict]:
    """Load chunks from LanceDB for extraction."""
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


def run_tier1(
    chunks: list[dict],
    part_patterns: list[str],
    max_concurrent: int,
) -> list[Entity]:
    """Tier 1: Regex extraction on all chunks. Threaded."""
    extractor = RegexPreExtractor(part_patterns=part_patterns)
    all_entities: list[Entity] = []

    def extract_one(chunk: dict) -> list[Entity]:
        return extractor.extract(
            text=chunk["text"],
            chunk_id=chunk["chunk_id"],
            source_path=chunk["source_path"],
        )

    with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
        futures = {pool.submit(extract_one, c): c for c in chunks}
        for future in as_completed(futures):
            try:
                all_entities.extend(future.result())
            except Exception as e:
                pass  # skip errors silently for regex

    return all_entities


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

    # Load GLiNER
    print(f"  Loading GLiNER model: {model_name} on {device}")
    model = GLiNER.from_pretrained(model_name)
    if "cuda" in device:
        import torch
        if torch.cuda.is_available():
            model = model.to(device)
            print(f"  GLiNER on {device}: {torch.cuda.get_device_name(int(device.split(':')[1]))}")
        else:
            print(f"  CUDA not available, falling back to CPU")

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

    print(DIVIDER)
    print("  HybridRAG V2 -- Tiered Entity Extraction")
    print(DIVIDER)
    print(f"  Store:       {store.count():,} chunks")
    print(f"  Entities:    {entity_store.count_entities():,} existing")
    print(f"  Max tier:    {args.tier}")
    print(f"  Limit:       {args.limit or 'all'}")
    print(f"  Threads:     {config.extraction.max_concurrent}")
    print(f"  Dry run:     {args.dry_run}")

    # Load chunks
    t0 = time.perf_counter()
    chunks = load_chunks(store, limit=args.limit)
    print(f"  Loaded:      {len(chunks):,} chunks ({time.perf_counter()-t0:.1f}s)")
    print()

    # --- Tier 1: Regex ---
    print("  [TIER 1] Regex extraction ...")
    t1_start = time.perf_counter()
    tier1_entities = run_tier1(chunks, config.extraction.part_patterns, config.extraction.max_concurrent)
    t1_elapsed = time.perf_counter() - t1_start

    # Dedup by (chunk_id, entity_type, text)
    seen = set()
    unique_t1 = []
    for e in tier1_entities:
        key = (e.chunk_id, e.entity_type, e.text)
        if key not in seen:
            seen.add(key)
            unique_t1.append(e)

    tier1_chunk_ids = {e.chunk_id for e in unique_t1}
    from collections import Counter
    t1_types = Counter(e.entity_type for e in unique_t1)
    print(f"  [TIER 1] {len(unique_t1):,} entities from {len(tier1_chunk_ids):,} chunks ({t1_elapsed:.2f}s)")
    print(f"           Types: {dict(t1_types)}")
    print(f"           Rate: {len(chunks)/max(t1_elapsed, 0.001):,.0f} chunks/sec")
    print()

    all_entities = list(unique_t1)

    # --- Tier 2: GLiNER ---
    if args.tier >= 2:
        print("  [TIER 2] GLiNER extraction ...")
        t2_start = time.perf_counter()
        tier2_entities = run_tier2_gliner(
            chunks=chunks,
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
        before = entity_store.count_entities()
        inserted = entity_store.insert_entities(all_entities)
        after = entity_store.count_entities()
        print(f"  Stored:      {inserted:,} new entities (before={before:,}, after={after:,})")
    elif args.dry_run:
        print(f"  DRY RUN:     would insert up to {len(all_entities):,} entities")

    total_types = Counter(e.entity_type for e in all_entities)
    print()
    print(DIVIDER)
    print(f"  Total entities: {len(all_entities):,}")
    print(f"  Type breakdown: {dict(total_types)}")
    print(f"  Total time:     {time.perf_counter()-t0:.1f}s")
    print(DIVIDER)

    store.close()


if __name__ == "__main__":
    main()
