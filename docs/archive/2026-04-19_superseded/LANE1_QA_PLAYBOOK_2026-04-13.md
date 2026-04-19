# Lane 1 QA Playbook — 2026-04-13

**Purpose:** Fast, high-signal QA guide for the Lane 1 retrieval/router burn-down handoff.

**Scope:** Retrieval/router/rerank/path-hint changes only. This is not a GUI, installer, or structured-store review.

## Current Read

- Lane 1 appears to be a **path-heuristic + router-guard expansion**, not a typed-metadata schema/backfill lane.
- Expected touch points:
  - `src/query/query_router.py`
  - `src/query/vector_retriever.py`
  - `src/query/reranker.py`
  - `src/query/pipeline.py`
  - `src/store/lance_store.py`
  - `tests/test_candidate_pool_wiring.py`
- Expected output artifacts:
  - `docs/production_eval_results_lane1_retrieval_router_400_2026-04-13.json`
  - `docs/PRODUCTION_EVAL_RESULTS_LANE1_RETRIEVAL_ROUTER_400_2026-04-13.md`
  - compare delta vs `docs/production_eval_results_post_cdrl_path_patch_400_2026-04-13.json`

## Highest-Risk QA Targets

1. `src/query/pipeline.py`
   - ` _prioritize_visit_condition_results`
   - watch for regressions on field-visit / visit-condition rows
2. `src/query/vector_retriever.py`
   - path allowlist / denylist overfit
   - DID/reference/archive penalties
   - exact-ID handling for CDRL / IGSI / PO families
3. `src/store/lance_store.py`
   - `metadata_path_search` head/tail behavior
   - duplicate suppression by `source_path`
4. `src/query/reranker.py`
   - path-match side-channel promoting wrong top-1s
5. `src/query/query_router.py`
   - provider-agnostic guards
   - purchase-order and narrow shipment routing overrides

## Hard-Fail Conditions

- Any change under `tests/golden_eval/`
- Lane 1 result JSON missing, malformed, or not `400` queries
- Wrong baseline store/config
  - must point at clean Tier 1 baseline, not stale `data\index`
- `PASS < 226/400`
- `routing_correct < 298/400`
- net regression larger than a small handful of queries on the current PASS baseline
- off-stage aggregation-heavy queries suddenly turning into fake PASS wins
- field-visit demo-safe backups regressing
- top-1 PASS rows surfacing DID/reference/archive paths
- spillover into GUI, installer, or structured/tabular files outside lane scope

## Conditional-Pass Read

- Acceptable if:
  - PASS improves modestly over baseline
  - routing improves modestly over baseline
  - gains are concentrated in router/rerank/CDRL/PO/A027 families
  - no off-stage query flips
  - no field-visit regressions
  - latency increase is bounded and explained
- Treat as tech debt, not blocker, if:
  - the lift is still driven by path heuristics rather than true typed metadata

## First Query IDs To Spot-Check

### Router / intent

- `PQ-115`
- `PQ-116`
- `PQ-130`
- `PQ-165`
- `PQ-166`
- `PQ-344`
- `PQ-446`
- `PQ-448`
- `PQ-451`
- `PQ-453`

### Field-visit / pipeline-flip risk

- `PQ-130`
- `PQ-184`
- `PQ-185`
- `PQ-186`
- `PQ-296`

### CDRL / exact-ID / metadata-path

- `PQ-103`
- `PQ-109`
- `PQ-117`
- `PQ-120`

### Cyber / A027 rerank

- `PQ-190`
- `PQ-191`
- `PQ-193`
- `PQ-194`
- `PQ-195`
- `PQ-251`

### Keep-miss / anti-gaming checks

- `PQ-148`
- `PQ-150`
- `PQ-263`
- `PQ-264`
- `PQ-380`
- `PQ-381`
- `PQ-492`
- `PQ-500`

## Commands QA Should Run

### Surface and spillover

```powershell
git -C C:\HybridRAG_V2 status -s
git -C C:\HybridRAG_V2 diff --stat src/query/ src/store/lance_store.py src/store/relationship_store.py tests/test_candidate_pool_wiring.py
git -C C:\HybridRAG_V2 diff --stat tests/golden_eval/
```

### Lane 1 unit tests

```powershell
C:\HybridRAG_V2\.venv\Scripts\python.exe -m pytest -q tests\test_candidate_pool_wiring.py
C:\HybridRAG_V2\.venv\Scripts\python.exe -m pytest -q -k "router or retriever or path_hint or visit_condition"
```

### Result artifact sanity

```powershell
Test-Path C:\HybridRAG_V2\docs\production_eval_results_lane1_retrieval_router_400_2026-04-13.json
Test-Path C:\HybridRAG_V2\docs\PRODUCTION_EVAL_RESULTS_LANE1_RETRIEVAL_ROUTER_400_2026-04-13.md
```

### Compare against the correct baseline

```powershell
C:\HybridRAG_V2\.venv\Scripts\python.exe scripts\compare_production_eval_results.py `
  --baseline docs\production_eval_results_post_cdrl_path_patch_400_2026-04-13.json `
  --new docs\production_eval_results_lane1_retrieval_router_400_2026-04-13.json `
  --report-md docs\COMPARE_LANE1_vs_POST_CDRL_2026-04-13.md
```

## Required Evidence Package From Lane 1

- result JSON
- markdown report
- compare delta against post-CDRL baseline
- pytest results for the Lane 1 test surface
- changed-files list
- exact commands run
- off-stage query audit
- field-visit regression audit
- DID/reference/archive top-1 audit
- latency comparison versus current baseline

## Biggest Hidden Trap

The most likely miss in QA is the small logic flip in `src/query/pipeline.py` around visit-condition ranking. It is easy to overlook because the much larger `vector_retriever.py` diff draws attention, but a regression there can quietly damage strong field-engineering demo-safe queries even if total PASS goes up.

The second biggest trap is overfitting to literal Windows path substrings. That can make the current corpus look better while remaining fragile for future fresh exports or path-layout changes.
