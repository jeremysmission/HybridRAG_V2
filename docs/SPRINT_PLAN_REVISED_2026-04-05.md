# HybridRAG V2 — Revised Sprint Plan (Dependency-Ordered)

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-05 MDT
**Demo Target:** 2026-05-02

---

## Completed Sprints

| Sprint | Focus | Status | Key Metric |
|--------|-------|--------|------------|
| Sprint 1 | Core tri-store, API, hybrid search | QA 10/10 | Sub-30ms retrieval |
| Sprint 2 | Entity extraction, query router, quality gates | QA 11/11 | 169 entities extracted |
| Sprint 3 | CRAG verifier, GUI, enrichment, eval scorer | QA 13/13 | 25/25 retrieval |
| Sprint 4 | Perf tuning, V1vsV2 harness, demo prep, docs | QA 14/14 | 10/10 demo rehearsal |

---

## Sprint 5: Data Pipeline — Get Real Data Flowing

**Goal:** Real files through real pipes on real hardware. Nothing else matters until this works.

| Slice | Work | Status |
|-------|------|--------|
| 5.1 | Stage source files on C: (role-based subfolders from D:\source) | In progress (copies running) |
| 5.2 | CorpusForge GUI — human visual pass | Ready (start_corpusforge.bat) |
| 5.3 | CorpusForge test run — 100 file subset via GUI, watch it live | Blocked by 5.1 + 5.2 |
| 5.4 | Import to V2 — run import_embedengine.py, verify chunks | Blocked by 5.3 |
| 5.5 | Entity extraction on real chunks — populate stores | Blocked by 5.4 |
| 5.6 | First real query in V2 GUI — the proof moment | Blocked by 5.5 |
| 5.7 | Fix everything that breaks — parser crashes, encoding, paths | Throughout |

**Exit criteria:** You can ask a real question about real production-sim documents and get a real answer with real source citations.

---

## Sprint 6: Scale + Prove

**Goal:** Push volume through the pipe and prove it handles real-world scale.

| Slice | Work | Depends on |
|-------|------|------------|
| 6.1 | CorpusForge scale run — 5,000+ files, fix edge cases | Sprint 5 |
| 6.2 | Import + extract at scale — bulk LanceDB + entity extraction | 6.1 |
| 6.3 | Performance tuning on real data — benchmark.py, tune indexes | 6.2 |
| 6.4 | Golden eval on real data — run 400-query set, measure pass rate | 6.2 |
| 6.5 | Enrichment test — pull phi4:14b, measure retrieval improvement | 6.1 |
| 6.6 | Second machine deployment — install on work laptop, prove guide works | Sprint 5 |

**Exit criteria:** 5,000+ files processed. 15/25 golden queries on real data. P50 measured. Runs on 2 machines.

---

## Sprint 7: Demo Ready

**Goal:** Prove it's showable with real data, rehearsed, stress-tested.

| Slice | Work | Depends on |
|-------|------|------------|
| 7.1 | Full corpus run — process largest feasible subset, run overnight | Sprint 6 |
| 7.2 | V1 vs V2 comparison — same queries, document improvement numbers | 7.1 + V1 boots |
| 7.3 | Persona-specific queries — PM, logistics, engineer on real data | 7.1 |
| 7.4 | Demo rehearsal on real data — 10-query flow, timed | 7.3 |
| 7.5 | Human button smash — non-developer, 10 min, GUI harness Tier D | 7.1 |
| 7.6 | Screen-record backup demo | 7.4 |
| 7.7 | Performance polish — P50 < 3s, query cache warm-up | 7.1 |

**Exit criteria:** 20/25 golden queries on real data. Demo rehearsed. Button smash survived. Backup recording exists.

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
| 9.5 | User training materials + operator certification |
| 9.6 | Monitoring + alerting dashboard |
| 9.7 | CorpusForge GUI polish (progress per-file, cancel between files) |

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

**Skip list strategy:** Hash ALL files. Parse text-based formats (PDF, DOCX, XLSX, TXT, HTML, email, etc.). Defer CAD/binary formats (DWG, PAR, SolidWorks) via skip manifest. At demo: "We indexed X of Y files. The deferred formats are hashed and tracked."

**400-query golden set:** `tests/golden_eval/golden_tuning_400.json` — role-tagged, fact-mapped, citation-verified. Ported from V1.

---

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
