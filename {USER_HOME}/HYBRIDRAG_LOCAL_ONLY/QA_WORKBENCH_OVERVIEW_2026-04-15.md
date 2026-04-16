# QA Workbench Overview

Rendered: 2026-04-15 23:06
Repo root: `C:\HybridRAG_V2`
Local-only root: `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY`

This is the management-readable state of every live benchmark lane.
It is a read-only view over artifacts that live elsewhere.

---

## 1. Latest certified baseline

(not yet available -- expected at `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\BASELINE_PACK_MANIFEST_2026-04-15.md`)

## 2. Hardtail summary

(not yet available -- expected at `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\HARDTAIL_TRAINING40_HEAD_TO_HEAD_SCOREBOARD_2026-04-15.md`)

## 3. Count benchmark status

- Frozen target manifest: `C:\HybridRAG_V2\tests\golden_eval\count_benchmark_targets_2026-04-15.json`
- Target count: **15** (v1 high-specificity)
- Latest live run result: `C:\HybridRAG_V2\tests\golden_eval\results\count_benchmark\count_benchmark_20260415_220246.md` (updated 2026-04-15 22:02)
- Run note: `C:\HybridRAG_V2\docs\COUNT_BENCHMARK_RUN_NOTE_2026-04-15.md`
- Status: Ready for QA (Researcher shipped 2026-04-15: pytest 8 passed, live run 7/7 frozen-expectation verification)

## 4. Aggregation benchmark status

- Runner: `C:\HybridRAG_V2\scripts\run_aggregation_benchmark_2026_04_15.py`
- Frozen seed manifest: `C:\HybridRAG_V2\tests\aggregation_benchmark\aggregation_seed_manifest_2026-04-15.json` (items: 12), id: aggregation_benchmark_2026-04-15
- Run note: `C:\HybridRAG_V2\tests\aggregation_benchmark\AGGREGATION_BENCHMARK_RUN_NOTE_2026-04-15.md`
- Status: Ready for QA (reviewer validated-on-disk 2026-04-15: pytest 9 passed, runner Gate PASS 12/12)

## 5. Regression status

- Latest production eval file: `C:\HybridRAG_V2\docs\production_eval_results_gui_2026-04-15_230536.json`
- run_id: 20260416_050553
- Last updated: 2026-04-15 23:05
- Pass / Partial / Miss: 0 / 0 / 0
- Total queries: ?
- Routing correct: 0
- Wall-clock latency: p50 0 ms / p95 0 ms

## 6. Strongest / weakest areas

- by persona: (not present in payload)
- by query type: (not present in payload)

## 7. Artifact links

### Baseline package (priority 2, QA-PASSED)
- `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\CERTIFIED_BASELINE_PACKAGE_RECOMMENDATION_2026-04-15.md`
- `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\BASELINE_PACK_MANIFEST_2026-04-15.md`
- `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\BASELINE_SCORING_CONTRACT_2026-04-15.md`
- `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\BENCHMARK_LEDGER_TEMPLATE_2026-04-15.md`
- `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\CORPUS_COUNT_RECONCILIATION_2026-04-15.md`

### Hardtail training-40
- `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\HARDTAIL_TRAINING40_HEAD_TO_HEAD_SCOREBOARD_2026-04-15.md`
- `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\provider_runs\hardtail_v1\CoPilot+\2026-04-15_run_03_training40\extraction_manifest.json`
- `{USER_HOME}\HYBRIDRAG_LOCAL_ONLY\provider_runs\hardtail_v1\CoPilot+\2026-04-15_run_02_training40\extraction_manifest.json`

### Count benchmark
- runner: `C:\HybridRAG_V2\scripts\count_benchmark.py`
- targets: `C:\HybridRAG_V2\tests\golden_eval\count_benchmark_targets_2026-04-15.json`
- results dir: `C:\HybridRAG_V2\tests\golden_eval\results\count_benchmark`
- run note: `C:\HybridRAG_V2\docs\COUNT_BENCHMARK_RUN_NOTE_2026-04-15.md`

### Aggregation benchmark
- runner: `C:\HybridRAG_V2\scripts\run_aggregation_benchmark_2026_04_15.py`
- seed manifest: `C:\HybridRAG_V2\tests\aggregation_benchmark\aggregation_seed_manifest_2026-04-15.json`
- run note: `C:\HybridRAG_V2\tests\aggregation_benchmark\AGGREGATION_BENCHMARK_RUN_NOTE_2026-04-15.md`

### Production eval docs directory
- `C:\HybridRAG_V2\docs`

---

Signed: CoPilot+ - HybridRAG_Educational / HYBRIDRAG_LOCAL_ONLY - 2026-04-15 MDT
