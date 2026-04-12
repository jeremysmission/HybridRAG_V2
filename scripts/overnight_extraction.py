"""
Clone1 / phi4 Overnight Extraction -- NOT the V2 LanceStore tiering path.

IMPORTANT -- read this before running:
  This script is the Clone1 / Ollama-phi4 background runner. It pulls chunks
  from a HybridRAG3_Clone1 SQLite index (read-only) and runs phi4 LLM
  extraction via a local Ollama server, then writes entities and
  relationships into the V2 SQLite stores.

  This is NOT the same pipeline as ``scripts/tiered_extract.py``. If you
  want the V2 Tier 1 (regex) + Tier 2 (GLiNER) extraction pipeline that
  reads from the V2 LanceStore, use::

      .venv\\Scripts\\python.exe scripts\\tiered_extract.py --tier 1
      .venv\\Scripts\\python.exe scripts\\tiered_extract.py --tier 2   # GLiNER (GPU)

  or the GUI: ``start_gui.bat`` -> Skip Import -> Max Tier 1/2.

Two modes:
  - Single GPU (default): one Ollama stream on GPU 0
  - Split local mode: two processes, split chunks, merge results

Usage:
  python scripts/overnight_extraction.py
  python scripts/overnight_extraction.py --limit 1000 --gpu 0
  python scripts/overnight_extraction.py --limit 5000 --resume
  python scripts/overnight_extraction.py --status
  python scripts/overnight_extraction.py --clone1-db C:\\path\\to\\hybridrag.sqlite3

Output:
  - Entities + relationships in data/index/entities.sqlite3
  - Progress log in data/extraction_progress.json
  - Console output with timing and throughput stats
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.schema import load_config
from src.llm.client import LLMClient
from src.extraction.entity_extractor import EntityExtractor, RegexPreExtractor
from src.extraction.quality_gate import QualityGate
from src.store.entity_store import EntityStore
from src.store.relationship_store import RelationshipStore


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _default_clone1_db() -> str:
    """Resolve the default Clone1 SQLite path from the operator's home dir.

    Historical note: an earlier revision of this file used a raw-string
    literal ``r"{USER_HOME}\\HybridRAG3_Clone1\\..."`` that was never
    substituted by any templating step, so the script would hard-fail at
    startup on every machine with "Clone1 DB not found at {USER_HOME}\\...".
    Use ``Path.home()`` so the default resolves correctly on any Windows
    user profile, and let ``--clone1-db`` override it when the Clone1 index
    lives somewhere else.
    """
    return str(Path.home() / "HybridRAG3_Clone1" / "data" / "index" / "hybridrag.sqlite3")


CLONE1_DB = _default_clone1_db()
PROGRESS_FILE = "data/extraction_progress.json"
DEFAULT_LIMIT = 2000
BATCH_LOG_EVERY = 10  # log progress every N chunks


def load_progress(path: str) -> dict:
    """Load or create progress tracking file."""
    p = Path(path)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {"extracted_chunk_ids": [], "total_extracted": 0, "total_entities": 0,
            "total_relationships": 0, "started_at": None, "last_update": None}


def save_progress(path: str, progress: dict):
    """Save progress to JSON."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    progress["last_update"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(p, "w") as f:
        json.dump(progress, f, indent=2)


def sample_chunks_fast(db_path: str, limit: int, exclude_ids: set) -> list[dict]:
    """
    Fast rowid-based sampling from Clone1. Avoids ORDER BY RANDOM().
    Returns diverse chunks by stepping through rowid space evenly.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT MAX(rowid) FROM chunks")
    max_rowid = cur.fetchone()[0] or 1

    # Step evenly through rowid space for diversity
    step = max(1, max_rowid // (limit * 3))
    chunks = []
    rowid = random.randint(1, step)  # random start offset

    while len(chunks) < limit and rowid <= max_rowid:
        cur.execute("""
            SELECT chunk_id, text, source_path, text_length
            FROM chunks
            WHERE rowid >= ? AND text IS NOT NULL AND text_length > 100
            LIMIT 1
        """, (rowid,))

        row = cur.fetchone()
        if row and row["chunk_id"] not in exclude_ids:
            chunks.append({
                "chunk_id": row["chunk_id"],
                "text": row["text"],
                "source_path": row["source_path"] or "",
                "text_length": row["text_length"],
            })

        rowid += step + random.randint(0, step // 2)  # add jitter

    conn.close()
    return chunks


def print_status(progress_path: str):
    """Print current extraction status."""
    prog = load_progress(progress_path)
    print(f"Extraction Progress:")
    print(f"  Chunks extracted: {prog['total_extracted']}")
    print(f"  Entities found:   {prog['total_entities']}")
    print(f"  Relationships:    {prog['total_relationships']}")
    print(f"  Started:          {prog.get('started_at', 'never')}")
    print(f"  Last update:      {prog.get('last_update', 'never')}")
    if prog['total_extracted'] > 0 and prog.get('started_at'):
        start = time.mktime(time.strptime(prog['started_at'], "%Y-%m-%dT%H:%M:%S"))
        elapsed = time.time() - start
        rate = prog['total_extracted'] / max(elapsed, 1) * 60
        print(f"  Avg rate:         {rate:.1f} chunks/min")


def main():
    parser = argparse.ArgumentParser(
        description="Clone1 / phi4 overnight extraction runner (not the V2 LanceStore tiered_extract path)"
    )
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--clone1-db", default=CLONE1_DB)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help="Max chunks to extract this run")
    parser.add_argument("--gpu", type=int, default=0, help="GPU index (0 or 1)")
    parser.add_argument("--port", type=int, default=11434, help="Ollama port")
    parser.add_argument("--resume", action="store_true", help="Skip already-extracted chunks")
    parser.add_argument("--status", action="store_true", help="Print progress and exit")
    parser.add_argument("--dry-run", action="store_true", help="Sample and count but don't extract")
    args = parser.parse_args()

    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)

    if args.status:
        print_status(PROGRESS_FILE)
        return

    config = load_config(args.config)

    # Load progress for resume
    progress = load_progress(PROGRESS_FILE)
    exclude_ids = set(progress["extracted_chunk_ids"]) if args.resume else set()

    if not progress["started_at"]:
        progress["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    # Verify Clone1 exists
    if not Path(args.clone1_db).exists():
        print(f"ERROR: Clone1 DB not found at {args.clone1_db}")
        print()
        print("This script is the Clone1 / Ollama-phi4 overnight pipeline. It needs a")
        print("HybridRAG3_Clone1 SQLite index to read chunks from. If you do not have")
        print("Clone1 on this machine, you probably want a DIFFERENT pipeline:")
        print()
        print("  V2 Tier 1 (regex, safe unattended):")
        print("    .venv\\Scripts\\python.exe scripts\\tiered_extract.py --tier 1")
        print()
        print("  V2 Tier 2 (GLiNER GPU; do NOT run unattended while the known Tier 2")
        print("  CUDA issue is open):")
        print("    .venv\\Scripts\\python.exe scripts\\tiered_extract.py --tier 2")
        print()
        print("  GUI walk-away: start_gui.bat  ->  Skip Import  ->  Max Tier 1")
        print()
        print("Otherwise, point --clone1-db at an existing Clone1 index, for example:")
        print("  python scripts/overnight_extraction.py --clone1-db C:\\path\\to\\hybridrag.sqlite3")
        sys.exit(1)

    # Sample chunks
    print(f"Sampling {args.limit} chunks from Clone1 (excluding {len(exclude_ids)} already done)...")
    chunks = sample_chunks_fast(args.clone1_db, args.limit, exclude_ids)
    print(f"  Got {len(chunks)} chunks to process")

    if args.dry_run:
        lengths = [c["text_length"] for c in chunks]
        print(f"  Length range: {min(lengths)}-{max(lengths)} chars")
        print(f"  Avg length: {sum(lengths)/len(lengths):.0f} chars")
        print("  (dry-run, nothing extracted)")
        return

    if not chunks:
        print("No new chunks to extract.")
        return

    # Initialize extraction pipeline
    ollama_url = f"http://localhost:{args.port}/v1"
    llm_client = LLMClient(
        model="phi4:14b-q4_K_M",
        deployment="phi4:14b-q4_K_M",
        max_tokens=4096,
        temperature=0,
        timeout_seconds=300,
        provider_override="ollama",
    )

    if not llm_client.available:
        print(f"ERROR: Ollama not available at port {args.port}")
        print(f"  Start with: ollama serve")
        sys.exit(1)

    extractor = EntityExtractor(llm_client)
    regex_pre = RegexPreExtractor(part_patterns=config.extraction.part_patterns)
    quality_gate = QualityGate(
        min_confidence=config.extraction.min_confidence,
        vocab_path=config.paths.site_vocabulary,
        part_patterns=config.extraction.part_patterns,
    )
    entity_store = EntityStore(config.paths.entity_db)
    relationship_store = RelationshipStore(config.paths.entity_db)

    print(f"\nStarting extraction on GPU {args.gpu}, Ollama port {args.port}")
    print(f"  Model: phi4:14b-q4_K_M")
    print(f"  Chunks: {len(chunks)}")
    print(f"  Entity store: {config.paths.entity_db}")
    print(f"  Progress file: {PROGRESS_FILE}")
    print()

    # Run extraction
    start_time = time.time()
    session_entities = 0
    session_rels = 0
    session_errors = 0

    for i, chunk in enumerate(chunks):
        chunk_id = chunk["chunk_id"]
        text = chunk["text"]
        source_path = chunk["source_path"]

        try:
            # Tier 1: Regex (free, instant)
            regex_entities = regex_pre.extract(text, chunk_id, source_path)

            # Tier 3: phi4 LLM extraction
            result = extractor.extract_from_chunk(text, chunk_id, source_path)

            # Merge + quality gate
            all_entities = regex_entities + result.entities
            filtered_entities = quality_gate.filter_entities(all_entities)
            filtered_rels = quality_gate.filter_relationships(result.relationships)

            # Insert
            entity_store.insert_entities(filtered_entities)
            relationship_store.insert_relationships(filtered_rels)
            if result.table_rows:
                entity_store.insert_table_rows(result.table_rows)

            session_entities += len(filtered_entities)
            session_rels += len(filtered_rels)

            # Track progress
            progress["extracted_chunk_ids"].append(chunk_id)
            progress["total_extracted"] += 1
            progress["total_entities"] += len(filtered_entities)
            progress["total_relationships"] += len(filtered_rels)

        except Exception as e:
            session_errors += 1
            print(f"  ERROR on chunk {chunk_id[:16]}: {e}")

        # Progress logging
        if (i + 1) % BATCH_LOG_EVERY == 0 or (i + 1) == len(chunks):
            elapsed = time.time() - start_time
            rate = (i + 1) / max(elapsed, 0.01) * 60
            save_progress(PROGRESS_FILE, progress)
            print(
                f"  [{i+1}/{len(chunks)}] "
                f"{session_entities} entities, {session_rels} rels, "
                f"{session_errors} errors, "
                f"{rate:.1f} chunks/min, "
                f"{elapsed:.0f}s elapsed"
            )

    # Final summary
    elapsed = time.time() - start_time
    rate = len(chunks) / max(elapsed, 0.01) * 60
    save_progress(PROGRESS_FILE, progress)

    print(f"\n{'='*60}")
    print(f"Extraction complete")
    print(f"  Chunks processed: {len(chunks)}")
    print(f"  Entities:         {session_entities}")
    print(f"  Relationships:    {session_rels}")
    print(f"  Errors:           {session_errors}")
    print(f"  Rate:             {rate:.1f} chunks/min")
    print(f"  Elapsed:          {elapsed:.0f}s ({elapsed/60:.1f}m)")
    print(f"  Entity store:     {entity_store.count_entities()} total")
    print(f"  Relationship store: {relationship_store.count()} total")
    print(f"{'='*60}")

    entity_store.close()
    relationship_store.close()


if __name__ == "__main__":
    main()
