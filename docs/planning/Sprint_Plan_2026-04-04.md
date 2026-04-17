# HybridRAG V2 — Sprint Plan (4-Week Demo Target)

**Author:** Jeremy Randall (CoPilot+)
**Repo:** HybridRAG_V2
**Date:** 2026-04-04 MDT
**Demo Target:** 2026-05-02 (4 weeks from today)
**Work Mode:** Nights and weekends included. Agile — get something useful out for demo ASAP.

---

## Guiding Principles

1. **Every sprint produces a working, demo-able system.** No big bang.
2. **Sprint 1 is the MVP.** If we only finish Sprint 1, we still have something better than V1.
3. **Reuse V1 code aggressively.** Parsers, GUI aesthetic, security modules — copy, don't rewrite.
4. **500 lines per class max** (comments excluded). Keeps code AI-reviewable and modular.
5. **Golden eval from day one.** 5 queries in Sprint 1, 20+ by Sprint 4.

---

## Sprint 1: Foundation (Week 1 — April 5-11)

**Goal:** Basic semantic query pipeline working against imported V1 index. Prove the repo boots, queries, and answers.

### Slice 1.1: Repo Bootstrap (Day 1-2)
- [ ] Initialize git repo, CoPilot+.md, .gitignore
- [ ] Create directory structure (src/, tests/, docs/, scripts/, config/)
- [ ] Port Pydantic config schema from V1 (simplified: 1 mode, 2 presets)
- [ ] Write config.yaml (single config, no mode switching)
- [ ] Boot sequence: validate config → connect stores → ready

### Slice 1.2: LanceDB Store (Day 2-3)
- [ ] Implement `lance_store.py` — create/open LanceDB table
- [ ] Write `migrate_v1_index.py` script — import V1 FAISS vectors + SQLite chunks into LanceDB
- [ ] Verify: 27.6M chunks loaded, vector search returns results
- [ ] Verify: BM25 full-text search works (should be sub-second vs V1's 12-24s)
- [ ] **Fallback if LanceDB waiver blocked:** implement `faiss_store.py` wrapping V1's FAISS + FTS5

### Slice 1.3: Basic Query Pipeline (Day 3-5)
- [ ] Implement `llm/client.py` — unified openai SDK client (GPT-4o, GPT-OSS-120B)
- [ ] Implement `query/vector_retriever.py` — LanceDB hybrid search (vector + BM25 + RRF)
- [ ] Implement `query/reranker.py` — FlashRank reranking (top-30 → top-10)
- [ ] Implement `query/context_builder.py` — assemble context from ranked chunks
- [ ] Implement `query/generator.py` — GPT-4o generation with graduated confidence
- [ ] Implement `api/routes.py` — POST /query endpoint
- [ ] **Fallback if FlashRank waiver blocked:** use LanceDB built-in reranking

### Slice 1.4: First Golden Eval (Day 5-7)
- [ ] Write 5 golden queries (mix of semantic, entity, aggregation)
- [ ] Run eval, measure: fact_score, confidence accuracy, latency
- [ ] Compare against V1 baseline on same queries
- [ ] Document results

### Sprint 1 Exit Criteria
- [ ] Repo boots from clean install in <30 seconds
- [ ] Simple semantic queries return relevant answers with citations
- [ ] LanceDB hybrid search under 100ms (vs V1's 12-24s FTS5)
- [ ] FlashRank reranking under 50ms
- [ ] 5/5 golden queries produce reasonable answers
- [ ] API endpoint functional

**Sprint 1 Deliverable:** A working RAG system that is already faster than V1 on keyword search, with FlashRank reranking and graduated confidence. No entity extraction yet — that's Sprint 2.

---

## Sprint 2: Quality-Gated Extraction (Week 2 — April 12-18)

**Goal:** Populate structured tables with validated entities. Make aggregation and lookup queries work.

### Slice 2.1: Entity Extraction Pipeline (Day 1-3)
- [ ] Implement `ingest/entity_extractor.py` — GLiNER2 first-pass NER
- [ ] Implement GPT-4o second-pass for complex entities (failure narratives, relationships)
- [ ] Define entity schema: part_number, person, site, date, failure_mode, action_type
- [ ] Run extraction on sample of 1,000 chunks, measure quality
- [ ] **Fallback if GLiNER waiver blocked:** GPT-4o handles all extraction

### Slice 2.2: Quality Gates + Normalization (Day 2-4)
- [ ] Implement `ingest/quality_gate.py` — confidence thresholds (reject < 0.7)
- [ ] Implement `ingest/entity_normalizer.py` — controlled vocabulary matching
- [ ] Build site vocabulary (25 enterprise program sites with known aliases)
- [ ] Build part number pattern validator (ARC-NNNN, IGSI-NNNN, PO-YYYY-NNNN)
- [ ] Build person name deduplication (separate phone/email from name)
- [ ] Implement `scripts/audit_extraction.py` — quality report

### Slice 2.3: Structured Stores (Day 3-5)
- [ ] Implement `store/entity_store.py` — SQLite tables for validated entities
- [ ] Implement `store/relationship_store.py` — entity-relationship triples
- [ ] Implement `store/table_store.py` — Docling-extracted table rows
- [ ] Implement `ingest/table_extractor.py` — Docling table extraction
- [ ] **Fallback if Docling waiver blocked:** openpyxl for .xlsx, pdfplumber for PDF tables

### Slice 2.4: Query Router + Structured Retrieval (Day 5-7)
- [ ] Implement `query/router.py` — GPT-4o query classification
- [ ] Implement `query/entity_retriever.py` — SQLite entity/aggregation lookup
- [ ] Implement `query/table_retriever.py` — Text2SQL via GPT-4o
- [ ] Implement `query/decomposer.py` — sub-query generation for COMPLEX queries
- [ ] Run extraction on full corpus (background, may take 2-3 days)

### Sprint 2 Exit Criteria
- [ ] Entity extraction produces validated, normalized data
- [ ] "Who is the POC for Thule?" returns a real person name
- [ ] "How many maintenance service reports in 2025?" returns a count from SQL
- [ ] Quality audit report shows extraction accuracy metrics
- [ ] 10/10 golden queries passing (including entity + aggregation types)

**Sprint 2 Deliverable:** The structured extraction pipeline is live. Aggregation queries that were impossible in V1 now return SQL-backed answers with citations.

---

## Sprint 3: Query Intelligence + GUI (Week 3 — April 19-25)

**Goal:** Multi-hop queries, contextual enrichment integration, GUI with streaming, CRAG verification.

### Slice 3.1: Contextual Enrichment Integration (Day 1-2)
- [ ] Import contextually-enriched chunks from EmbedEngine (phi4:14B output)
- [ ] Load enriched text into LanceDB BM25 index
- [ ] Measure retrieval improvement on golden queries (target: 30%+ improvement)
- [ ] If EmbedEngine enrichment not ready: run enrichment via GPT-OSS (free) in batch

### Slice 3.2: Advanced Query Features (Day 2-4)
- [ ] Multi-hop query support via relationship JOINs
- [ ] Query expansion (synonym matching, acronym resolution)
- [ ] Parent chunk expansion (retrieve child, return parent for context)
- [ ] CRAG verification loop (GPT-OSS-20B grades response, retries if low confidence)
- [ ] Streaming response support (SSE via FastAPI)

### Slice 3.3: GUI Port (Day 4-6)
- [ ] Port V1 Tkinter color scheme, fonts, button styles
- [ ] Implement streaming token display
- [ ] Add query path badge (SEMANTIC / SQL / LOOKUP / MULTI-HOP)
- [ ] Add graduated confidence indicator (HIGH green / PARTIAL yellow / NOT_FOUND red)
- [ ] Add expandable source citations panel
- [ ] Add structured results display (tables rendered as tables)
- [ ] Remove: mode toggle, role selector, grounding bias slider

### Slice 3.4: Expanded Golden Eval (Day 6-7)
- [ ] Expand golden eval to 20+ queries
- [ ] Include all five failure classes: aggregation, entity, tabular, synonym, cross-doc
- [ ] Measure: fact_score, confidence accuracy, latency, path routing accuracy
- [ ] Compare V1 vs V2 on identical queries — document improvements

### Sprint 3 Exit Criteria
- [ ] GUI boots and renders with V1 aesthetic
- [ ] Streaming responses work end-to-end
- [ ] Multi-hop queries produce merged results from multiple stores
- [ ] CRAG verification catches at least 1 hallucination in eval set
- [ ] 15/20 golden queries passing with correct confidence levels

**Sprint 3 Deliverable:** A polished query system with GUI, streaming, and all five query types working. This is the minimum demo-ready system.

---

## Sprint 4: Demo Hardening (Week 4 — April 26 - May 2)

**Goal:** Production-quality on real work data. Demo-ready.

### Slice 4.1: Full Corpus Validation (Day 1-3)
- [ ] Run full extraction on production corpus (if not completed in Sprint 2)
- [ ] Validate extraction quality on work data (not primary workstation test data)
- [ ] Tune: confidence thresholds, retrieval depths, RRF weights, reranking top-N
- [ ] Build index audit report ("what did we extract?")
- [ ] Identify and fix any corpus-specific edge cases

### Slice 4.2: Performance Tuning (Day 3-5)
- [ ] Benchmark all query types on production data
- [ ] Target: P50 < 3s, P95 < 10s
- [ ] Optimize LanceDB index settings for 27.6M chunks
- [ ] Optimize SQLite indexes for entity/aggregation queries
- [ ] Memory profiling on primary workstation and laptop

### Slice 4.3: Demo Prep (Day 5-7)
- [ ] Prepare 10 demo queries covering all failure classes
- [ ] Document expected answers for each demo query
- [ ] Rehearse demo flow: simple → entity → aggregation → tabular → complex
- [ ] Build "V1 vs V2" comparison slides (same query, different results)
- [ ] Final golden eval: 20/20 queries passing
- [ ] Bug fixes, edge cases, polish

### Slice 4.4: Documentation + Handover (Day 7)
- [ ] Update all docs with final architecture
- [ ] Write deployment guide (clean install steps)
- [ ] Write operator guide (how to run queries, read confidence levels)
- [ ] Create demo script with talking points

### Sprint 4 Exit Criteria
- [ ] 20/20 golden queries passing on production data
- [ ] P50 latency < 3s, P95 < 10s
- [ ] GUI demo flow rehearsed and documented
- [ ] Clean install works on fresh machine
- [ ] All docs current

**Sprint 4 Deliverable:** Demo-ready system. V1 vs V2 comparison documented. Operator guide written. Ready to show.

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Waiver delays (any of 4 packages) | Medium | Low | Every package has a fallback using approved software. Development proceeds. |
| GLiNER extraction quality poor on corpus | Medium | Medium | GPT-4o handles complex entities. Quality gates reject garbage. Audit report surfaces issues early. |
| LanceDB issues at 27.6M scale | Low | High | FAISS + FTS5 fallback is V1's proven stack. Migration script works both ways. |
| Full corpus extraction takes > 3 days | Medium | Low | Start in Sprint 2, runs in background. Demo can use partial extraction. |
| EmbedEngine enrichment not ready | Medium | Low | Run enrichment via GPT-OSS in batch. Same technique, API cost instead of free. |
| Demo date pressure | High | High | Sprint 1 alone produces a working system better than V1. Each subsequent sprint adds capability. |

---

## Reuse from V1

| V1 Module | V2 Reuse | Notes |
|---|---|---|
| 32 file parsers | Copy as-is | Battle-tested on 100K+ files |
| GUI color scheme + buttons | Port aesthetic | Same Tkinter, simplified internals |
| Config validation pattern | Adapt to Pydantic | Simpler (1 mode, 2 presets) |
| Security/injection guard | Copy as-is | V1's 9-rule prompt is proven |
| Cost tracker | Copy as-is | Same openai SDK billing |
| Query history logging | Adapt | Same SQLite pattern |
| Boot sequence pattern | Adapt | Simpler (no mode detection) |
| EmbedEngine modules | Separate repo | Chunker, embedder, batch manager reused |

---

Jeremy Randall | HybridRAG_V2 | 2026-04-04 MDT
