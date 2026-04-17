# HybridRAG V2 — Revised Sprint Plan (Dependency-Ordered)

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-05 MDT
**Demo Target:** 2026-05-02

**Architecture Rule:** primary workstation = dev/prove architecture only. Production data processing on work machines.
**Cost Rule:** phi4:14b ($0 local) for bulk extraction. GPT-4o-mini ($0.207/1M) as fallback. GPT-4o for user-facing queries only.
**Throughput Rule:** CUDA-only embedding. CPU/Ollama HTTP fallback kills speed (45x slower). Verify CUDA stays active.
**Parallel Rule:** CorpusForge and V2 work streams run in parallel wherever possible. QA each sprint.

---

## Completed Sprints

| Sprint | Focus | Status | Key Metric |
|--------|-------|--------|------------|
| Sprint 1 | Core tri-store, API, hybrid search | QA 10/10 | Sub-30ms retrieval |
| Sprint 2 | Entity extraction, query router, quality gates | QA 11/11 | 169 entities extracted |
| Sprint 3 | CRAG verifier, GUI, enrichment, eval scorer | QA 13/13 | 25/25 retrieval |
| Sprint 4 | Perf tuning, V1vsV2 harness, demo prep, docs | QA 14/14 | 10/10 demo rehearsal |

---

## Sprint 5: primary workstation Setup + Pipeline Proof (CURRENT)

**Goal:** Both repos running on primary workstation with real data, CUDA verified, parallel pipeline proven.
**Two parallel tracks: CorpusForge (CF) and HybridRAG V2 (V2).**

### Track A: CorpusForge on primary workstation

| Slice | Work | Status | Depends on |
|-------|------|--------|------------|
| 5A.1 | Create CorpusForge venv on primary workstation (py -3.12, torch cu128, requirements.txt) | TODO | primary workstation access |
| 5A.2 | Fix CorpusForge launcher (CRLF bat, QA blocker) | DONE | |
| 5A.3 | Port parallel 8-worker pipeline from V1 to CorpusForge pipeline.py | DONE | |
| 5A.4 | CorpusForge GUI — human visual pass via start_corpusforge.bat | TODO | 5A.1 |
| 5A.5 | Verify CUDA-only embedding (verify_cuda_embedding.py) — must show "cuda" not "onnx" | TODO | 5A.1 |
| 5A.6 | Verify parallel pipeline (verify_parallel_pipeline.py) — 8 workers vs 1, measure speedup | TODO | 5A.1 |
| 5A.7 | Run CorpusForge throughput benchmark (benchmark_pipeline.py) on golden 14 files | TODO | 5A.5 + 5A.6 |
| 5A.8 | CorpusForge test run — 100 file subset from data/source, watch it live | TODO | 5A.7 |
| 5A.9 | Fix everything that breaks — parser crashes, encoding, CUDA fallback | Throughout | |

### Track B: HybridRAG V2 Pipeline

| Slice | Work | Status | Depends on |
|-------|------|--------|------------|
| 5B.1 | Fix import_embedengine.py (--source required, batch inserts, mmap vectors) | DONE | |
| 5B.2 | Import CorpusForge export into V2 LanceDB — verify chunks appear | TODO | 5A.8 |
| 5B.3 | Entity extraction on imported chunks — populate SQLite stores | TODO | 5B.2 |
| 5B.4 | First real query in V2 GUI — the proof moment | TODO | 5B.3 |
| 5B.5 | V2 GUI human visual pass — query panel, entity panel, settings | TODO | 5B.4 |

### Track C: phi4 Extraction Validation (CRITICAL PATH)

| Slice | Work | Status | Depends on |
|-------|------|--------|------------|
| 5C.1 | Install Ollama on primary workstation | TODO | primary workstation access |
| 5C.2 | Pull phi4:14b-q4_K_M (~8GB download) | TODO | 5C.1 |
| 5C.3 | Quick smoke test: single extraction call, verify JSON output | TODO | 5C.2 |
| 5C.4 | Run A/B test: 50 chunks from Clone1, phi4 vs GPT-4o side by side | TODO | 5C.2 + API key |
| 5C.5 | QA analyzes A/B results with agentic eval best practices | TODO | 5C.4 |
| 5C.6 | Decision gate: phi4 approved/rejected for work extraction | TODO | 5C.5 |

### Track D: Clone1 Structure Learning

| Slice | Work | Status | Depends on |
|-------|------|--------|------------|
| 5D.1 | Analyze file_hash dedup rates in Clone1 (exact duplicates) | TODO | Clone1 on C: |
| 5D.2 | Analyze source_quality table for parsing failure patterns | TODO | Clone1 on C: |
| 5D.3 | Analyze chunk length distribution — inform V2 chunking strategy | TODO | Clone1 on C: |
| 5D.4 | Document dedup/parsing/chunking findings (agnostic, no production data) | TODO | 5D.1-3 |

### Track E: Environment Setup + Verification

| Slice | Work | Status | Depends on |
|-------|------|--------|------------|
| 5E.1 | Verify env vars on primary workstation: CUDA_VISIBLE_DEVICES pinned per repo (no GPU sharing), PYTHONUTF8=1 | TODO | |
| 5E.2 | Verify API key: OPENAI_API_KEY set and working (commercial, for A/B test) | TODO | |
| 5E.3 | Verify CorpusForge config/config.yaml: paths, embed device=cuda, workers=8 | TODO | 5A.1 |
| 5E.4 | Verify V2 config/config.yaml: paths, llm.provider=auto, extraction.model=phi4 | TODO | |
| 5E.5 | Run validate_setup.py on V2 — all 16 checks pass or documented gap | TODO | 5E.1-4 |
| 5E.6 | Run health_check.py on V2 — stores, config, GPU, disk all green | TODO | 5E.5 |
| 5E.7 | Verify nvidia-smi: GPU 0 available, driver current, VRAM free | TODO | |
| 5E.8 | Verify Ollama serves on localhost:11434 after install | TODO | 5C.1 |

**Sprint 5 Exit Criteria:**
1. CorpusForge processes 100+ files on primary workstation with CUDA embedding at >30 chunks/sec
2. V2 imports CorpusForge export and answers a real query with source citations
3. phi4 extraction quality validated (approved or rejected with data)
4. Parallel 8-worker pipeline verified faster than sequential
5. All scripts in both repos have been QA'd on real hardware

**Sprint 5 QA Checklist (for QA team):**
- [ ] CorpusForge venv works, GUI launches, CUDA verified
- [ ] Parallel pipeline speedup measured (target: 3-6x over sequential)
- [ ] CUDA embedding stays on GPU — never falls back to ONNX/CPU during run
- [ ] Throughput benchmark: report chunks/sec per stage
- [ ] A/B extraction: QA independently evaluates phi4 vs GPT-4o results
- [ ] V2 import: chunks appear in LanceDB, entities in SQLite
- [ ] V2 query: answer references real document content
- [ ] Both GUIs: human visual pass, no crashes
- [ ] Clone1 dedup analysis: findings documented

---

## Sprint 6: Scale + Prove

**Goal:** Push volume through the pipe and prove it handles real-world scale.

| Slice | Work | Depends on |
|-------|------|------------|
| 6.1a | CorpusForge scale run — 5,000+ files on GPU 0, fix edge cases | Sprint 5 |
| 6.1b | CorpusForge Clone on GPU 1 — 2x throughput, split source dirs, merge exports | 6.1a proven |
| 6.2 | Import + extract at scale — bulk LanceDB + entity extraction | 6.1 |
| 6.3 | Performance tuning on real data — benchmark.py, tune indexes | 6.2 |
| 6.4 | Golden eval on real data — run 400-query set, measure pass rate | 6.2 |
| 6.5 | Contextual enrichment test — phi4:14b preambles, measure retrieval improvement | 6.1 |
| 6.6 | Dedup pipeline integration — implement SimHash/MinHash from 5D findings | 5D.4 |
| 6.7 | Port to work machine — install both repos, prove deployment guide works | Sprint 5 |

**Exit criteria:** 5,000+ files processed. 15/25 golden queries on real data. P50 measured. Runs on 2 machines. Dedup reduces index by measurable %.

**Sprint 6 QA Checklist:**
- [ ] 5K+ files through CorpusForge without crash
- [ ] Throughput: report chunks/sec at scale (target: >30/sec sustained)
- [ ] LanceDB index: verify vector count matches chunk count
- [ ] Entity extraction: types and counts reasonable for corpus
- [ ] Golden eval: 15/25 minimum, report per-query breakdown
- [ ] Dedup: before/after chunk count comparison
- [ ] Work machine: both repos install and run from guide alone

---

## Sprint 7: Work Extraction + Demo Hardening

**Goal:** Production extraction running at work 24/7. Demo rehearsed on real data.

| Slice | Work | Depends on |
|-------|------|------------|
| 7.1 | START extraction at work — phi4 or GPT-4o-mini per 5C decision | Sprint 5C + 6.7 |
| 7.2 | Full corpus run — process largest feasible subset overnight/weekend | 7.1 |
| 7.3 | V1 vs V2 comparison — same queries, document improvement numbers | 7.2 + V1 boots |
| 7.4 | Persona-specific queries — PM, logistics, engineer on real data | 7.2 |
| 7.5 | Demo rehearsal on real data — 10-query flow, timed | 7.4 |
| 7.6 | Human button smash — non-developer, 10 min, GUI harness Tier D | 7.2 |
| 7.7 | Screen-record backup demo | 7.5 |
| 7.8 | Performance polish — P50 < 3s, query cache warm-up | 7.2 |
| 7.9 | Skip-file acknowledgment slide — "indexed X of Y, deferred Z tracked" | 7.2 |

**Exit criteria:** 20/25 golden queries on real data. Demo rehearsed. Button smash survived. Backup recording exists. Skip manifest presented cleanly.

**Sprint 7 QA Checklist:**
- [ ] Work extraction: running or complete, chunk count reported
- [ ] V1 vs V2: side-by-side comparison on 10+ queries
- [ ] Demo rehearsal: 10 queries, 3 personas, under time target
- [ ] Button smash: Tier D, non-developer, 10 min, 0 crashes
- [ ] Backup recording exists and plays
- [ ] P50 latency < 3s measured on real data

---

## Sprint 8: Demo Day (May 2)

| Slice | Work |
|-------|------|
| 8.1 | Morning-of verification — machine ready, keys set, Ollama running |
| 8.2 | Deliver demo — 10 queries, 3 personas, skip acknowledgment, V1 vs V2 |
| 8.3 | Capture feedback — stakeholder reactions, feature requests |
| 8.4 | Post-demo handoff — update docs, plan next phase |

---

## Sprint 9: Post-Demo Production (Backlog)

| Slice | Work |
|-------|------|
| 9.1 | Incorporate demo feedback |
| 9.2 | Full 700GB corpus if not done |
| 9.3 | Turnkey report generation prototype (PM persona) |
| 9.4 | Azure OpenAI migration for work deployment |
| 9.5 | AWS GovCloud OSS integration (if endpoint accessible externally) |
| 9.6 | User training materials + operator certification |
| 9.7 | Monitoring + alerting dashboard |
| 9.8 | CorpusForge GUI polish (progress per-file, cancel between files) |
| 9.9 | Content-level dedup at scale (MinHash across full corpus) |

---

## Critical Path to Demo

```
NOW ────────────────────────────────────────────────────── May 2
  │
  ├── Sprint 5 (4 parallel tracks, ~3-4 days)
  │   ├─ Track A: CorpusForge on primary workstation (venv, CUDA, parallel pipeline)
  │   ├─ Track B: V2 import + first query
  │   ├─ Track C: phi4 A/B validation ← GATES WORK EXTRACTION
  │   └─ Track D: Clone1 structure learning
  │
  ├── Sprint 6: Scale + prove (~4 days)
  │   ├─ 5K files, golden eval, perf tuning
  │   └─ Port to work machine
  │
  ├── Sprint 7: Work extraction + demo hardening (~5 days)
  │   ├─ START EXTRACTION AT WORK 24/7 ← long pole
  │   └─ Demo rehearsal, V1 vs V2, button smash
  │
  └── Sprint 8: Demo Day (May 2)
```

**LONG POLE:** Work extraction start date. Track C (phi4 validation) gates it.

---

## Extraction Math (First Principles)

**Raw corpus:** 27.6M chunks from 187K source files.
**After filtering pipeline:**
1. Skip list (CAD/binary): -50% → ~93K parseable files
2. Format-conversion dedup (DOCX→PDF, signed versions): -20-30% → ~65K unique files
3. Meaningful chunks only (not headers/boilerplate/footers): ~30-50 per file → ~2-3M chunks
4. Regex pre-extraction (parts, emails, dates, POs): handles 60-70% of easy entities for $0
5. Entity-signal filter (skip chunks with zero extractable signal): -40-50%
6. **LLM extraction needed: ~1-1.5M chunks**

**V1 PROVEN throughput (Clone1 git 2026-03-22 to 2026-04-05):**
- V1 realistic average: **~60 chunks/sec** (varied by file type and parse quality)
- Peak: **200 chunks/sec** on work laptop with CUDA batch + 8 parallel workers
- Key: ThreadPoolExecutor(8 workers) → prefetch 2x → GPU batch embed → SQLite write
- Token-budget dynamic batching (49K budget, Snowflake 16x paper)
- OOM backoff: halves batch size on CUDA OOM, persists across batches
- Direct CUDA encode: 45x faster than Ollama HTTP
- **CRITICAL V1 LESSON:** CPU/Ollama fallback kills throughput. Must verify CUDA stays active.

**V2 extraction timeline (using V1 proven patterns):**
- 1.5M filtered chunks at 60/sec = **~7 hours (one workday)**
- Full 14M unfiltered at 60/sec = **~65 hours (~3 days)**
- With filtering + work Blackwell GPUs (faster than dev workstation GPU): **4-8 hours realistic**
- **Work machine runs 24/7 in background** — start ASAP once phi4 validated

**Source commits to port:** `afe7877`, `0750633`, `8fba386` (all 2026-04-02 in Clone1).

---

## Source Data Structure

```
C:\HybridRAG_V2\data\source\
├── program_management/     ← PM persona queries
├── logistics/              ← Logistics analyst queries
├── field_engineer/         ← Field engineer queries
├── engineering/            ← Engineer queries (92K files, many CAD → skip list)
├── system_admin/           ← Sysadmin queries
├── autocad/                ← CAD-specific (mostly deferred via skip list)
├── cyber_security/         ← Cybersecurity docs
├── bulk_stress_test/       ← Mixed formats for stress testing
└── role_corpus_golden/     ← 14 curated golden files (1 per role per format)
```

**Testing Resources:**
- Clone1 index: {USER_HOME}\HybridRAG3_Clone1\data\index\ (27.6M chunks, 187GB)
- 400-query golden set: `tests/golden_eval/golden_tuning_400.json`
- V1 source commits: Clone1 `src/core/indexer.py`, `src/core/embedder.py`

**Skip list strategy:** Hash ALL files. Parse text-based formats. Defer CAD/binary via skip manifest. At demo: "We indexed X of Y files. The deferred formats are hashed and tracked."

---

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
