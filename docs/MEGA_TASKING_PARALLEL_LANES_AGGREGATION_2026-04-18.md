# MEGA Task Plan — Parallel Lanes for Failure-Aggregation Capability (2026-04-18)

**Owner:** Jeremy Randall (HybridRAG_V2)
**Co-pilot:** CoPilot+
**Target demo:** 2026-05-02 (14 days out)
**Sprint parent:** Sprint 3 + Sprint D (Aggregation / Failure Substrate)
**Companion doc:** `SPRINT_SLICE_AGGREGATION_FAILURE_RATE_2026-04-18.md`

---

## Resources on the Board

| Resource | Role | Primary surface | Never touches |
|----------|------|----------------|---------------|
| **Lane A** | Coder A on **V2 / GPU 0** | `src/query/`, `src/gui/`, GPU 0 eval | V2_Dev branch, Lane B substrate |
| **Lane B** | Coder B on **V2_Dev / GPU 1** | `src/extraction/`, `src/store/`, GPU 1 eval | V2 branch, Lane A product surfaces |
| **R3** (Claude-R3) | Data researcher / truth-pack owner | `HYBRIDRAG_LOCAL_ONLY/`, corpus mining | Repo code (research artifacts only) |
| **Researcher-Web** (Claude-Researcher) | Literature + external validation | `HYBRIDRAG_LOCAL_ONLY/research_notes/` | Repo code |
| **Coder-Free** (Codex / 3rd floater) | Unblocked coding helper | Whichever surface has no active owner | Do not cross lane owners |
| **QA** | Gate keeper | Eval runs, GUI smash, acceptance reports | Code (does not commit) |

### Hard Parallelism Rules
1. **No lane crosses another lane's code surface.** Lane A owns retrieval/router/GUI in V2. Lane B owns extraction/substrate in V2_Dev. Merges happen via PR after A/B passes.
2. **Substrate artifacts are shared read-only.** Alias tables, truth packs, `failure_events.db` are written once by owner, consumed by both lanes.
3. **Overnight = heavy compute.** Full corpus extraction, 400-query evals, bakeoffs. Never interactive.
4. **Daytime = iterate + QA.** Smoke tests, GUI smash, narrow A/Bs, truth-pack spot-checks.
5. **No touching the reverted dead patterns:** temporal full-400, metadata candidate injection, subtractive narrowing, broad free-form LLM counting.

---

## Wave Structure (14-day cadence to demo)

```
Wave 0 (tonight/Day 0)     → kickoff unblocks
Wave 1 (Days 1-3)          → substrate foundation
Wave 2 (Days 4-6)          → A/B on aggregation backend
Wave 3 (Days 7-10)         → expansion + GUI surface
Wave 4 (Days 11-14)        → demo hardening
```

Each wave ends with a QA gate, a handover doc, and a sanitize-before-push checkpoint.

---

## WAVE 0 — Kickoff (tonight + Day 0)

Purpose: unblock all lanes before the sprint properly begins. Everything here runs in parallel.

### Lane A (GPU 0, V2)
- [ ] Finalize current product P0s (query history + Advanced Top-K) if not already banked
- [ ] Smoke-test `aggregation_exact_10` against 85.75% baseline (no regression)
- [ ] Commit + sanitize + push to remote
- [ ] **Overnight run:** baseline 400-query GPT-4o eval on V2 (headline preservation check)

### Lane B (GPU 1, V2_Dev)
- [ ] Canary `--full-reindex` on verified recovery subset (per STATE_SNAPSHOT blocker)
- [ ] If canary passes: run full verified recovery subset; post export path
- [ ] **Overnight run:** recovery-subset export + mapped 14-query eval

### R3 — Slice 1 of aggregation sprint
- [ ] Build `failure_analysis_truth_pack_nexion_isto_2026-04-19.json` (≥20 audited Q1/Q2/Q3-style questions)
- [ ] Produce `nexion_isto_failure_event_source_map.md` (top 3-5 source families)
- [ ] Per-family schema fingerprint (column headers, row layout)

### Researcher-Web — parallel literature lane
- [ ] 2026 deep-dive research note on:
  - failure-event NER (FMEA-augmented NER patterns)
  - text-to-SQL routing for aggregation intent (CSR-RAG, SAG, TableRAG)
  - installed-base / denominator sourcing in military logistics records
  - window-function ranking in SQL-over-extracted-corpus systems
- [ ] Output: `research_notes/aggregation_research_deep_dive_2026-04-19.md`
- [ ] Web-sourced best-practice schema for `failure_events` table (validate my proposal)

### Coder-Free — unblock Slice 2 alias tables
- [ ] From `source_metadata` (93,636 rows) extract:
  - canonical system list (NEXION, ISTO, + any others ≥100 rows)
  - canonical site list (Djibouti + top 20 sites)
- [ ] Seed `config/canonical_aliases.yaml` with stub entries
- [ ] Year canonicalizer unit tests (10 cases: FY24, CY2024, 2024, 04/2024, Q1-2024, etc.)

### QA
- [ ] Gate Lane A product P0 push before it goes to remote
- [ ] Gate Lane B canary export — does file count + chunk count + vector count match expectation?

**Wave 0 handover:** `~/.claude/handover/wave0_kickoff_2026-04-18_EOD.md`

---

## WAVE 1 — Substrate Foundation (Days 1-3)

Purpose: populate the deterministic failure-event substrate on one pilot family. Prove the pattern works before expanding.

### Lane A (GPU 0, V2)
- [ ] Merge Coder-Free's aggregation_router scaffold into V2 (stub backend; returns UNSUPPORTED if substrate missing)
- [ ] Wire router into `src/query/pipeline.py` as AGGREGATION branch before vector path
- [ ] Add `rows_matched`, `substrate_coverage_pct` return fields
- [ ] Daily smoke: 85.75% baseline must hold with aggregation branch disabled
- [ ] **Overnight Day 2:** V2 baseline eval with aggregation branch wired but no substrate (proves no regression)
- [ ] **Overnight Day 3:** V2 eval with stub substrate (proves UNSUPPORTED path works)

### Lane B (GPU 1, V2_Dev)
- [ ] Build failure-event extractor for 1 pilot family (highest-yield from R3's Slice 1 map)
- [ ] Regex-first approach; path-derived fallback for site/system when row lacks fields
- [ ] Write rows to `data/substrate/failure_events.db` (idempotent)
- [ ] **Overnight Day 2:** run extractor on pilot family across full corpus
- [ ] **Overnight Day 3:** QA's extractor-vs-truth-pack spot-check run (GPU 1 inference)

### R3
- [ ] Audit extractor output against truth pack; compute precision + recall
- [ ] Flag extraction failures by failure mode (missing part_number, missing date, etc.)
- [ ] Produce `failure_extractor_pilot_audit_2026-04-21.md`
- [ ] Start `installed_base_source_mapping.md` research (for Slice 6 denominator)

### Researcher-Web
- [ ] Validate aggregation router intent patterns against 2026 published taxonomies
- [ ] Research deterministic-vs-bounded-count product UX patterns (how enterprise tools surface this)
- [ ] Research query-decomposition patterns for multi-part questions (e.g., "top 5 each year for 7 years" = 7 queries or 1 windowed?)
- [ ] Output: `research_notes/aggregation_ux_patterns_2026-04-20.md`

### Coder-Free
- [ ] Build `src/query/aggregation_router.py` (pattern matcher, stub)
- [ ] Build `src/query/sql_adapter.py` with 3 parameterized templates:
  - `top_n_by_group`, `count_by_filter`, `count_by_group_per_year`
- [ ] Unit tests against an empty DB (must return UNSUPPORTED, not crash)
- [ ] Push PR to Lane A for integration review (do NOT merge unreviewed into V2)

### QA
- [ ] Gate extractor precision ≥ 0.90 before Lane B expands
- [ ] Gate SQL adapter unit-test coverage
- [ ] Produce `wave1_qa_report_2026-04-21.md`

**Wave 1 handover:** `wave1_foundation_complete_2026-04-21_EOD.md`
**Decision point:** if extractor precision < 0.90 on pilot family, Lane B pauses expansion; R3 debugs extraction; plan slips 1 day.

---

## WAVE 2 — A/B on Aggregation Backend (Days 4-6)

Purpose: prove the deterministic backend beats free-form RAG on failure-aggregation questions. This is the **signature A/B** of the sprint.

### The A/B Design
- **Both lanes run the SAME 50-question failure-analysis eval pack** (from R3's expanded truth pack)
- **Lane A (V2):** aggregation router ENABLED, deterministic backend routes failure questions through SQL
- **Lane B (V2_Dev):** aggregation router DISABLED, standard RAG path handles failure questions
- **Metric:** exact-count pass rate, off-by-one rate, UNSUPPORTED rate, evidence-attribution coverage
- **Expected outcome:** Lane A crushes Lane B on exact-count; Lane B may still win on qualitative narrative quality

### Lane A (GPU 0, V2)
- [ ] Merge aggregation backend (Slice 4 complete from Wave 1)
- [ ] Wire evidence linker stub — return 1-3 chunk IDs per aggregation row
- [ ] Add `aggregation_trace.jsonl` output to eval runner
- [ ] **Day 4 afternoon:** run 50-question failure-analysis eval (agg ENABLED) on V2
- [ ] **Overnight Day 4:** full 400-query regression eval with aggregation branch live (headline preservation)
- [ ] **Overnight Day 5:** 500-query stress A/B (enabled vs disabled within V2 via feature flag)

### Lane B (GPU 1, V2_Dev)
- [ ] Expand extractor to families 2-3 from R3's source map (if Wave 1 passed precision gate)
- [ ] Populate `failure_events.db` with expanded substrate
- [ ] Keep aggregation router DISABLED on V2_Dev (control arm)
- [ ] **Day 4 afternoon:** run 50-question failure-analysis eval (agg DISABLED) on V2_Dev
- [ ] **Overnight Day 5:** full-corpus extraction pass across all families covered so far
- [ ] **Overnight Day 6:** installed-base extractor pilot (Slice 6 kickoff)

### R3
- [ ] Expand truth pack: 20 → 50 audited questions (Q1/Q2/Q3-style + variants)
- [ ] Audit A/B output on Day 5; produce `aggregation_ab_audit_2026-04-23.md`
  - per-question winner, evidence quality, numeric error
- [ ] Identify failure modes on Lane A side (where did deterministic backend return wrong counts?)
- [ ] Start installed-base source audit (Slice 6)

### Researcher-Web
- [ ] Research window-function ranking best practices for "top N per year × 7 years" (Q3 shape)
- [ ] Survey 2026 published evidence-attribution benchmarks; pick one to adopt for aggregation lane
- [ ] Sanity-check our precision/recall numbers against published failure-extraction benchmarks
- [ ] Output: `research_notes/aggregation_benchmark_alignment_2026-04-23.md`

### Coder-Free
- [ ] Build `src/query/evidence_linker.py` (maps aggregation row → source chunks)
- [ ] Build determinism test harness: same question × same state × 10 runs = same answer
- [ ] PR to Lane A for Wave 3 GUI work

### QA
- [ ] Gate A/B results: `aggregation_backend_accuracy.md` with exact-count pass rate, off-by-one, UNSUPPORTED, evidence coverage
- [ ] Gate 400-query headline preservation (85.75% must hold)
- [ ] Verify no provider endpoint strings leaked in traces (sanitizer check)
- [ ] Produce `wave2_qa_report_2026-04-24.md`

**Wave 2 handover:** `wave2_ab_complete_2026-04-24_EOD.md`
**Decision point:** if Lane A doesn't beat Lane B on exact-count by ≥30 percentage points, debug the backend before Wave 3 GUI work. Root cause before proceeding.

---

## WAVE 3 — Expansion + GUI Surface (Days 7-10)

Purpose: make the aggregation capability visible to a demo operator, expand substrate coverage, lock in determinism.

### Lane A (GPU 0, V2)
- [ ] Integrate Slice 5 GUI aggregation surface:
  - confidence tier badge (GREEN/YELLOW/RED)
  - ranked result table with part_number, count, rank, evidence chunk link
  - "Deterministic backend count" label
  - expandable evidence panel with source chunks
- [ ] Wire LLM narration path — takes deterministic rows, narrates, never computes counts
- [ ] Add "Rerun this query" button (for demo determinism proof)
- [ ] **Overnight Day 7:** GUI smash regression (existing features still work)
- [ ] **Overnight Day 8:** full 400-query + 50-question aggregation combined eval
- [ ] **Overnight Day 9:** latency profile — aggregation questions must be <10s wall clock

### Lane B (GPU 1, V2_Dev)
- [ ] Extend extractor to remaining families from R3's source map (5+ families total)
- [ ] Full-corpus extraction pass → refreshed `failure_events.db`
- [ ] Begin installed-base extractor (Slice 6) — if substrate sources are mapped
- [ ] **Overnight Day 7:** full multi-family extraction
- [ ] **Overnight Day 8:** installed-base extraction pilot
- [ ] **Overnight Day 9:** mirror final substrate to V2 as gold copy

### R3
- [ ] Expand truth pack to 100+ questions (broader failure scenarios, more systems)
- [ ] Ship `aggregation_demo_pack.md` — 10 GREEN demo questions with exact expected outputs
- [ ] Ship `aggregation_failure_mode_catalog.md` — where the backend fails + mitigations
- [ ] Start installed-base coverage audit (which years/parts/sites are populated?)

### Researcher-Web
- [ ] Competitive analysis: how do Palantir, Oracle, IBM Maximo surface grouped-aggregation answers in their UIs?
- [ ] Risk analysis: demo-day failure modes for aggregation questions (what could go wrong on stage?)
- [ ] Output: `research_notes/demo_aggregation_risk_matrix_2026-04-27.md`

### Coder-Free
- [ ] Build install script for aggregation substrate on workstation laptop (the demo machine)
- [ ] Build `aggregation_smoke_test.py` — 10 questions, pass/fail, runs in <30s
- [ ] QA workbench integration: aggregation-specific tab showing substrate coverage stats

### QA
- [ ] Gate GUI end-to-end: operator types Q1, Q2, Q3 → correct deterministic answers surface with evidence
- [ ] Run determinism test: each demo question × 10 runs = identical answer
- [ ] Latency gate: aggregation questions <10s p50
- [ ] Gate install script on clean .venv on workstation laptop
- [ ] Produce `wave3_qa_report_2026-04-27.md`

**Wave 3 handover:** `wave3_expansion_complete_2026-04-27_EOD.md`
**Decision point:** if installed-base substrate is <50% coverage for Q3, Q3 locks at YELLOW for demo. Not a blocker — still a strong answer.

---

## WAVE 4 — Demo Hardening (Days 11-14)

Purpose: rehearse, harden, backup, polish. No new features after Day 11.

### Lane A (GPU 0, V2)
- [ ] Full demo rehearsal on V2: 20 demo questions (retrieval + aggregation mixed)
- [ ] Latency tuning — any question >8s gets investigated
- [ ] Error handling: network blip, substrate empty, LLM timeout — all graceful
- [ ] **Overnight Day 11:** demo-pack dry run × 3 identical iterations (determinism proof)
- [ ] **Overnight Day 13:** 400-query + 100-question aggregation FINAL eval

### Lane B (GPU 1, V2_Dev)
- [ ] Mirror final V2 substrate to V2_Dev (backup demo machine)
- [ ] V2_Dev becomes cold backup — boots to identical state as V2
- [ ] Final substrate hash verification (both lanes: same `failure_events.db` SHA)
- [ ] **Overnight Day 11:** parity eval — both lanes same questions same results
- [ ] **Overnight Day 12:** stress test — 500 queries in 30 min on V2_Dev

### R3
- [ ] Finalize `aggregation_demo_pack.md` — GREEN-only, 8-10 questions
- [ ] Rehearse ground-truth one more pass; fix any truth-pack drift
- [ ] Ship `demo_day_runbook.md` — per-question fallback narration, recovery steps

### Researcher-Web
- [ ] Pitch polish: competitive positioning slide (how our deterministic approach beats free-form RAG competitors)
- [ ] Cite industry validation (2026 literature) for the SAG approach
- [ ] Output: `research_notes/demo_pitch_citations_2026-04-29.md`

### Coder-Free
- [ ] Final install script pass on workstation laptop (oldest-safe waiver versions)
- [ ] Pre-flight checklist script: validates substrate exists, SHA matches, CUDA active, config correct
- [ ] Printed operator runbook (PDF)

### QA
- [ ] Full dress rehearsal on workstation laptop (demo machine)
- [ ] Audience simulation — 3 non-technical viewers smash the GUI
- [ ] Final sanitizer pass on all pushed artifacts (no endpoint leaks)
- [ ] Produce `wave4_demo_ready_report_2026-05-01.md`

**Wave 4 handover:** `demo_ready_2026-05-01_EOD.md`

---

## Parallelization Map

```
TIMELINE       Lane A (GPU 0)   Lane B (GPU 1)   R3             Researcher      Coder-Free        QA
────────────── ──────────────── ──────────────── ────────────── ────────────── ────────────────── ──────
Wave 0 night   GPT-4o 400 eval  Recovery canary  Truth pack v1  Lit deep dive  Alias table seed   gate
Wave 1 Day 1   Router stub      Extractor build  Source map     UX patterns    SQL adapter        —
Wave 1 Day 2   Wire router      Extractor run    Extract audit  Benchmark val. Adapter tests      extract P/R
Wave 1 Day 3   Baseline parity  Spot-check run   Install-base   Query decomp   Evidence linker    gate adapter
Wave 2 Day 4   Agg A arm eval   Agg B arm eval   Audit A/B      Window-fn res. Determinism harn.  A/B audit
Wave 2 Day 5   400+stress       Multi-family ex. TP → 50 Q      Bench alignment PR evidence linker 400 gate
Wave 2 Day 6   Feature flag AB  Install-base pilot Fail-mode cat Risk matrix  GUI stub           agg gate
Wave 3 Day 7   GUI tier surface Multi-family run  TP → 100 Q    Competitive   Install script     GUI gate
Wave 3 Day 8   LLM narration    Install-base ext. Demo pack v1  Demo risk mtx Smoke test         determinism
Wave 3 Day 9   Latency profile  Mirror substrate  Install cov.  Evidence atbn QA tab integration  latency
Wave 3 Day 10  GUI polish       Substrate freeze  Demo pack v2  Pitch prep    Preflight script   wave3 QA
Wave 4 Day 11  Rehearsal v1     Parity eval       Runbook       —             Install final      dress 1
Wave 4 Day 12  Error handling   Stress 500 q      TP final      —             Operator doc       audience sim
Wave 4 Day 13  Final 400 eval   Cold backup       —             —             —                 sanitizer
Wave 4 Day 14  DEMO DAY         backup hot-swap   live support  live support  live support       gate
```

---

## Overnight Run Discipline

| Night | Lane A run | Lane B run | Cross-check |
|-------|-----------|-----------|-------------|
| Wave 0 → 1 | GPT-4o 400 eval | Recovery canary export | headline preserved |
| Wave 1 Day 2 | Router wired no substrate (baseline) | Full-corpus pilot extraction | no regression + extraction yield |
| Wave 1 Day 3 | Stub substrate (UNSUPPORTED path) | Extractor spot-check run | UNSUPPORTED works + P/R ≥ 0.90 |
| Wave 2 Day 4 | Agg ENABLED 400+50 | Agg DISABLED 50 | A/B diff > 30 pts on exact-count |
| Wave 2 Day 5 | 500 stress + feature flag AB | Multi-family extraction | no crashes + new substrate rows |
| Wave 2 Day 6 | (rest / short eval) | Installed-base pilot | denominator mapping evidence |
| Wave 3 Day 7 | GUI regression smash | Multi-family full extraction | GUI stable + refreshed substrate |
| Wave 3 Day 8 | 400 + 100 combined | Installed-base extraction | headline + Q3 coverage |
| Wave 3 Day 9 | Latency profile | Mirror V2 substrate to V2_Dev | <10s + SHA match |
| Wave 4 Day 11 | Demo pack × 3 (determinism) | Parity eval | identical outputs × both lanes |
| Wave 4 Day 12 | Error-injection rehearsal | Stress 500 q | graceful degradation |
| Wave 4 Day 13 | Final 400 eval | Cold-backup boot test | headline + hot-swap < 2 min |

---

## Rules of the Road

### Non-Negotiables
- **Every merge requires QA gate.** No merging to V2 main without a signed QA report for that slice.
- **Headline (85.75% PASS) never regresses.** If any A/B drops headline by >1%, the change is reverted, root-caused, retried.
- **Sanitize before push.** Commercial endpoint strings, NVIDIA workstation GPU refs, secrets — zero tolerance.
- **Hash everything.** Substrate DBs, truth packs, eval outputs all get SHA256 logged in their audit trail.
- **Determinism is a feature.** Same question × same state × same answer, 10 runs, always.

### Signals to Escalate (halt + replan)
- Extractor precision < 0.85 on pilot family — R3 debugs, Lane B pauses
- Any A/B regresses headline > 1% — revert + root-cause in ≤ 24h
- Installed-base coverage < 30% by Wave 3 end — Q3 demotes to YELLOW + refocus
- Any lane's overnight job crashes 2 nights in row — infrastructure review before more overnight runs
- GUI introduces latency > 12s p50 on aggregation — Coder-Free joins Lane A for tuning

### Explicit Do-Not
- Do NOT re-open temporal full-400 lane
- Do NOT retry metadata candidate injection
- Do NOT try subtractive metadata narrowing
- Do NOT retrain any model in this sprint (extraction + SQL only)
- Do NOT expand corpus import (recovery subset only, if at all)
- Do NOT let LLM compute any count — ever — in the aggregation path

---

## Daily Cadence

### Morning (30 min)
- War room board post: what ran overnight, what broke, what's ready for QA
- Each agent claims one task from wave backlog
- Jeremy reviews + dispatches

### Midday (15 min)
- Quick sync: any blockers? Any lane-owner conflicts?
- QA ships gates for morning's completed work

### Evening (30 min)
- Handover doc updated (`~/.claude/handover/<agent>_<date>.md`)
- Overnight runs kicked off
- Sanitize + push sweep on anything commit-ready

---

## Success Metrics (Wave-Level)

| Wave | Metric | Pass threshold |
|------|--------|---------------|
| 0 | Kickoff unblocks | all 5 actors have work; baseline eval runs |
| 1 | Substrate foundation | 1 family extracted with P ≥ 0.90, R ≥ 0.70 |
| 2 | A/B on aggregation | Lane A exact-count pass ≥ 30pts above Lane B |
| 3 | Expansion + GUI | 5+ families in substrate; GUI shows tier + evidence |
| 4 | Demo hardening | 10 GREEN demo questions; determinism 10/10; latency <10s |

### Demo-Day Definition of Done
- 10 GREEN demo questions, all rehearsed, all deterministic
- Q1 + Q2 return GREEN with ranked table + evidence on demo machine
- Q3 returns GREEN or YELLOW (explicit tier) — never red-in-disguise
- Cold-backup lane (V2_Dev) can hot-swap in < 2 min if demo machine fails
- Operator runbook printed; fallback narratives memorized
- Sanitizer clean; no provider endpoint leaks in any pushed artifact

---

## Files This Plan Produces (13 artifacts)

1. `failure_analysis_truth_pack_nexion_isto_2026-04-19.json` (R3, Wave 0)
2. `nexion_isto_failure_event_source_map.md` (R3, Wave 0)
3. `config/canonical_aliases.yaml` (Coder-Free, Wave 0 → 1)
4. `data/substrate/failure_events.db` (Lane B, Wave 1 → 3)
5. `data/substrate/installed_base.db` (Lane B, Wave 2 → 3)
6. `src/query/aggregation_router.py` (Coder-Free, Wave 1)
7. `src/query/sql_adapter.py` (Coder-Free, Wave 1)
8. `src/query/evidence_linker.py` (Coder-Free, Wave 2)
9. `src/extraction/failure_event_extractor.py` (Lane B, Wave 1 → 3)
10. `src/gui/panels/aggregation_panel.py` (Lane A, Wave 3)
11. `aggregation_backend_accuracy.md` (QA, Wave 2)
12. `aggregation_demo_pack.md` (R3, Wave 3)
13. `demo_day_runbook.md` (R3, Wave 4)

Plus: 4 wave handover docs, 4 QA reports, 4 research notes.

---

Jeremy Randall | CoPilot+ | HybridRAG_V2 | 2026-04-18 MDT
