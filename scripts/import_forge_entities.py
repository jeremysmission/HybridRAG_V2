"""
Import CorpusForge S3+ entity exports into HybridRAG V2 entity store.

Reads entities.jsonl from a Forge export directory, maps GLiNER labels
to V2 entity types, applies quality gates, and inserts into the SQLite
entity store.

Usage:
    python scripts/import_forge_entities.py --source C:/CorpusForge/data/output/export_YYYYMMDD_HHMM
    python scripts/import_forge_entities.py --source path/to/export --dry-run
    python scripts/import_forge_entities.py --source path/to/export --min-confidence 0.5
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.store.entity_store import EntityStore, Entity

DIVIDER = "=" * 55

# Map GLiNER labels to V2 entity types
# Forge S3 GLiNER uses: PERSON, ORGANIZATION, LOCATION, DATE, PART_NUMBER,
# PURCHASE_ORDER, FAILURE_MODE, ACTION, SITE, EMAIL, PHONE
LABEL_MAP = {
    "PERSON": "PERSON",
    "ORGANIZATION": "ORG",
    "ORG": "ORG",
    "LOCATION": "SITE",
    "SITE": "SITE",
    "DATE": "DATE",
    "PART_NUMBER": "PART",
    "PART": "PART",
    "PURCHASE_ORDER": "PO",
    "PO": "PO",
    "EMAIL": "CONTACT",
    "PHONE": "CONTACT",
    "CONTACT": "CONTACT",
    "FAILURE_MODE": "PART",  # failures tied to parts
    "ACTION": "ORG",         # maintenance actions -> org context
}

# V2 valid entity types
VALID_TYPES = {"PERSON", "PART", "SITE", "DATE", "PO", "ORG", "CONTACT"}


def load_forge_entities(export_dir: Path) -> list[dict]:
    """Load entities.jsonl from a Forge export."""
    entities_path = export_dir / "entities.jsonl"
    if not entities_path.exists():
        print(f"  ERROR: {entities_path} not found", file=sys.stderr)
        sys.exit(1)

    entities = []
    with open(entities_path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                entities.append(json.loads(line))
    return entities


def map_entity(raw: dict, source_map: dict[str, str]) -> Entity | None:
    """
    Map a Forge entity dict to a V2 Entity object.

    Returns None if the entity should be skipped.
    """
    label = raw.get("label", "").upper()
    v2_type = LABEL_MAP.get(label)
    if not v2_type:
        return None

    text = raw.get("text", "").strip()
    if not text:
        return None

    chunk_id = raw.get("chunk_id", "")
    confidence = raw.get("score", 0.0)
    source_path = source_map.get(chunk_id, "")

    return Entity(
        entity_type=v2_type,
        text=text,
        raw_text=text,
        confidence=confidence,
        chunk_id=chunk_id,
        source_path=source_path,
        context="",
    )


def build_source_map(export_dir: Path) -> dict[str, str]:
    """Build chunk_id -> source_path mapping from chunks.jsonl."""
    chunks_path = export_dir / "chunks.jsonl"
    mapping = {}
    if chunks_path.exists():
        with open(chunks_path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line:
                    chunk = json.loads(line)
                    cid = chunk.get("chunk_id", "")
                    src = chunk.get("source_path", "")
                    if cid and src:
                        mapping[cid] = src
    return mapping


def main() -> None:
    """Parse command-line inputs and run the main import forge entities workflow."""
    parser = argparse.ArgumentParser(
        description="Import CorpusForge entity exports into V2 entity store."
    )
    parser.add_argument(
        "--source", required=True,
        help="Path to CorpusForge export directory (must contain entities.jsonl).",
    )
    parser.add_argument(
        "--entity-db", default=None,
        help="Path to V2 entity SQLite DB (default: from config).",
    )
    parser.add_argument(
        "--min-confidence", type=float, default=0.5,
        help="Minimum confidence score for import (default: 0.5).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be imported without writing.",
    )
    args = parser.parse_args()

    export_dir = Path(args.source)
    if not export_dir.is_dir():
        print(f"  ERROR: {export_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    # Resolve entity DB path
    if args.entity_db:
        db_path = args.entity_db
    else:
        from src.config.schema import load_config
        config = load_config("config/config.yaml")
        db_path = str(V2_ROOT / config.paths.entity_db)

    print(DIVIDER)
    print("  HybridRAG V2 -- Import Forge Entities")
    print(DIVIDER)
    print(f"  Source:     {export_dir}")
    print(f"  Entity DB: {db_path}")
    print(f"  Min conf:  {args.min_confidence}")
    print(f"  Dry run:   {args.dry_run}")
    print()

    # Load
    raw_entities = load_forge_entities(export_dir)
    print(f"  Raw entities loaded: {len(raw_entities)}")

    source_map = build_source_map(export_dir)
    print(f"  Chunk->source map:   {len(source_map)} entries")

    # Map and filter
    label_counts = Counter(e.get("label", "UNKNOWN").upper() for e in raw_entities)
    print(f"\n  Label distribution (Forge):")
    for label, count in label_counts.most_common():
        v2_type = LABEL_MAP.get(label, "SKIP")
        print(f"    {label:20s} -> {v2_type:10s} : {count}")

    mapped = []
    skipped_label = 0
    skipped_confidence = 0
    for raw in raw_entities:
        entity = map_entity(raw, source_map)
        if entity is None:
            skipped_label += 1
            continue
        if entity.confidence < args.min_confidence:
            skipped_confidence += 1
            continue
        mapped.append(entity)

    print(f"\n  Mapped entities:       {len(mapped)}")
    print(f"  Skipped (bad label):   {skipped_label}")
    print(f"  Skipped (low conf):    {skipped_confidence}")

    type_counts = Counter(e.entity_type for e in mapped)
    print(f"\n  V2 type distribution:")
    for etype, count in type_counts.most_common():
        print(f"    {etype:10s} : {count}")

    if args.dry_run:
        print(f"\n{DIVIDER}")
        print("  DRY RUN -- no data written.")
        print(DIVIDER)
        return

    # Import
    t0 = time.perf_counter()
    store = EntityStore(db_path)
    before = store.count_entities()
    inserted = store.insert_entities(mapped)
    after = store.count_entities()
    elapsed = time.perf_counter() - t0

    print(f"\n  Before:    {before:,} entities")
    print(f"  Inserted:  {inserted:,} new entities")
    print(f"  After:     {after:,} entities")
    print(f"  Time:      {elapsed:.2f}s")
    print(DIVIDER)
    print("  Entity import complete.")
    print(DIVIDER)


if __name__ == "__main__":
    main()
