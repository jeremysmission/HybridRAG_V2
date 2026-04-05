# Sprint 6 Game Plan — Scale + Prove

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-05 MDT
**Pre-req:** Sprint 5 QA passed

---

## Goal

Push 5,000+ files through CorpusForge → V2, prove golden eval on real data, deploy to work machine.

---

## Research Findings (informing this plan)

### LanceDB at Scale
- IVF_PQ index: `num_partitions = sqrt(N)` (~1000 for 1M vectors), PQ 64-96 sub-vectors for 768-dim
- `nprobes` start at 10-20, tune for recall@10
- Compact fragments after bulk insert: `compact_files()` + `cleanup_old_versions()`
- Pre-sort data by semantic similarity before insertion improves locality

### Dedup Strategy
- **MinHash with LSH banding** beats SimHash for format-converted docs (DOCX→PDF)
- Word-level 5-gram shingles, 128-256 hash functions
- LSH: 20 bands x 5 rows for ~0.8 Jaccard threshold
- `datasketch` library — runs 187K files in minutes on single machine
- SimHash too sensitive to whitespace/header changes from format conversion

### Golden Eval at Scale
- 400 queries = 95% CI within +/-3% on NDCG — statistically solid
- Stratify by: query type, source doc type, difficulty tier (30+ per stratum)
- NDCG@10 primary, MAP + Recall@K secondary
- Report per-stratum breakdowns, not just aggregate
- Consider Ragas for automated RAG-specific metrics (faithfulness, relevance)

### Production Ingestion
- 500-2000 files per batch (throughput vs error isolation)
- Checkpoint/resume via manifest (file hash + status + timestamp)
- Process-per-file error isolation, dead-letter queue for failures
- Content-hash for idempotency and natural dedup

### Work Machine Deployment
- `pip download -r requirements.txt -d ./wheels` on Beast → offline install at work
- Zip `~/.ollama/models` to transfer phi4 without re-download
- Match Python minor version exactly
- Blackwell needs CUDA 12.8+ and matching torch build
- Deployment verification script: imports, CUDA, endpoints, config paths, single ingest+query cycle

---

## Slices

| Slice | Work | Depends on | Parallel? |
|-------|------|------------|-----------|
| 6.1 | CorpusForge scale run: 5K files on GPU 0, batch 500-2K, checkpoint/resume | Sprint 5 | |
| 6.2 | CorpusForge Clone on GPU 1: 2x throughput, split source dirs, merge exports | 6.1 proven | With 6.3+ |
| 6.3 | Import scale exports into V2 LanceDB (batch 1000, mmap vectors) | 6.1 | |
| 6.4 | Build IVF_PQ index on LanceDB: sqrt(N) partitions, nprobes=20, compact | 6.3 | |
| 6.5 | Entity extraction at scale: phi4 or GPT-4o-mini per Sprint 5C decision | 6.3 | With 6.4 |
| 6.6 | MinHash dedup pipeline: datasketch, 5-gram shingles, LSH banding | Sprint 5D | With 6.1 |
| 6.7 | Golden eval on real data: 400-query set, NDCG@10, per-stratum breakdown | 6.5 | |
| 6.8 | Contextual enrichment test: phi4 preambles on 500 chunks, measure retrieval delta | 6.3 | With 6.7 |
| 6.9 | Benchmark: full pipeline throughput report (per-stage timing, chunks/sec) | 6.1 | |
| 6.10 | Package wheels for work machine: pip download, zip ollama models | Sprint 5 | Anytime |
| 6.11 | Deploy to work machine: offline install, verify_deploy.py, single ingest+query | 6.10 | |
| 6.12 | Performance tuning: batch sizes, nprobes, embed batch, SQLite PRAGMAs | 6.7 | |

---

## Exit Criteria

1. 5,000+ files processed through CorpusForge without crash
2. V2 LanceDB has IVF_PQ index, compact, searchable
3. 15/25 golden queries pass on real data (NDCG@10 reported)
4. P50 latency measured and documented
5. Dedup reduces chunk count by measurable % vs raw
6. Work machine runs both repos from deployment guide alone
7. Throughput benchmark: sustained >30 chunks/sec on Beast

## QA Checklist (for QA team)

- [ ] 5K+ files ingested, export size and chunk count reported
- [ ] LanceDB vector count matches chunk count after import
- [ ] IVF_PQ index created, search latency < raw scan
- [ ] Entity extraction: types, counts, confidence distribution
- [ ] Golden eval: 15/25 minimum, per-query breakdown, per-stratum report
- [ ] Dedup: before/after chunk count, % reduction
- [ ] Benchmark: per-stage timing table, sustained chunks/sec
- [ ] Work machine: verify_deploy.py passes all checks
- [ ] Work machine: single query returns answer with citations

---

## Risks

| Risk | Mitigation |
|------|------------|
| LanceDB OOM on bulk insert | Batch inserts (1000/batch), mmap vectors — already implemented |
| Parser crashes on edge-case files | Per-file error isolation, dead-letter queue, stale future watchdog |
| phi4 extraction quality insufficient | Sprint 5C decision gate; fallback to GPT-4o-mini API |
| Work machine CUDA driver mismatch | Verify nvidia-smi + torch.cuda before starting; document Blackwell torch build |
| Golden eval too optimistic | Stratify queries, include adversarial tier, report per-stratum not just aggregate |

---

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
