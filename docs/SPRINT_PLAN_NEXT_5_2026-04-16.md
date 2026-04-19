# Sprint Plan -- Next 5 Sprints (3 Parallel Lanes)

**Author:** Jeremy Randall (CoPilot+)
**Repo:** HybridRAG_V2
**Date:** 2026-04-16 MDT
**Target:** May 2 demo
**Baseline:** 64.0% retrieval PASS (256/400), production will use GPT-4o for answer generation

---

## Lane Structure

Three parallel lanes that don't step on each other's code:

| Lane | Focus | Code Surfaces | Owner |
|------|-------|---------------|-------|
| **Lane A: Retrieval Quality** | Fix the 64% -> 85% gap | `src/query/`, `src/store/`, `config/` | Coder A + CoPilot+-Researcher |
| **Lane B: Entity Enrichment** | Populate empty stores, extraction pipeline | `src/extraction/`, entity SQLite DB | Coder B + CoPilot+-Researcher |
| **Lane C: Deploy + Demo Prep** | Install scripts, proxy, guides, demo deck | `tools/`, `scripts/`, `docs/`, batch files | QA + Researchers |

No lane touches another lane's code surfaces. All lanes share the eval harness for A/B testing.

---

## Sprint 1 (Current -- in progress)

**Theme:** Baseline + infrastructure hardening
**Status:** ~70% complete

### Lane A: Retrieval Quality
- [x] 400-query production baseline established (64.0% PASS)
- [x] Relevance score bug fixed (`_relevance_score` vs `_distance`)
- [ ] **IN PROGRESS:** Adaptive top-k per query type (ENTITY=10, SEMANTIC=30, AGGREGATE=50)
- [ ] **IN PROGRESS:** NVIDIA workstation GPU reference sanitization (compliance)

### Lane B: Entity Enrichment
- [x] Schema externalized to `config/extraction_schema_v1.yaml` (Option A)
- [x] 10 relationship phrase regex patterns added (755K corpus hits)
- [x] Path-derived metadata extraction (site, contract period, program name)
- [ ] **IN PROGRESS:** FTS5 index on entity store text column (100x speedup)
- [ ] **IN PROGRESS:** Investigate why 0 relationships in entity store

### Lane C: Deploy + Demo Prep
- [x] Proxy-hardened RAGAS install scripts (Megatask 11)
- [x] Waiver sheet Rev C (RAGAS + rapidfuzz + CVE audit)
- [x] User guides upgraded (V2, IQT, Career Moves)
- [x] Button smash harness ported and verified
- [x] CA cert export fix (IQT + Career Moves)
- [ ] **IN PROGRESS:** Entity store health pre-flight check
- [ ] **IN PROGRESS:** NDCG@k metric added

**Sprint 1 Acceptance:** All IN PROGRESS items complete. A/B test adaptive top-k against 64% baseline.

---

## Sprint 2 (Next)

**Theme:** Close the retrieval gap -- target 75%+
**Depends on:** Sprint 1 A/B results

### Lane A: Retrieval Quality
- [ ] Tune adaptive top-k values based on Sprint 1 A/B results
- [ ] Add query decomposition for AGGREGATE type (currently 56% PASS -- worst performer)
- [ ] Improve SEMANTIC routing accuracy (currently 47% correct -- hurting retrieval)
- [ ] A/B test: before/after on 400-query pack
- [ ] Target: 75%+ retrieval PASS rate

### Lane B: Entity Enrichment
- [ ] Populate relationship store from Tier 1 regex extraction (currently 0 rows)
- [ ] Populate extracted_tables from tabular_substrate.py (currently 0 rows)
- [ ] Add PART_NUMBER, CONTRACT, SITE typed entities (currently 0 typed entities despite 19.9M generic)
- [ ] Key-value colon parsing for 5.4M semi-structured chunks
- [ ] A/B test: entity-type queries before/after population
- [ ] **Aggregation capability slice (Slices 0-2): gold top-N pack, `failure_events` table, extractor wire-up.** See `SPRINT_SLICE_AGGREGATION_CAPABILITY_2026-04-18.md`

### Lane C: Deploy + Demo Prep
- [ ] Test install scripts on BOTH work machines (laptop + desktop) with real proxy
- [ ] Version downgrade validation (oldest safe waiver versions)
- [ ] Fix LanceDB import RAM explosion (loads VRAM-equivalent of RAM)
- [ ] Fix GUI VRAM label mislabeling
- [ ] Demo rehearsal pack verification

**Sprint 2 Acceptance:** 75%+ retrieval PASS. Entity store has typed entities + relationships. Install works behind proxy on both work machines.

---

## Sprint 3

**Theme:** Entity extraction at scale + relationship recovery
**Depends on:** Sprint 2 entity population path verified

### Lane A: Retrieval Quality
- [ ] Run full 400-query eval with GPT-4o generation (not just retrieval-only)
- [ ] Measure end-to-end answer quality: retrieval + generation
- [ ] Tune reranker + context builder based on GPT-4o results
- [ ] Compare GPT-4o vs phi4 on same 400-query pack (phi4 for cost comparison only)
- [ ] Target: 80%+ end-to-end with GPT-4o

### Lane B: Entity Enrichment
- [ ] Evaluate GLiREL for deterministic relationship extraction (CoPilot+-Researcher finding)
- [ ] If GLiREL A/B shows improvement: integrate into Tier 2 extraction pipeline
- [ ] Cross-chunk dedup in quality_gate.py (marathon Hash Point: `TC 16-06-23-003` vs `TC16-06-23-003`)
- [ ] Run CoPilot+ Max hardtail extraction on 1000 new chunks (overnight, free on Max plan)
- [ ] Compare: updated Tier 1 regex vs phi4 vs CoPilot+ on same hardtail pack
- [ ] **Aggregation capability slice (Slices 3-7): canonical normalization, aggregate SQL API, router + generator wire-up, A/B, demo rehearsal.** See `SPRINT_SLICE_AGGREGATION_CAPABILITY_2026-04-18.md`. Demo queries: "highest failing part numbers in Nexion 2024", "ISTO Djibouti 2022-2025", "top 5 failure parts per year for past 7 years"

### Lane C: Deploy + Demo Prep
- [ ] CorpusForge install script proxy-hardened
- [ ] Demo deck finalized with industry validation citations (5 from CoPilot+-Researcher)
- [ ] Demo rehearsal: full walkthrough with real queries on work machine
- [ ] Sanitizer updated with all compliance patterns
- [ ] Fresh install test on clean work machine (wipe + reinstall)

**Sprint 3 Acceptance:** 80%+ end-to-end with GPT-4o. GLiREL A/B tested. Demo deck ready. Clean install verified.

---

## Sprint 4

**Theme:** Demo hardening + edge cases
**Depends on:** Sprint 3 demo rehearsal findings

### Lane A: Retrieval Quality
- [ ] Fix edge cases from demo rehearsal (specific queries that fail)
- [ ] Aggregation query improvements (currently 56% -- demo audience will ask these)
- [ ] "I don't know" response quality (abstention on out-of-scope queries)
- [ ] Cross-document reasoning queries (the hardest case)
- [ ] Target: 85%+ on demo-relevant query subset

### Lane B: Entity Enrichment
- [ ] CorpusForge metadata enrichment (marathon Hash Point 2: richer chunk emission)
- [ ] Site alias normalization map (from overnight mining path signals)
- [ ] Vendor/organization name normalization
- [ ] Schema v2 locked-set validation (promote only if it wins on frozen hardtail)
- [ ] Post-merge cross-chunk canonicalization

### Lane C: Deploy + Demo Prep
- [ ] Nightly diff pipeline (CorpusForge incremental ingest)
- [ ] Production monitoring setup (Splunk forwarder is pre-approved)
- [ ] Operator runbook for daily operations
- [ ] Security posture documentation for Cyber review
- [ ] Backup/recovery procedures

**Sprint 4 Acceptance:** 85%+ on demo queries. Nightly diff pipeline working. Security docs ready for Cyber.

---

## Sprint 5

**Theme:** Demo day prep + polish
**Depends on:** Sprint 4 complete

### Lane A: Retrieval Quality
- [ ] Final 400-query eval with production config
- [ ] Latency optimization (target: <5s p50 wall clock with GPT-4o)
- [ ] Query cache for repeated questions (demo reliability)
- [ ] Stress test: 50 rapid queries back-to-back

### Lane B: Entity Enrichment
- [ ] Freeze entity schema (no more changes before demo)
- [ ] Final entity count verification
- [ ] Relationship store health check (target: >10K relationships)
- [ ] Extraction quality spot-check (10 random entities verified by human)

### Lane C: Deploy + Demo Prep
- [ ] Demo day dry run on work machine (full audience simulation)
- [ ] One-pager for PM (problem, solution, security, accuracy, cost, next steps)
- [ ] Backup demo on primary workstation (if work machine fails)
- [ ] Print demo QA prep doc (50 questions + answers)
- [ ] Final button smash on work machine GUI

**Sprint 5 Acceptance:** Demo-ready. All queries rehearsed. Backup plan tested. One-pager printed.

---

## Key Metrics Across Sprints

| Sprint | Retrieval PASS Target | Entity Store | Demo Readiness |
|--------|----------------------|-------------|----------------|
| 1 (current) | 64% (baseline) | 19.9M generic, 0 relationships | Install scripts built |
| 2 | 75%+ | Typed entities + relationships populated | Install tested on work machines |
| 3 | 80%+ (with GPT-4o) | GLiREL A/B tested, cross-chunk dedup | Demo deck + rehearsal |
| 4 | 85%+ (demo queries) | Schema v2 validated, nightly diff | Security docs, operator runbook |
| 5 | 85%+ (certified) | Frozen, verified | Demo day ready |

---

## Architecture Reference

```
User Query
    |
    v
[Query Router] -- GPT-4o classifies query type (ENTITY/SEMANTIC/TABULAR/AGGREGATE)
    |
    v
[Vector Search] -- LanceDB IVF_PQ on 10.4M chunks (189ms p50) -- WORKING
    |
    v
[FTS Search] -- LanceDB Tantivy full-text (sub-second) -- WORKING
    |
    v
[Hybrid Fusion] -- RRF combines vector + FTS results -- WORKING
    |
    v
[Reranker] -- FlashRank cross-encoder (3.3s p50) -- WORKING
    |
    v
[Entity Retriever] -- SQLite entity store lookup -- BROKEN (0 relationships, LIKE on 19.9M)
    |                                                  FIX: FTS5 + populate typed entities
    v
[Context Builder] -- Assembles chunks + entities for LLM
    |
    v
[GPT-4o Generation] -- Produces cited answer (demo/production)
[phi4:14b] -- Local alternative for overnight/batch work (not demo-facing)
```

---

Jeremy Randall | HybridRAG_V2 | 2026-04-16 MDT
