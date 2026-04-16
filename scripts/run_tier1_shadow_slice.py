#!/usr/bin/env python3
"""
Run a bounded Tier 1 shadow extraction against a sampled slice of the live
LanceDB store, writing entities/relationships to an isolated shadow SQLite
store instead of the authoritative database.

This is the execution companion to the pre-rerun regex gate:

1. sample representative chunks from the live store
2. run Tier 1 extraction on that sampled slice
3. persist to an isolated shadow DB
4. emit summary counts and top PO/PART values for approval review
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.config.schema import load_config
from src.store.entity_store import EntityStore, Entity
from src.store.relationship_store import RelationshipStore, Relationship
from src.extraction.entity_extractor import (
    RegexPreExtractor,
    EventBlockParser,
    RegexRelationshipExtractor,
    RelationshipPhraseExtractor,
)
from scripts.audit_tier1_regex_gate import sample_chunks_from_store


def build_extractor(config_path: str) -> RegexPreExtractor:
    """Assemble the structured object this workflow needs for its next step."""
    config = load_config(config_path)
    return RegexPreExtractor(
        part_patterns=config.extraction.part_patterns,
        security_standard_exclude_patterns=config.extraction.security_standard_exclude_patterns,
    )


def ensure_parent(path: Path) -> None:
    """Support the run tier1 shadow slice workflow by handling the ensure parent step."""
    path.parent.mkdir(parents=True, exist_ok=True)


def reset_shadow_dbs(entity_db: Path, rel_db: Path) -> None:
    """Support the run tier1 shadow slice workflow by handling the reset shadow dbs step."""
    if entity_db.exists():
        entity_db.unlink()
    if rel_db.exists():
        rel_db.unlink()


def query_top_entities(entity_db: Path, entity_type: str, limit: int = 20) -> list[dict]:
    """Run a focused lookup against the underlying stores and return the matching data."""
    if not entity_db.exists():
        return []
    conn = sqlite3.connect(entity_db)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT text, COUNT(*) AS c
            FROM entities
            WHERE entity_type = ?
            GROUP BY text
            ORDER BY c DESC, text ASC
            LIMIT ?
            """,
            (entity_type, limit),
        )
        return [{"text": row[0], "count": row[1]} for row in cur.fetchall()]
    finally:
        conn.close()


def main() -> int:
    """Parse command-line inputs and run the main run tier1 shadow slice workflow."""
    parser = argparse.ArgumentParser(description="Run an isolated Tier 1 shadow slice.")
    parser.add_argument("--config", default="config/config.tier1_shadow_2026-04-13.yaml")
    parser.add_argument("--sample-limit", type=int, default=5000)
    parser.add_argument("--sample-seed", type=int, default=42)
    parser.add_argument("--sample-mode", choices=("stratified", "random"), default="stratified")
    parser.add_argument("--max-scan-chunks", type=int, default=50000)
    parser.add_argument("--reset", action="store_true", help="Delete existing shadow DBs before running.")
    parser.add_argument("--json-out", default="", help="Optional JSON output path.")
    args = parser.parse_args()

    config = load_config(args.config)
    entity_db = V2_ROOT / config.paths.entity_db
    rel_db = Path(str(entity_db).replace("entities.sqlite3", "relationships.sqlite3"))
    ensure_parent(entity_db)

    if args.reset:
        reset_shadow_dbs(entity_db, rel_db)

    extractor = build_extractor(args.config)
    event_parser = EventBlockParser(
        part_patterns=config.extraction.part_patterns,
        security_standard_exclude_patterns=config.extraction.security_standard_exclude_patterns,
    )
    rel_extractor = RegexRelationshipExtractor()
    phrase_extractor = RelationshipPhraseExtractor()

    selection = sample_chunks_from_store(
        extractor=extractor,
        sample_limit=args.sample_limit,
        seed=args.sample_seed,
        sample_mode=args.sample_mode,
        max_scan_chunks=args.max_scan_chunks,
    )

    entity_store = EntityStore(str(entity_db))
    rel_store = RelationshipStore(str(rel_db))

    seen_entities: set[tuple[str, str, str]] = set()
    seen_rels: set[tuple[str, str, str, str]] = set()
    entities: list[Entity] = []
    rels: list[Relationship] = []

    for chunk in selection.chunks:
        extracted = extractor.extract(chunk.text, chunk.chunk_id, chunk.source_path)
        block_entities, block_rels = event_parser.parse(
            text=chunk.text,
            chunk_id=chunk.chunk_id,
            source_path=chunk.source_path,
        )
        co_rels = rel_extractor.extract(
            text=chunk.text,
            chunk_id=chunk.chunk_id,
            source_path=chunk.source_path,
        )
        p_rels = phrase_extractor.extract(
            text=chunk.text,
            chunk_id=chunk.chunk_id,
            source_path=chunk.source_path,
        )

        for entity in extracted + block_entities:
            key = (entity.chunk_id, entity.entity_type, entity.text)
            if key not in seen_entities:
                seen_entities.add(key)
                entities.append(entity)

        for rel in block_rels + co_rels + p_rels:
            key = (rel.subject_text, rel.predicate, rel.object_text, rel.chunk_id)
            if key not in seen_rels:
                seen_rels.add(key)
                rels.append(rel)

    if entities:
        entity_store.insert_entities(entities)
    if rels:
        rel_store.insert_relationships(rels)

    type_counts = Counter(entity.entity_type for entity in entities)
    pred_counts = Counter(rel.predicate for rel in rels)
    top_pos = query_top_entities(entity_db, "PO", limit=20)
    top_parts = query_top_entities(entity_db, "PART", limit=30)

    report = {
        "config": args.config,
        "entity_db": str(entity_db),
        "relationship_db": str(rel_db),
        "sample_limit": args.sample_limit,
        "sample_seed": args.sample_seed,
        "sample_mode": args.sample_mode,
        "max_scan_chunks": args.max_scan_chunks,
        "scanned_chunks": selection.scanned_chunks,
        "selected_chunks": len(selection.chunks),
        "stratum_seen": dict(selection.stratum_seen),
        "entity_total": len(entities),
        "relationship_total": len(rels),
        "entity_breakdown": dict(type_counts),
        "relationship_breakdown": dict(pred_counts),
        "top_po": top_pos,
        "top_part": top_parts,
    }

    print("=" * 72)
    print("TIER 1 SHADOW SLICE")
    print("=" * 72)
    print(f"Shadow entity DB: {entity_db}")
    print(f"Shadow rel DB:    {rel_db}")
    print(f"Scanned chunks:   {selection.scanned_chunks:,}")
    print(f"Selected chunks:  {len(selection.chunks):,} ({args.sample_mode})")
    print(f"Entities:         {len(entities):,}")
    print(f"Relationships:    {len(rels):,}")
    print(f"Entity breakdown: {dict(type_counts)}")
    print(f"Top PO:           {top_pos[:10]}")
    print(f"Top PART:         {top_parts[:10]}")

    if args.json_out:
        out_path = Path(args.json_out)
        ensure_parent(out_path)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"JSON report:      {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
