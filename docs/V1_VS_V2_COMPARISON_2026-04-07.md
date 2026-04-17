# V1 vs V2 Comparison Report

> WARNING: Historical comparison only. This file contains stale store counts and early capability framing, and is unsafe for current demo/operator narration.
> Start instead with `docs/MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md` and `docs/V2_DEMO_READINESS_GAP_ANALYSIS_2026-04-12.md`.

**Date:** 2026-04-07 MDT
**Author:** Jeremy Randall (CoPilot+)

---

## Architecture Comparison

| Feature | V1 (HybridRAG3) | V2 (HybridRAG_V2) |
|---------|-----------------|-------------------|
| Vector store | LanceDB | LanceDB (same) |
| Entity store | None | SQLite (40,981 entities) |
| Relationship store | None | SQLite (4,683 relationships) |
| Table store | None | SQLite (3,397 extracted tables) |
| Query router | Keyword heuristics | GPT-4o structured outputs + rule-based fallback |
| Reranker | None | FlashRank (ms-marco-MiniLM-L-12-v2) |
| Embedding model | all-MiniLM-L6-v2 (384d) | nomic-embed-text-v1.5 (768d, CUDA) |
| Chunk source | Direct file parsing | CorpusForge pipeline (parse+chunk+embed+export) |
| Dedup strategy | File hash only | File hash + document-level near-duplicate |
| Enrichment | None | phi4:14b contextual preambles |
| Entity extraction | None | GLiNER + phi4 overnight extraction |

## Query Type Coverage

| Query Type | V1 | V2 |
|------------|-----|-----|
| SEMANTIC (narrative) | Yes (vector only) | Yes (vector + reranker + FTS) |
| ENTITY (who/what lookup) | No | Yes (entity store direct lookup) |
| AGGREGATE (count/list) | No | Yes (entity aggregation across docs) |
| TABULAR (PO/spreadsheet) | No | Yes (extracted table row query) |
| COMPLEX (multi-hop) | No | Yes (sub-query decomposition) |

## Golden Eval Results (25 queries)

| Metric | V1 (estimated) | V2 (measured) |
|--------|----------------|---------------|
| Retrieval accuracy | ~15/25 (60%) | 25/25 (100%) |
| Entity queries | 0/5 | 5/5 |
| Aggregate queries | 0/5 | 5/5 |
| Tabular queries | 0/3 | 3/3 |
| Semantic queries | ~15/17 | 17/17 |

V1 could only answer semantic queries via vector search. V2's tri-store architecture handles all 5 query types.

## Performance

| Metric | V1 | V2 |
|--------|-----|-----|
| P50 latency (retrieval) | ~200ms | 20ms |
| P95 latency (retrieval) | ~500ms | 57ms |
| Embedding dimension | 384 | 768 |
| Embedding device | CPU/ONNX | CUDA (NVIDIA workstation GPU) |
| Chunk count | ~6.9M (bloated) | 17,707 (deduped canonical) |
| Index size | ~170 GB | ~79 MB |

## Key V2 Improvements

1. **Structured queries** -- entity/aggregate/tabular queries bypass vector dilution
2. **Document-level dedup** -- 170 GB -> 79 MB index via canonical source list
3. **CUDA embedding** -- 10-45x faster than CPU/ONNX
4. **Reranker** -- FlashRank improves precision in top-k results
5. **Enrichment** -- phi4 contextual preambles improve retrieval recall
6. **Quality gates** -- min confidence 0.7 on entities, schema validation on import

---

Jeremy Randall | HybridRAG_V2 | 2026-04-07 MDT
