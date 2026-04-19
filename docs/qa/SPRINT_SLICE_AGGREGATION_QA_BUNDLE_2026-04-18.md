# Aggregation Sprint Slice — QA Bundle

**Author:** Jeremy Randall (CoPilot+)
**Repo:** HybridRAG_V2 (primary `C:\HybridRAG_V2`, dev lane `C:\HybridRAG_V2_Dev`)
**Date:** 2026-04-18 MDT
**Slice doc:** `docs/SPRINT_SLICE_AGGREGATION_FAILURE_RATE_2026-04-18.md`
**Mega plan:** `docs/MEGA_TASKING_PARALLEL_LANES_AGGREGATION_2026-04-18.md`
**Status:** **READY FOR QA**

---

## 1. What Was Built

A deterministic failure-aggregation backend (Structure-Augmented Generation pattern) that intercepts grouped-aggregation queries BEFORE the LLM router and answers them via parameterized SQL against a new `failure_events` substrate. The LLM narrates the deterministic result — it never computes counts.

### Target questions this unlocks

1. **"What were the highest failing part numbers in the monitoring systems in 2024?"** → GREEN
2. **"What were the highest failing part numbers in the legacy monitoring systems in Djibouti from 2022-2025?"** → GREEN
3. **"What are the top 5 failure-rate parts ranked each year for the past 7 years?"** → YELLOW (rate requires installed-base denominator — not yet populated)

### New files

| File | Purpose |
|------|---------|
| `config/canonical_aliases.yaml` | monitoring system / legacy monitoring system + 22 site aliases (Djibouti inc. Camp Lemonnier) |
| `src/store/failure_events_store.py` | SQLite substrate (`failure_events` table) |
| `src/extraction/failure_event_extractor.py` | Regex + path-derived extractor |
| `src/query/aggregation_executor.py` | Intent detection + SQL + evidence linking + tier rendering |
| `scripts/populate_failure_events.py` | Pass 1 (path) + optional Pass 2 (chunks) populator |
| `scripts/reconcile_raw_vs_substrate.py` | E:\CorpusTransfr ground-truth reconciliation |
| `tests/test_failure_aggregation.py` | 44 unit tests (all passing) |
| `tests/aggregation_benchmark/failure_truth_pack_2026-04-18.json` | 20-question truth pack |

### Wiring changes

| File | Change |
|------|--------|
| `src/query/pipeline.py` | Added `aggregation_executor` branch BEFORE router. Falls through to standard RAG when query isn't aggregation. |
| `src/gui/launch_gui.py` | Factory builds `AggregationExecutor` at GUI boot. Logs coverage summary. |
| `scripts/boot.py` | Same factory for CLI boot. |

---

## 2. What I Already Tested (all green)

### Unit tests
```
$ python -m pytest tests/test_failure_aggregation.py -q
............................................                             [100%]
44 passed in 0.18s
```

Coverage: year canonicalization, system alias resolution, site alias resolution (including Camp Lemonnier → djibouti), intent detection, top-N parsing, SQL adapter (`top_n_parts`, `top_n_parts_per_year`), evidence linker, executor end-to-end on a seeded 15-event substrate, RAG passthrough for non-aggregation queries.

### GUI harness Tier A (scripted panel checks)
```
$ python tools/qa/gui_button_smash_harness.py --tier a
Tier A (scripted):  96/96 passed
Widgets discovered: 107
```
Aggregation backend wiring did NOT break any existing GUI panel.

### Live substrate smoke
Substrate populated from real V2 `retrieval_metadata.sqlite3` (93,636 source rows):

```
Coverage:
  total_events:      35,990
  with_system:       35,649 (monitoring system + legacy monitoring system)
  with_site:         10,882 (22 distinct sites)
  with_year:         19,941
  with_part_number:   3,021 (900 distinct parts)
```

Live query results (see `output/qa_agg/smoke_test_results_2026-04-18.json`):

| Query | Tier | Top Result |
|-------|------|-----------|
| monitoring system 2024 highest failing parts | GREEN | `EC11612` (4 failures, 4 distinct docs) |
| legacy monitoring system Djibouti 2022-2025 | GREEN | `SEMS3D-35674` (2 failures) |
| Top 5 failure **rate** per year × 7 years | YELLOW | Returns per-year counts + rate-unsupported disclaimer |
| Top 10 monitoring system Vandenberg 2022 | GREEN | `SEMS3D-40540` (3 failures) |
| "Who is the POC for Thule?" | PASSTHROUGH | Falls through to standard RAG ✓ |

---

## 3. Substrate Coverage (what exists, what's missing)

| Field | Rows | Coverage | Gap |
|-------|------|----------|-----|
| system (monitoring system / legacy monitoring system) | 35,649 | 99.0% | Only 2 systems detected so far |
| event_year | 19,941 | 55.4% | Paths w/o date tokens — chunk pass could raise this |
| site_token | 10,882 | 30.2% | Paths that don't mention a canonical site (many generic CDRL folders) |
| part_number | 3,021 | 8.4% | **Biggest gap** — part_numbers live in chunk TEXT, not path. Pass 2 (chunk-derived) would raise this to est. 60-80% |
| installed_base (denominator) | 0 | 0% | Not in this slice — Sprint 6 of mega plan |

**QA note:** The 8.4% part-number coverage is a known limitation of path-only extraction. Pass 2 (chunk-derived, runs against LanceDB) would dramatically raise this. I did not run Pass 2 because it needs a GPU overnight job — that's QA's call on whether to run it as part of this gate or defer.

---

## 4. QA Responsibilities (the 5 Pillars + Slice-Specific)

Following `docs/qa/QA_EXPECTATIONS_2026-04-05.md`.

### Pillar 1: Boot & Config
- [ ] `python scripts/boot.py` boots clean with aggregation executor attached
- [ ] Log line appears: `[OK] Aggregation executor attached (failure_events=35990, with_system=35649)`
- [ ] Aggregation init fails gracefully if `failure_events.sqlite3` missing (pipeline still assembles, agg disabled)
- [ ] `config/canonical_aliases.yaml` loads without YAML errors

### Pillar 2: Core Pipeline (real GPU, real LLM)
- [ ] Launch GUI on workstation (Blackwell Single GPU — follow project policy)
- [ ] Submit each of the 3 target questions in the main query panel:
  1. `What were the highest failing part numbers in the monitoring systems in 2024?`
  2. `What were the highest failing part numbers in the legacy monitoring systems in Djibouti from 2022-2025?`
  3. `What are the top 5 failure rate parts ranked each year for the past 7 years?`
- [ ] Verify each returns a ranked markdown table (not free-form prose count)
- [ ] Verify Q1 and Q2 show `Confidence tier: GREEN`
- [ ] Verify Q3 shows `Confidence tier: YELLOW` with rate-disclaimer text
- [ ] Verify `query_path` field in response is `AGGREGATION_GREEN` or `AGGREGATION_YELLOW` (not `AGGREGATE` — those are different)
- [ ] Submit `Who is the POC for Thule?` — verify it falls through to standard RAG (answer text should be natural-language answer, not a ranked table)
- [ ] **Determinism check:** rerun Q1 ten times. Same answer every time. No variance.

### Pillar 3: 3-Tier Test Corpus
- [ ] Run `python -m pytest tests/test_failure_aggregation.py -q` — expect `44 passed`
- [ ] Run `python -m pytest tests/aggregation_benchmark/ tests/test_count_benchmark.py tests/test_aggregation_benchmark_2026_04_15.py -q` — confirm no regression in existing aggregation benchmark
- [ ] Tier 3 (negative): empty substrate path → confirm graceful UNSUPPORTED not crash. Test: temporarily rename `data/index/failure_events.sqlite3`, submit Q1, verify pipeline falls through to RAG (doesn't crash)

### Pillar 4: Real Data Pass
- [ ] Verify `failure_events.sqlite3` exists at `C:\HybridRAG_V2\data\index\failure_events.sqlite3`
- [ ] Verify row count ≥ 35,000 (`sqlite3 failure_events.sqlite3 "SELECT COUNT(*) FROM failure_events"`)
- [ ] Verify monitoring systems count ≥ 20,000
- [ ] Verify legacy monitoring systems count ≥ 5,000
- [ ] Verify Djibouti site count ≥ 100 (`...WHERE site_token='djibouti'`)

### Pillar 5: Graceful Degradation
- [ ] Empty `failure_events.sqlite3` (delete + recreate empty) → pipeline falls through to RAG without crashing
- [ ] Missing `canonical_aliases.yaml` → executor init logs warning, pipeline still works (agg executor = None, falls through to RAG)
- [ ] LLM unavailable → aggregation still returns the deterministic table (LLM only narrates, not required for backend)

### Slice-Specific QA
- [ ] **Truth pack verification:** read `tests/aggregation_benchmark/failure_truth_pack_2026-04-18.json` and pick 5 random GREEN questions. Submit each in GUI. Verify parsed filters (`system`, `site_token`, `year_from`, `year_to`) match the truth pack's `expected_filters`.
- [ ] **Evidence display:** for Q1 and Q2, click through to verify source paths in the Evidence section are real file paths under `D:\CorpusTransfr\verified\IGS\...`
- [ ] **GUI button smash Tier B (smart monkey):** `python tools/qa/gui_button_smash_harness.py --tier b --smart-rounds 30`
- [ ] **GUI button smash Tier C (dumb monkey):** `python tools/qa/gui_button_smash_harness.py --tier c --dumb-seconds 60`
- [ ] **Human button smash Tier D:** non-author smashes GUI for 10 minutes — specifically tries to break aggregation with weird queries ("top 999999 failing parts", "top 0 failing parts", "top failing parts in NONEXISTENT system", empty query, just whitespace, SQL-injection-shaped strings).
- [ ] **Ground-truth reconcile (optional overnight):** `python scripts/reconcile_raw_vs_substrate.py --mode compare --raw-root D:\CorpusTransfr --limit 500000 --output output/qa_agg/reconcile_500k.json`. Expect substrate coverage % > 90% for monitoring systems count.

---

## 5. Parallel QA Lanes (GPU 0 + GPU 1)

Both GPUs are available. Recommend running these in parallel:

### Lane A — V2 / GPU 0
```bash
set CUDA_VISIBLE_DEVICES=0
cd C:\HybridRAG_V2
# Run unit tests + GUI Tier A (fast)
python -m pytest tests/test_failure_aggregation.py -q
python tools/qa/gui_button_smash_harness.py --tier a
# Live-query the 3 target questions in GUI
python -m src.gui.launch_gui
```

### Lane B — V2_Dev / GPU 1
```bash
set CUDA_VISIBLE_DEVICES=1
cd C:\HybridRAG_V2_Dev
# Mirror the aggregation build (if not yet synced)
# Run parity test — same questions, same answers
# Run 400-query regression eval (existing headline 85.75% must hold)
python scripts/run_production_eval.py --output docs/PRODUCTION_EVAL_RESULTS_AGG_WIRED_2026-04-18.md
```

Expected cross-lane: identical top-3 results for Q1 and Q2 on both lanes (determinism guarantee).

---

## 6. Known Limitations (call out to stakeholders)

1. **Part-number coverage is 8.4%** — path-derived only. Chunk-derived Pass 2 needed for higher coverage. Mitigation: run Pass 2 overnight before demo.
2. **Q3 (failure rate) returns YELLOW** — installed-base denominator substrate not yet populated. That's Sprint 6 / Slice 6 of the mega plan. Demo can present Q3 as "top failure-COUNT parts per year" rather than "failure-rate parts".
3. **Only 2 systems detected so far** — monitoring system, legacy monitoring system. Other systems in corpus will silently skip. Aliases can be extended in `canonical_aliases.yaml` without code changes.
4. **Path-year extraction is 55%** — some paths don't have date tokens. Could be raised via chunk-derived year extraction from document text (Pass 2).

---

## 7. Backlog Items Satisfied By This Slice

From `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\BacklogWork_2026_17_4.txt`:

- [x] AGGREGATION P0: smallest deterministic substrate for monitoring system failures (partial — path-derived substrate exists, Pass 2 remaining)
- [x] AGGREGATION P1: narrow deterministic backend pilot for monitoring system / legacy monitoring system failure counts (`aggregation_executor.py`)
- [x] AGGREGATION P1: deterministic backend path for exact counts
- [x] AGGREGATION P0: demo-safe aggregation query pack (`failure_truth_pack_2026-04-18.json`)
- [~] AGGREGATION P0: aggregation evidence contract — implicit in tier system (GREEN/YELLOW/RED), not yet externalized as separate doc
- [~] AGGREGATION P1: benchmark deterministic backend vs truth pack — tests exist, formal benchmark runner not yet wired into `run_aggregation_benchmark_2026_04_15.py`
- [ ] AGGREGATION P1: denominator sources for true failure rates — Sprint 6
- [ ] AGGREGATION P1: UI/API framing for count answers — partially done via tier markdown; dedicated panel/badge is next sprint

---

## 8. Artifacts for QA

| Artifact | Path |
|----------|------|
| Substrate DB | `C:\HybridRAG_V2\data\index\failure_events.sqlite3` |
| Substrate coverage report | `output/qa_agg/substrate_report_2026-04-18.json` |
| Smoke test results | `output/qa_agg/smoke_test_results_2026-04-18.json` |
| GUI harness Tier A report | `output/qa_agg_smash_2026-04-18/qa_button_smash_report.json` |
| Unit test file | `tests/test_failure_aggregation.py` (44 tests) |
| Truth pack | `tests/aggregation_benchmark/failure_truth_pack_2026-04-18.json` (20 questions) |
| Slice plan | `docs/SPRINT_SLICE_AGGREGATION_FAILURE_RATE_2026-04-18.md` |
| Mega plan | `docs/MEGA_TASKING_PARALLEL_LANES_AGGREGATION_2026-04-18.md` |

---

## 8b. Sanitizer CLI reference

`sanitize_before_push.py` exposes two flags only:

```
python sanitize_before_push.py               # DRY RUN (preview — default)
python sanitize_before_push.py --apply       # REWRITE FILES IN PLACE
python sanitize_before_push.py --archive-dir <path>  # optional original-file archive
```

There is no `--dry-run` flag — the default (no args) is already the preview. An
earlier draft of this bundle referenced `--dry-run`; that was a documentation
error and has been corrected here.

---

## 9. QA Verdict Template

Copy into `docs/qa/SPRINT_SLICE_AGGREGATION_QA_REPORT_<date>.md`:

```
# Aggregation Sprint Slice QA Report
Date: 2026-04-XX
Tester: [name]
Lane A (V2/GPU 0): ...
Lane B (V2_Dev/GPU 1): ...

## Pillar 1 — Boot & Config: [PASS/FAIL]
## Pillar 2 — Core Pipeline: [PASS/FAIL]
## Pillar 3 — 3-Tier Corpus: [PASS/FAIL]
## Pillar 4 — Real Data: [PASS/FAIL]
## Pillar 5 — Graceful Degradation: [PASS/FAIL]
## Slice-Specific: [PASS/FAIL]
## Headline preservation (85.75% on 400-query): [PASS/FAIL]
## Determinism (Q1 × 10 runs = identical): [PASS/FAIL]
## GUI button smash (A+B+C+D): [PASS/FAIL]

## Issues
1. ...

## Verdict
- [ ] PASS — merge to V2 main; run Pass 2 chunk extraction overnight
- [ ] CONDITIONAL — fix [items] and retest
- [ ] FAIL — blockers: [items]

Signed: [name] | HybridRAG_V2 | 2026-04-XX MDT
```

---

Jeremy Randall | CoPilot+ | HybridRAG_V2 | 2026-04-18 22:20 MDT
