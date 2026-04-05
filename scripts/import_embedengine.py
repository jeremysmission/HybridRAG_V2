"""
Import CorpusForge export into HybridRAG V2 LanceDB store.

Reads chunks.jsonl + vectors.npy + manifest.json from a CorpusForge export
directory and loads them into the vector store with FTS indexing.

Usage:
  python scripts/import_embedengine.py --source C:/CorpusForge/data/export/export_YYYYMMDD_HHMM
  python scripts/import_embedengine.py --source path/to/export --dry-run
  python scripts/import_embedengine.py --source path/to/export --create-index
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.schema import load_config
from src.store.lance_store import LanceStore


DIVIDER = "=" * 55


def resolve_export_dir(source: Path) -> Path:
    """Resolve source path, following text-file redirects if needed."""
    if source.is_file() and source.suffix not in (".jsonl", ".npy", ".json"):
        # Text file pointing to real export dir
        real_path = source.read_text(encoding="utf-8-sig").strip()
        return Path(real_path)
    return source


def load_export(export_dir: Path) -> tuple[list[dict], np.ndarray, dict, dict | None]:
    """
    Load chunks, vectors, manifest, and optional skip_manifest
    from a CorpusForge export directory.

    Returns:
        (chunks, vectors, manifest, skip_manifest_or_None)
    """
    export_dir = resolve_export_dir(export_dir)

    chunks_path = export_dir / "chunks.jsonl"
    vectors_path = export_dir / "vectors.npy"
    manifest_path = export_dir / "manifest.json"
    skip_manifest_path = export_dir / "skip_manifest.json"

    # Validate required files
    missing = []
    if not chunks_path.exists():
        missing.append(str(chunks_path))
    if not vectors_path.exists():
        missing.append(str(vectors_path))
    if missing:
        for m in missing:
            print(f"  ERROR: Required file not found: {m}", file=sys.stderr)
        sys.exit(1)

    # Load chunks
    chunks = []
    with open(chunks_path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    # Load vectors — memory-map large files to avoid OOM on multi-GB arrays
    vec_file_bytes = vectors_path.stat().st_size
    MMAP_THRESHOLD = 500 * 1024 * 1024  # 500 MB
    if vec_file_bytes > MMAP_THRESHOLD:
        print(f"  vectors.npy is {vec_file_bytes / (1024**3):.1f} GB — using memory-mapped I/O")
        vectors = np.load(str(vectors_path), mmap_mode="r")
    else:
        vectors = np.load(str(vectors_path))

    if vectors.shape[0] != len(chunks):
        print(
            f"  ERROR: Chunk/vector count mismatch — "
            f"{len(chunks)} chunks vs {vectors.shape[0]} vectors.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load manifest (optional but expected)
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8-sig") as f:
            manifest = json.load(f)

    # Load skip manifest (optional)
    skip_manifest = None
    if skip_manifest_path.exists():
        with open(skip_manifest_path, encoding="utf-8-sig") as f:
            skip_manifest = json.load(f)

    return chunks, vectors, manifest, skip_manifest


def print_export_summary(
    export_dir: Path,
    chunks: list[dict],
    vectors: np.ndarray,
    manifest: dict,
    skip_manifest: dict | None,
) -> None:
    """Print details about the export being imported."""
    print(f"  Source:     {export_dir}")
    print(f"  Chunks:     {len(chunks):,}")
    print(f"  Vectors:    {vectors.shape[0]:,} x {vectors.shape[1]}d")
    if manifest:
        print(f"  Model:      {manifest.get('embedding_model', 'unknown')}")
        print(f"  Created:    {manifest.get('timestamp', 'unknown')}")
        if "corpus_name" in manifest:
            print(f"  Corpus:     {manifest['corpus_name']}")

    # Unique source files in the export
    source_files = {c.get("source_path", "") for c in chunks}
    source_files.discard("")
    if source_files:
        print(f"  Files:      {len(source_files):,} unique source documents")

    # Skip manifest summary
    if skip_manifest:
        skipped = skip_manifest.get("skipped_files", [])
        count = len(skipped) if isinstance(skipped, list) else skip_manifest.get("count", 0)
        print(f"  Skipped:    {count} files were skipped during corpus processing")
        print(f"              -- see skip_manifest.json for details")


def run_dry_run(
    export_dir: Path,
    chunks: list[dict],
    vectors: np.ndarray,
    manifest: dict,
    skip_manifest: dict | None,
    config_path: str,
) -> None:
    """Show what would be imported without touching the store."""
    config = load_config(config_path)

    print(DIVIDER)
    print("  HybridRAG V2 -- Import (DRY RUN)")
    print(DIVIDER)
    print_export_summary(export_dir, chunks, vectors, manifest, skip_manifest)
    print()
    print(f"  Target DB:  {config.paths.lance_db}")
    print(f"  Would insert up to {len(chunks):,} chunks (duplicates auto-skipped)")
    print(DIVIDER)
    print("  Dry run complete. No data was written.")
    print(DIVIDER)


def run_import(
    export_dir: Path,
    chunks: list[dict],
    vectors: np.ndarray,
    manifest: dict,
    skip_manifest: dict | None,
    config_path: str,
    create_index: bool,
) -> None:
    """Execute the full import into LanceDB."""
    config = load_config(config_path)

    print(DIVIDER)
    print("  HybridRAG V2 -- Import CorpusForge Export")
    print(DIVIDER)
    print_export_summary(export_dir, chunks, vectors, manifest, skip_manifest)
    print()

    # Enable store-level progress logging so batch inserts print progress
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )

    # Ingest
    t_start = time.perf_counter()

    store = LanceStore(config.paths.lance_db)
    before_count = store.count()
    print(f"  Inserting {len(chunks):,} chunks in batches of {store.INGEST_BATCH_SIZE:,} ...")
    inserted = store.ingest_chunks(chunks, vectors)
    t_ingest = time.perf_counter() - t_start

    # FTS index
    t_fts_start = time.perf_counter()
    store.create_fts_index()
    t_fts = time.perf_counter() - t_fts_start

    # Optional vector index
    t_idx = 0.0
    if create_index:
        t_idx_start = time.perf_counter()
        store.create_vector_index()
        t_idx = time.perf_counter() - t_idx_start

    after_count = store.count()
    store.close()

    t_total = time.perf_counter() - t_start
    duplicates = len(chunks) - inserted

    # Stats
    print(f"  Target DB:  {config.paths.lance_db}")
    print(f"  Before:     {before_count:,} chunks in store")
    print(f"  Inserted:   {inserted:,} new chunks")
    if duplicates > 0:
        print(f"  Duplicates: {duplicates:,} skipped (already in store)")
    print(f"  After:      {after_count:,} chunks in store")
    print()
    print(f"  Timing:")
    print(f"    Ingest:       {t_ingest:6.2f}s")
    print(f"    FTS index:    {t_fts:6.2f}s")
    if create_index:
        print(f"    Vector index: {t_idx:6.2f}s")
    print(f"    Total:        {t_total:6.2f}s")
    if inserted > 0 and t_ingest > 0:
        rate = inserted / t_ingest
        print(f"    Rate:         {rate:,.0f} chunks/sec")

    print(DIVIDER)
    print("  Import complete.")
    print(DIVIDER)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import CorpusForge export into HybridRAG V2 LanceDB store."
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Path to CorpusForge export directory (contains chunks.jsonl + vectors.npy).",
    )
    # Keep --export-dir as hidden alias for backwards compatibility
    parser.add_argument(
        "--export-dir",
        dest="source",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to V2 config YAML (default: config/config.yaml).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without writing to the store.",
    )
    parser.add_argument(
        "--create-index",
        action="store_true",
        help="Build LanceDB IVF_PQ vector index after import (recommended for >10K chunks).",
    )
    args = parser.parse_args()

    export_dir = Path(args.source)
    export_dir = resolve_export_dir(export_dir)

    if not export_dir.is_dir():
        print(f"  ERROR: Export directory not found: {export_dir}", file=sys.stderr)
        sys.exit(1)

    # Load export data
    chunks, vectors, manifest, skip_manifest = load_export(export_dir)

    if args.dry_run:
        run_dry_run(export_dir, chunks, vectors, manifest, skip_manifest, args.config)
    else:
        run_import(
            export_dir, chunks, vectors, manifest, skip_manifest,
            args.config, args.create_index,
        )


if __name__ == "__main__":
    main()
