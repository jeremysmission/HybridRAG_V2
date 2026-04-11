# How To Import a CorpusForge Export Into V2 LanceDB

**Date:** 2026-04-11
**Author:** Jeremy Randall (CoPilot+)

---

## What This Does

Takes a CorpusForge export directory (containing `chunks.jsonl` + `vectors.npy` + `manifest.json`) and loads it into HybridRAG V2's LanceDB vector store so you can query against it.

## Prerequisites

- HybridRAG V2 repo with working `.venv`
- A CorpusForge export directory (produced by the Forge pipeline)
- Enough disk space for the LanceDB store (~1.5-2x the vectors.npy size)

## The Export Directory Structure

A CorpusForge export looks like this:

```
export_YYYYMMDD_HHMM/
  chunks.jsonl        # One JSON object per line, each chunk has chunk_id, text, source_path
  vectors.npy         # numpy float16 array, shape (N, 768), one row per chunk
  manifest.json       # Metadata: chunk_count, vector_dim, embedding_model, stats
  entities.jsonl      # Entity extraction output (may be empty if extraction wasn't run)
  skip_manifest.json  # What was skipped/deferred during the Forge run
  run_report.txt      # Human-readable run summary
```

The critical alignment rule: **chunks.jsonl line count must equal vectors.npy row count**. If they don't match, the import will fail or produce corrupt results.

## Step-by-Step Import

### 1. Dry run first (always)

```bash
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts/import_embedengine.py \
  --source "E:/CorpusIndexEmbeddingsOnly/export_20260411_0720" \
  --dry-run
```

This loads and validates the export without writing anything. Check:
- chunk count matches vector rows
- manifest validation passes
- no rejected chunks

### 2. Backup the current store (if one exists)

```bash
# Rename the existing LanceDB folder
mv data/index/lancedb data/index/lancedb_backup_YYYYMMDD
mkdir -p data/index/lancedb
```

### 3. Run the import

```bash
.venv\Scripts\python.exe scripts/import_embedengine.py \
  --source "E:/CorpusIndexEmbeddingsOnly/export_20260411_0720" \
  --create-index
```

Flags:
- `--source` — path to the CorpusForge export directory (REQUIRED)
- `--create-index` — builds IVF_PQ vector index + FTS index after import (recommended for large stores)
- `--dry-run` — validate only, don't write
- `--exclude-source-glob "*.SAO.zip"` — optional safety filter for known junk patterns

### 4. Verify the import

After import completes, check:
- The script prints `inserted: N` matching your chunk count
- `data/index/lancedb/chunks.lance/` exists and has data
- Run a quick health check:

```bash
.venv\Scripts\python.exe -c "
from src.store.lance_store import LanceStore
store = LanceStore('data/index/lancedb')
print(f'Chunks in store: {store.count():,}')
"
```

## Time Estimates

| Corpus Size | Import Time | Index Build | Total |
|------------|-------------|-------------|-------|
| 242,650 chunks (Run 6) | ~13s | ~59s | ~72s |
| 10,435,593 chunks (full) | ~9 min | ~15-30 min | ~25-40 min |

Import speed is ~19,000 chunks/sec. The IVF_PQ index build is the slower part on large stores.

## What the Import Script Does Internally

1. **Loads** `chunks.jsonl` line by line into a list of dicts
2. **Loads** `vectors.npy` via numpy (memory-mapped for files >500MB)
3. **Validates** manifest (schema version, vector dim, chunk count cross-check)
4. **Validates** each chunk has required fields (chunk_id, text, source_path)
5. **Inserts** into LanceDB in batches of 1000 chunks with progress logging
6. **Builds FTS index** (BM25 full-text search on text + enriched_text columns)
7. **Builds IVF_PQ index** (approximate nearest neighbor for vector search) if `--create-index`
8. **Writes** import report JSON artifact

## After Import: What You Can Do

- **Run tiered extraction:** `scripts/tiered_extract.py --tier 1` (regex, instant)
- **Query the store:** start the API server or use the GUI
- **Run golden eval:** `scripts/run_golden_eval.py`
- **Check retrieval:** query specific terms and inspect returned chunks

## Common Issues

- **"vectors.npy has N rows but chunks.jsonl has M lines"** — the export is corrupt or was interrupted. Re-export from Forge.
- **Out of memory on large imports** — vectors >500MB are auto-memory-mapped. If still OOM, reduce batch size in the script.
- **Slow index build** — IVF_PQ on 10M+ chunks takes 15-30 min. This is normal. Don't kill it.
- **KMeans empty cluster warnings** — noise chunks (image metadata, junk) cause sparse clusters. Harmless but indicates the corpus needs skip/defer cleanup.

---

Jeremy Randall | HybridRAG_V2 | 2026-04-11 MDT
