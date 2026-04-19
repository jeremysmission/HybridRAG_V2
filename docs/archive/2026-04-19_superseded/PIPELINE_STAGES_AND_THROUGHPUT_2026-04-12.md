# HybridRAG V2 + CorpusForge — Pipeline Stages and Throughput Guide

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-12 MDT

Supersedes: `PIPELINE_STAGES_AND_THROUGHPUT_2026-04-05.md`

---

## The Three Pipeline Stages

Data flows through three distinct stages. Each has different bottlenecks, parallelism options, and tools.

### Stage 1: CorpusForge — Parse + Chunk + Embed

**What:** Raw files (PDF, DOCX, XLSX, etc.) → parsed text → chunks → vector embeddings → export package
**Where:** C:\CorpusForge
**Launcher:** `start_corpusforge.bat` (GUI) or `scripts/run_pipeline.py` (CLI)

| Sub-stage | Tool | Parallelism | Bottleneck | Speed |
|-----------|------|-------------|------------|-------|
| Parse files | 27 parsers via dispatcher | **8 workers (ThreadPoolExecutor)** | CPU/I/O, OCR | 38 files/sec |
| Chunk text | Chunker (1200 char, 200 overlap) | Single-threaded (instant) | None | 700K chunks/sec |
| Enrich (optional) | phi4:14b via Ollama | Single-stream | LLM generation | ~3 chunks/min |
| Embed vectors | sentence-transformers CUDA | **GPU batch (token-budget)** | GPU VRAM | 60-200 chunks/sec |
| Export | Packager (chunks.jsonl + vectors.npy) | Single-threaded | Disk I/O | Fast |

**Key rules:**
- CUDA-only embedding. CPU/Ollama HTTP fallback is 45x slower. Verify with `scripts/verify_cuda_embedding.py`.
- 8 parallel parser workers keep the GPU fed. Without them, GPU sits idle between files.
- Enrichment (phi4 context preambles) is optional and slow — disable for bulk runs, enable for quality.
- OOM backoff: if GPU runs out of memory, batch size halves automatically and retries.

**GPU assignment on the local development workstation:** keep one heavy workload per visible CUDA device, and treat any parallel local run as an experiment rather than a production assumption.

---

### Stage 2: V2 Import — CorpusForge Export → LanceDB

**What:** Takes CorpusForge export (chunks.jsonl + vectors.npy) and loads into V2's LanceDB vector store.
**Where:** C:\HybridRAG_V2
**Script:** `python scripts/import_embedengine.py --source <export_dir>`

| Sub-stage | Tool | Speed |
|-----------|------|-------|
| Load chunks | JSON lines reader | Fast |
| Load vectors | numpy mmap (>500MB) or load | Fast |
| Insert to LanceDB | Batch 1000 chunks at a time | ~10K chunks/sec |
| Build FTS index | LanceDB BM25 | Seconds |
| Build vector index | IVF_PQ (Sprint 6) | Minutes |

**Key rules:**
- `--source` is REQUIRED — points to CorpusForge export directory, not raw source files.
- Large vector files (>500MB) are memory-mapped automatically — won't OOM.
- Batch inserts with per-batch progress logging.
- Run `--dry-run` first to verify counts before inserting.

**No GPU needed** for this stage — it's pure I/O.

---

### Stage 3: Entity Extraction — Chunks → Entities + Relationships

**What:** Takes chunks from the V2 LanceDB store for the canonical pipeline, or from a Clone1 SQLite index for dev/test-only local experiments, and extracts structured entities.
**Where:** C:\HybridRAG_V2
**Scripts:**
- `scripts/extract_entities.py` — production extraction from V2 LanceDB chunks
- `scripts/overnight_extraction.py` — Clone1 / phi4 dev-test extraction, not the canonical V2 LanceStore path
- `scripts/ab_extraction_test.py` — Clone1 quality comparison (phi4 vs GPT-4o), not the canonical V2 LanceStore path
**Launcher:** `start_overnight_extraction.bat` (Clone1 / phi4 one-click overnight, not V2 tiered extraction)

| Method | Parallelism | Speed | Cost | Use case |
|--------|-------------|-------|------|----------|
| phi4 via Ollama (primary workstation) | Single-stream per GPU | **2.6 chunks/min** | $0 | Dev/test data overnight |
| phi4 via SGLang (primary workstation) | Continuous batching | ~10-20 chunks/min (est.) | $0 | Fast dev data (Sprint 6) |
| Parallel local Ollama (experimental) | Split local streams | ~5 chunks/min | $0 | Local experimentation only |
| GPT-4.1 Nano batch API | Massively parallel | 100+ chunks/min | ~$10-30 | Production at work |
| GPT-4o-mini batch API | Massively parallel | 100+ chunks/min | ~$50-100 | Production fallback |

**Tiered extraction (recommended for production):**

| Tier | Tool | What it finds | Speed | Cost |
|------|------|---------------|-------|------|
| 1 | Regex | Part numbers, emails, phones, dates, POs | Instant | $0 |
| 2 | GLiNER on GPU (waiver pending) | People, orgs, sites | 2,400-7,500/sec | $0 |
| 3 | phi4 local OR GPT-4.1 Nano batch | Relationships, complex entities | 2.6/min or 100+/min | $0 or $10-30 |
| 4 | GPT-4o (demo only) | Edge cases needing frontier reasoning | N/A | Expensive |

**Key rules:**
- Regex + GLiNER handle 60-80% of entities for free. LLM only for hard cases.
- Ollama is single-stream — parallel workers DON'T help. Need SGLang or API for parallelism.
- GPT-4o is for user-facing queries ONLY. Never use for bulk extraction.
- Progress saves every 10 chunks. Safe to Ctrl+C and resume with `--resume`.
- Overnight on primary workstation: ~2000 chunks = ~13 hours = ~10,000+ entities by morning.

**Local experimentation note:** if you intentionally run a second local extraction process, keep it isolated and give it a separate Ollama port.

---

## Throughput Summary (Local Development Workstation)

| Operation | Tool | Speed | GPU |
|-----------|------|-------|-----|
| File parsing | 8 workers | 38 files/sec | CPU |
| Chunking | Python string ops | 700K chunks/sec | CPU |
| Embedding | sentence-transformers CUDA | 60-200 chunks/sec | Yes |
| Entity extraction (Ollama) | phi4:14b single-stream | 2.6 chunks/min | Yes |
| Entity extraction (SGLang) | phi4:14b batched | ~10-20 chunks/min (est.) | Yes |
| Entity extraction (API) | GPT-4.1 Nano batch | 100+ chunks/min | No (cloud) |
| GLiNER NER | 500M model | 2,400-7,500 chunks/sec | Optional |
| LanceDB insert | Batch 1000 | ~10K chunks/sec | No |

---

## Corpus Size After Dedup (Clone1 Analysis)

| Metric | Count |
|--------|-------|
| Clone1 total chunks | 27,607,262 |
| Unique chunk hashes | 89,305 |
| Duplicate rate | 99.7% |
| Unique source files | 187,204 |
| Source drive size | ~366 GB (5 role folders) |
| After skip list (CAD/binary) | ~50% reduction |
| **Estimated unique chunks for V2** | **89K-300K** |

**Implication:** With proper dedup, the "millions of chunks" problem becomes "hundreds of thousands" — extraction is hours not months.

---

## Cost Reference

| Method | 300K chunks | Budget OK? |
|--------|-------------|------------|
| phi4 local (primary workstation) | $0 (electricity ~$75) | Yes |
| Tiered (regex+GLiNER+Nano) | $10-30 | Yes |
| GPT-4.1 Nano batch only | ~$35 | Yes |
| GPT-4o-mini batch only | ~$56 | Borderline |
| GPT-4o (NEVER for bulk) | ~$1,875 | NO |

**Budget rule:** Under $50 = no issues. $50-100 = needs justification. Over $100 = problematic.

See: `docs/TOKEN_PRICING_REFERENCE_2026-04-05.md` for full pricing table.

---

## Quick Reference Commands

```bash
# CorpusForge: process source files
cd C:\CorpusForge
start_corpusforge.bat                    # GUI
.venv\Scripts\python scripts/run_pipeline.py --source data/source  # CLI

# V2: import CorpusForge export
cd C:\HybridRAG_V2
.venv\Scripts\python scripts/import_embedengine.py --source <export_dir>

# V2: canonical tiered extraction from LanceDB
.venv\Scripts\python scripts/tiered_extract.py --tier 1
.venv\Scripts\python scripts/tiered_extract.py --tier 2

# Clone1 / phi4 dev-test overnight extraction (not canonical V2)
start_overnight_extraction.bat           # default 2000 chunks
start_overnight_extraction.bat 5000      # more chunks
start_overnight_extraction.bat resume    # pick up where stopped
start_overnight_extraction.bat status    # check progress

# Clone1 dev-test: A/B quality test
.venv\Scripts\python scripts/ab_extraction_test.py --sample-size 50

# V2: query (after data is loaded)
start_gui.bat                            # GUI
.venv\Scripts\python -m uvicorn src.api.server:app  # API
```

---

Jeremy Randall | HybridRAG_V2 | 2026-04-12 MDT
