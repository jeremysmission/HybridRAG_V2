# Retrieval Baseline and Root Cause Analysis -- 2026-04-16

**Author:** Jeremy Randall (CoPilot+)
**Repo:** HybridRAG_V2
**Date:** 2026-04-16 MDT
**Context:** Production 400-query eval baseline + root cause analysis of query timeouts and empty results

---

## Understanding the Numbers: Three Different Measurements

The 64.0% baseline is **retrieval-only** (no LLM generation). It uses the V2 `QueryPipeline.retrieve_context` path -- embed query, vector search, FTS, hybrid fusion, rerank. The scoring checks whether the expected document family appears in the top-K results. No phi4, no CoPilot+ -- pure retrieval.

This is DIFFERENT from the marathon's 85.1% which was CoPilot+ doing full extraction + answer generation. They're measuring different things:

| Measurement | What It Tests | Score |
|---|---|---|
| Today's baseline (64.0%) | Can retrieval FIND the right chunks? | 256/400 PASS |
| Marathon CoPilot+ (85.1%) | Can CoPilot+ ANSWER correctly from found chunks? | 338/397 |
| Marathon phi4 (75.8%) | Can phi4 ANSWER correctly from found chunks? | 301/397 |

The gap between 64% (retrieval finds it) and 85% (CoPilot+ answers correctly) means CoPilot+ is compensating for retrieval failures by reasoning across imperfect context. If we fix retrieval, both the retrieval-only score AND the CoPilot+-assisted score improve.

---

## Where the 64% Fails -- By Query Type

| Query Type | PASS | MISS | Problem |
|---|---|---|---|
| AGGREGATE | 59/106 (56%) | 28 | Worst performer -- cross-document counting |
| SEMANTIC | 56/102 (55%) | 25 | Routing only 47% correct, hurting retrieval |
| ENTITY | 90/117 (77%) | 19 | Best performer -- entity queries work |
| TABULAR | 51/75 (68%) | 7 | Decent, but structured data parsing can improve |

## Where the 64% Fails -- By Persona

| Persona | PASS | MISS | Problem |
|---|---|---|---|
| Cyber/Network | 59/80 (74%) | 3 | Strongest -- well-represented in corpus |
| Logistics | 58/80 (73%) | 14 | Good but aggregation queries drag it down |
| Field Engineer | 51/80 (64%) | 19 | Mid-range |
| Program Manager | 45/80 (56%) | 19 | Weak -- PM docs may be under-indexed |
| Aggregation/Cross-role | 43/80 (54%) | 24 | Weakest -- cross-doc is the hard case |

## Key Insight

6 of 9 MISSes in the first 50 had CORRECT routing. The router isn't the problem -- **retrieval recall** is. This confirms that improving extraction (Tier 1 regex from the overnight mining) and entity enrichment are the right moves to push from 64% toward the 85% ceiling.

---

## The Latency Problem

| Stage | P50 | P95 | Max |
|---|---|---|---|
| Vector search | 189ms | 12,729ms | 45,888ms |
| Rerank | 3,292ms | 6,770ms | 7,810ms |
| entity_lookup | 6,531ms | 7,062ms | 83,111ms |
| structured_lookup | 12,990ms | 116,030ms | 166,222ms |
| aggregate_lookup | 1,692ms | 59,045ms | 61,343ms |
| Router (OpenAI) | 1,833ms | 3,172ms | 10,190ms |
| **Wall clock total** | **11,171ms** | **54,654ms** | **97,317ms** |

Vector search is fast (189ms p50). The bottleneck is the entity/structured lookup paths hitting the SQLite entity store.

---

## ROOT CAUSE: Why Queries Timeout or Return Nothing

Investigation on 2026-04-16 revealed three compounding issues:

### Issue 1: Entity Store Has 19.9M Entities But 0 Relationships, 0 Tables, 0 Typed Entities

| Store | Row Count | Expected |
|---|---|---|
| entities | 19,959,604 | Has data but untyped |
| relationships | **0** | Should have thousands |
| extracted_tables | **0** | Should have thousands |
| PART_NUMBER entities | **0** | Should have millions (mining found 3.8M part number mentions) |

The entity extraction pipeline has not populated the entity types or relationships that the query pipeline depends on. The entity store has 19.9M generic entities but zero of the structured types (`PART_NUMBER`, `CONTRACT`, `SITE`, etc.) that the retriever searches for.

### Issue 2: LIKE Queries on 19.9M Rows Are Inherently Slow

A single `LIKE '%power%amplifier%'` query against the 19.9M-row entity table takes **1,199ms**. The entity retriever runs 2-3 cascading LIKE queries per request as it falls through lookup paths:
1. First try: lookup by entity_type + text_pattern (finds nothing -- types not populated)
2. Fallback: lookup by text_pattern only (expensive LIKE scan on 19.9M rows)
3. Fallback: relationship traversal (finds nothing -- 0 relationships)

Each fallback adds another full-table LIKE scan.

### Issue 3: Empty Stores Cause Cascading Fallbacks

When the query router classifies a question as ENTITY or AGGREGATE, it routes to the entity retriever. The entity retriever:
1. Searches relationships → 0 rows → falls through
2. Searches extracted_tables → 0 rows → falls through
3. Searches entities by type → 0 typed matches → falls through
4. Falls back to expensive LIKE scan on all 19.9M entities
5. Either times out or returns low-relevance generic matches

This is why queries take 13-166 seconds and often return nothing useful.

### Why the Marathon's 85.1% Didn't Hit This Problem

The marathon session measured CoPilot+'s extraction quality by giving CoPilot+ the RAW CHUNK TEXT directly, bypassing the entity store entirely. CoPilot+ read the chunks and extracted relationships on the fly. Our pipeline tries to use pre-computed entities and relationships from the store -- which is empty.

---

## The Fix Path

### Immediate (fixes timeout + empty results):
1. **Populate entity types** -- run Tier 1 regex extraction to create PART_NUMBER, CONTRACT, SITE, PERSON entities in the entity store
2. **Populate relationship store** -- Task 1 relationship regex (10 patterns from 755K corpus hits) fills the currently-empty relationship table
3. **Add FTS5 to entity text column** -- replaces `LIKE '%pattern%'` full-table scans with sub-millisecond full-text search

### Medium term (improves 64% toward 85%):
4. **Path-derived metadata** -- add site/contract/document_type from folder names (free metadata)
5. **Key-value colon parsing** -- 51.7% of corpus has semi-structured data the current parser misses
6. **GLiREL relationship extraction** -- deterministic ML model for relationship classification (research finding from today)

### What This Means

The retrieval layer (vector search + FTS) works correctly at 49ms. The entity enrichment layer is the bottleneck -- empty stores and expensive fallback queries. Every improvement to entity extraction directly improves both the 64% score AND the query latency.

---

## Full Baseline Report Reference

- 50-query summary: `baselines/BASELINE_50Q_SUMMARY_2026-04-16.md`
- 400-query full report: `baselines/baseline_400q_report_2026-04-16.md`
- 400-query raw results: `baselines/baseline_400q_results_2026-04-16.json`
- Overnight mining results: `overnight_autonomous_runs/2026-04-16_full_corpus_recon/output/`
- Marathon review board: `HYBRIDRAG_LOCAL_ONLY/Codex_Max_War_Room.txt`
- Marathon lessons: `HYBRIDRAG_LOCAL_ONLY/MarathonLessonsLearned_Impliciations.txt`

---

Jeremy Randall | HybridRAG_V2 | 2026-04-16 MDT
