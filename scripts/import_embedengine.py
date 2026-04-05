"""
Import CorpusForge export into V2 stores.

Reads chunks.jsonl + vectors.npy from a CorpusForge export directory
and loads them into the vector store (FAISS + SQLite FTS5).

Usage:
  python scripts/import_embedengine.py --export-dir path/to/export
  python scripts/import_embedengine.py --export-dir C:/CorpusForge/data/output/latest
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.schema import load_config
from src.store.lance_store import LanceStore


def load_export(export_dir: Path) -> tuple[list[dict], np.ndarray, dict]:
    """Load chunks, vectors, and manifest from a CorpusForge export."""
    # If export_dir is a symlink or text file pointing to real dir
    if export_dir.is_file():
        real_path = export_dir.read_text(encoding="utf-8-sig").strip()
        export_dir = Path(real_path)

    chunks_path = export_dir / "chunks.jsonl"
    vectors_path = export_dir / "vectors.npy"
    manifest_path = export_dir / "manifest.json"

    if not chunks_path.exists():
        print(f"Error: {chunks_path} not found.", file=sys.stderr)
        sys.exit(1)

    # Load chunks
    chunks = []
    with open(chunks_path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    # Load vectors
    vectors = np.load(str(vectors_path))

    # Load manifest
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8-sig") as f:
            manifest = json.load(f)

    return chunks, vectors, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CorpusForge export into V2")
    parser.add_argument(
        "--export-dir",
        required=True,
        help="Path to CorpusForge export directory (or 'latest' symlink).",
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to V2 config YAML.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    export_dir = Path(args.export_dir)

    print("=" * 50)
    print("  HybridRAG V2 — Import CorpusForge Export")
    print("=" * 50)

    # Load export
    chunks, vectors, manifest = load_export(export_dir)
    print(f"  Export:   {export_dir}")
    print(f"  Chunks:   {len(chunks)}")
    print(f"  Vectors:  {vectors.shape}")
    if manifest:
        print(f"  Model:    {manifest.get('embedding_model', 'unknown')}")
        print(f"  Created:  {manifest.get('timestamp', 'unknown')}")

    # Import into store
    store = LanceStore(config.paths.lance_db)
    inserted = store.ingest_chunks(chunks, vectors)
    store.create_fts_index()
    total = store.count()
    store.close()

    print(f"  Inserted: {inserted} new chunks")
    print(f"  Total:    {total} chunks in store")
    print("=" * 50)
    print("  Import complete.")
    print("=" * 50)


if __name__ == "__main__":
    main()
