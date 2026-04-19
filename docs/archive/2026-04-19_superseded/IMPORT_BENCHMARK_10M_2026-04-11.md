# Import Benchmark — 10.4M Chunks Into LanceDB

**Date:** 2026-04-11
**Author:** Jeremy Randall (CoPilot+)

---

## Corpus Details

| Metric | Value |
|--------|-------|
| Source | CorpusForge overnight export (E:\CorpusIndexEmbeddingsOnly\export_20260411_0720) |
| Chunks | 10,435,593 |
| Vector dim | 768 (float16, nomic-embed-text-v1.5) |
| chunks.jsonl | 14.1 GB |
| vectors.npy | 14.9 GB |
| Total export size | ~30 GB |

## Machine

| Component | Spec |
|-----------|------|
| Machine | primary workstation (personal dev workstation) |
| RAM | 64 GB |
| Storage source | USB 3.2 NVMe external SSD (E:) — **this was the bottleneck** |
| Storage target | C: 2TB NVMe (internal) |
| GPU | Not used for import (CPU + I/O only) |

## Timing Breakdown (USB source → NVMe target)

| Phase | Duration | Notes |
|-------|----------|-------|
| Load chunks.jsonl (10.4M JSON lines) | ~60-80 min (est.) | USB read bottleneck — 14.1 GB over USB 3.2 |
| Load vectors.npy (memory-mapped) | ~1 min | numpy mmap, fast regardless of source |
| Validate chunks (required fields check) | ~5-10 min (est.) | 10.4M chunks × 3 field checks |
| Batch inserts into LanceDB | ~60-90 min | ~1000 chunks/batch, 9,680 batches total |
| Build FTS index (BM25) | Included in total | Built during inserts |
| Build IVF_PQ vector index | ~15-30 min (est.) | Still running at time of this note |
| **Total wall clock** | **~2.5-3 hours** | Import started 11:25 AM, still in index build at 2:10 PM |

## Peak Resource Usage

| Resource | Peak | Notes |
|----------|------|-------|
| RAM | 30.2 GB | During chunk loading phase, dropped to ~20 GB during inserts |
| CPU | Sustained heavy single-core | JSON parsing + LanceDB writes |
| Disk written | 42 GB | LanceDB on-disk store (larger than input due to index structures) |

## Expected Timing From NVMe Source (Next Time)

The USB read phase dominated this run. Reading 14.1 GB of JSON from USB 3.2 is ~5-10x slower than NVMe.

A local copy was made during this run to `C:\HybridRAG_V2\data\forge_exports\` (verified byte-identical).

| Phase | USB Source (this run) | NVMe Source (expected) |
|-------|---------------------|----------------------|
| Load chunks.jsonl | ~60-80 min | **~10-15 min** |
| Batch inserts | ~60-90 min | ~60-90 min (same, disk-write bound) |
| IVF_PQ index build | ~15-30 min | ~15-30 min (same, CPU bound) |
| **Total** | **~2.5-3 hours** | **~1.5-2 hours** |

## Comparison With Smaller Imports

| Corpus Size | Import Time | Index Build | Total | Source |
|-------------|------------|-------------|-------|--------|
| 242,650 chunks (Run 6) | ~13 sec | ~59 sec | ~72 sec | reviewer measurement |
| 10,435,593 chunks (full) | ~2+ hours | ~15-30 min | ~2.5-3 hours | This benchmark |

Scaling is roughly linear for inserts but sub-linear for index build (IVF_PQ gets more efficient with larger datasets in relative terms).

## Lessons Learned

1. **Always copy the export to NVMe first.** The USB read phase added 45-70 minutes of unnecessary wall time.
2. **30 GB RAM is needed** for the chunk loading phase. 64 GB machines handle it fine. 32 GB machines would be tight.
3. **The import script should log batch progress.** The current script was silent during the multi-hour run, which made it hard to tell if it was alive or stalled.
4. **IVF_PQ index build is CPU-bound, not GPU.** No benefit from having GPUs available during import.

## Operator Guidance

For the walk-away script (`RUN_IMPORT_AND_EXTRACT.bat`):

- If source is on USB: budget 3 hours for import alone
- If source is on local NVMe: budget 1.5-2 hours for import
- Tier 1+2 extraction adds another 1-4 hours after import
- **Total walk-away time: 3-7 hours depending on source location and GPU speed**

---

Jeremy Randall | HybridRAG_V2 | 2026-04-11 MDT
