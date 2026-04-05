"""
Entity extraction runner — processes LanceDB chunks through GPT-4o extractor.

Reads chunks from the LanceDB store, extracts entities + relationships + tables,
applies quality gates, and inserts into SQLite stores.

Usage:
  python scripts/extract_entities.py
  python scripts/extract_entities.py --config config/config.yaml --batch-size 10
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.schema import load_config
from src.store.lance_store import LanceStore
from src.store.entity_store import EntityStore
from src.store.relationship_store import RelationshipStore
from src.llm.client import LLMClient
from src.extraction.entity_extractor import EntityExtractor, RegexPreExtractor
from src.extraction.quality_gate import QualityGate


def main():
    parser = argparse.ArgumentParser(description="Extract entities from indexed chunks")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--batch-size", type=int, default=10, help="Chunks per batch")
    parser.add_argument("--limit", type=int, default=0, help="Max chunks to process (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Extract but don't insert")
    args = parser.parse_args()

    config = load_config(args.config)

    # Initialize stores
    lance_store = LanceStore(config.paths.lance_db)
    entity_store = EntityStore(config.paths.entity_db)
    relationship_store = RelationshipStore(config.paths.entity_db)

    # Initialize LLM
    llm_client = LLMClient(
        api_base=config.llm.api_base,
        api_version=config.llm.api_version,
        model=config.llm.model,
        deployment=config.llm.deployment,
        max_tokens=config.llm.max_tokens,
        temperature=config.llm.temperature,
        timeout_seconds=config.llm.timeout_seconds,
    )

    if not llm_client.available:
        print("ERROR: LLM not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY.")
        sys.exit(1)

    extractor = EntityExtractor(llm_client)
    regex_pre = RegexPreExtractor(part_patterns=config.extraction.part_patterns)
    quality_gate = QualityGate(
        min_confidence=config.extraction.min_confidence,
        vocab_path=config.paths.site_vocabulary,
        part_patterns=config.extraction.part_patterns,
    )

    # Read all chunks from LanceDB
    total_chunks = lance_store.count()
    if total_chunks == 0:
        print("No chunks in LanceDB store. Run import first.")
        sys.exit(1)

    print(f"Processing {total_chunks} chunks from LanceDB...")

    # Fetch chunks
    try:
        table = lance_store._table
        limit = args.limit if args.limit > 0 else total_chunks
        all_chunks = table.search().select(
            ["chunk_id", "text", "source_path"]
        ).limit(limit).to_list()
    except Exception as e:
        print(f"ERROR reading chunks: {e}")
        sys.exit(1)

    total_entities = 0
    total_rels = 0
    total_tables = 0
    total_tokens_in = 0
    total_tokens_out = 0
    start_time = time.time()

    for i in range(0, len(all_chunks), args.batch_size):
        batch = all_chunks[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1

        for chunk in batch:
            chunk_id = chunk["chunk_id"]
            text = chunk["text"]
            source_path = chunk["source_path"]

            # Regex pre-extraction (fast, free)
            regex_entities = regex_pre.extract(text, chunk_id, source_path)

            # GPT-4o extraction (slow, costs tokens)
            result = extractor.extract_from_chunk(text, chunk_id, source_path)

            # Merge regex + LLM entities (LLM wins on dedup via quality gate)
            all_entities = regex_entities + result.entities
            filtered_entities = quality_gate.filter_entities(all_entities)
            filtered_rels = quality_gate.filter_relationships(result.relationships)

            if not args.dry_run:
                entity_store.insert_entities(filtered_entities)
                relationship_store.insert_relationships(filtered_rels)
                entity_store.insert_table_rows(result.table_rows)

            total_entities += len(filtered_entities)
            total_rels += len(filtered_rels)
            total_tables += len(result.table_rows)
            total_tokens_in += result.input_tokens
            total_tokens_out += result.output_tokens

        elapsed = time.time() - start_time
        processed = min(i + args.batch_size, len(all_chunks))
        print(
            f"  Batch {batch_num}: {processed}/{len(all_chunks)} chunks, "
            f"{total_entities} entities, {total_rels} relationships, "
            f"{total_tables} table rows ({elapsed:.1f}s)"
        )

    elapsed = time.time() - start_time
    print(f"\nExtraction complete in {elapsed:.1f}s:")
    print(f"  Chunks processed: {len(all_chunks)}")
    print(f"  Entities: {total_entities}")
    print(f"  Relationships: {total_rels}")
    print(f"  Table rows: {total_tables}")
    print(f"  Tokens: {total_tokens_in} in / {total_tokens_out} out")

    if args.dry_run:
        print("  (dry-run — nothing inserted)")
    else:
        print(f"  Entity store: {entity_store.count_entities()} total entities")
        print(f"  Relationship store: {relationship_store.count()} total relationships")
        print(f"  Entity types: {entity_store.entity_type_summary()}")

    entity_store.close()
    relationship_store.close()


if __name__ == "__main__":
    main()
