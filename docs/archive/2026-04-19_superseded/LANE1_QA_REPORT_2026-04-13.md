# Lane 1 QA Report — 2026-04-13

## Verdict

**FAIL**

Lane 1 does **not** clear QA in its current state. The main failure is evidence hygiene, not the narrow unit-test surface:

- the required Lane 1 400-query result JSON/report are still missing
- the live eval command is pointed at the wrong config by omission
- the active eval surface is not isolated to the repo-local `.venv`
- two live eval processes are targeting the same output artifact path

That combination makes the lane result untrustworthy even before score comparison.

## Hard Fails

1. **Required result artifacts are missing**
   - Missing at QA time:
     - `docs/production_eval_results_lane1_retrieval_router_400_2026-04-13.json`
     - `docs/PRODUCTION_EVAL_RESULTS_LANE1_RETRIEVAL_ROUTER_400_2026-04-13.md`
     - `docs/COMPARE_LANE1_vs_POST_CDRL_2026-04-13.md`
   - This blocks the required baseline comparison against `docs/production_eval_results_post_cdrl_path_patch_400_2026-04-13.json`.

2. **Wrong store/config launch surface**
   - The active Lane 1 eval command line does **not** pass `--config`.
   - `scripts/run_production_eval.py` defaults to `config/config.yaml`.
   - The QA playbook requires the clean Tier 1 baseline, not default `data/index`.
   - Current default config:
     - `config/config.yaml` -> `paths.entity_db: data/index/entities.sqlite3`
   - Required clean baseline config:
     - `config/config.tier1_clean_2026-04-13.yaml` -> `paths.entity_db: data/index/clean/tier1_clean_20260413/entities.sqlite3`

3. **Repo-local venv rule is violated in the live eval surface**
   - Two active `run_production_eval.py` processes were present.
   - One uses the repo-local interpreter:
     - `C:\HybridRAG_V2\.venv\Scripts\python.exe`
   - One uses system Python:
     - `{USER_HOME}\AppData\Local\Programs\Python\Python312\python.exe`
   - The lane prompt explicitly requires the repo-local `.venv`.

4. **Output trust is compromised by duplicate concurrent writers**
   - Both active eval processes target:
     - `docs/production_eval_results_lane1_retrieval_router_400_2026-04-13.json`
     - `docs/PRODUCTION_EVAL_RESULTS_LANE1_RETRIEVAL_ROUTER_400_2026-04-13.md`
   - Even if artifacts appear later, this launch state is not trustworthy without a clean rerun.

## Checks That Passed

1. **No benchmark pack edits detected**
   - `git diff --stat -- tests/golden_eval/` returned no changes.

2. **Targeted Lane 1 tests passed**
   - `tests/test_candidate_pool_wiring.py`: `22 passed`
   - `pytest -q -k "router or retriever or path_hint or visit_condition"`: `49 passed, 248 deselected`

3. **Diff surface broadly matches the intended Lane 1 area**
   - Retrieval/router files:
     - `src/query/pipeline.py`
     - `src/query/query_router.py`
     - `src/query/reranker.py`
     - `src/query/vector_retriever.py`
     - `src/store/lance_store.py`
     - `tests/test_candidate_pool_wiring.py`
   - Shared-tree spillover also shows:
     - `src/store/relationship_store.py`
   - I did **not** see benchmark-pack edits or GUI/installer changes in the inspected Lane 1 diff surface.

## Conditional Concerns

1. **No score delta can be certified**
   - Baseline to beat remains:
     - `PASS 226/400`
     - `routing_correct 298/400`
   - Without a finished clean-config Lane 1 artifact, PASS, routing, latency, and query-level deltas are unproven.

2. **Off-stage false lifts cannot be audited yet**
   - The playbook requires checks on:
     - `PQ-148`
     - `PQ-150`
     - `PQ-263`
     - `PQ-264`
     - `PQ-380`
     - `PQ-381`
     - `PQ-492`
     - `PQ-500`
   - Current QA cannot certify that these remained safely non-promoted.

3. **DID/reference/archive top-1 pollution is not empirically cleared**
   - The code adds stronger path prioritization and archive/reference penalties.
   - That is directionally good.
   - But the required 400-pack artifact is missing, so no real top-1 audit exists yet on PASS rows.

4. **The lane is still path-heuristic heavy**
   - Static read suggests useful improvements, but still mainly through path heuristics and regex hints rather than real typed metadata.
   - This matches the reboot warning about overfitting to literal path substrings.

## Top Lifts Expected From The Diff

- `src/query/pipeline.py`
  - `QueryPipeline._prioritize_visit_condition_results` now sorts in the intended direction and has passing coverage for curated field-visit preference.
- `src/query/query_router.py`
  - adds purchase-order expansion
  - adds document-location routing guard
  - adds narrow temporal shipment routing override
- `src/query/vector_retriever.py`
  - expands CDRL/A027/contract/site/date/PO path-hint groups
  - adds breadth handling for cross-reference style queries
  - adds path-hit prioritization to demote archive/reference material
- `src/store/lance_store.py`
  - metadata path search now prefers distinct `source_path` hits and head chunks before broader tail fallback

## Top Risks / Regressions

- wrong config for the live eval
- non-venv interpreter in the active eval surface
- duplicate concurrent writers to the same result artifact
- still no empirical proof on field-visit rows, off-stage rows, DID/reference/archive top-1 cleanliness, or latency delta
- heuristic/path-substring overfit remains a real risk even if the final score improves

## Commands Run

```powershell
git -C C:\HybridRAG_V2 status --short
git -C C:\HybridRAG_V2 branch --show-current
Get-Content C:\HybridRAG_V2\docs\LANE1_QA_PLAYBOOK_2026-04-13.md
Get-Content C:\HybridRAG_V2\docs\QUERIES_TO_AVOID_FOR_DEMO_2026-04-13.md
git -C C:\HybridRAG_V2 diff --stat -- src/query/ src/store/lance_store.py src/store/relationship_store.py tests/test_candidate_pool_wiring.py
git -C C:\HybridRAG_V2 diff --stat -- tests/golden_eval/
Test-Path C:\HybridRAG_V2\docs\production_eval_results_lane1_retrieval_router_400_2026-04-13.json
Test-Path C:\HybridRAG_V2\docs\PRODUCTION_EVAL_RESULTS_LANE1_RETRIEVAL_ROUTER_400_2026-04-13.md
Test-Path C:\HybridRAG_V2\docs\COMPARE_LANE1_vs_POST_CDRL_2026-04-13.md
Get-Content C:\HybridRAG_V2\docs\REBOOT_HANDOVER_2026-04-13.md | Select-Object -Index (130..175)
Get-Content C:\HybridRAG_V2\docs\REBOOT_HANDOVER_2026-04-13.md | Select-Object -Index (64..90)
Get-Content C:\HybridRAG_V2\scripts\run_production_eval.py | Select-Object -First 220
Get-Content C:\HybridRAG_V2\scripts\run_production_eval.py | Select-Object -Index (900..1010)
Get-Content C:\HybridRAG_V2\config\config.yaml | Select-Object -First 60
Get-Content C:\HybridRAG_V2\config\config.tier1_clean_2026-04-13.yaml | Select-Object -First 60
C:\HybridRAG_V2\.venv\Scripts\python.exe -m pytest -q C:\HybridRAG_V2\tests\test_candidate_pool_wiring.py
C:\HybridRAG_V2\.venv\Scripts\python.exe -m pytest -q -k "router or retriever or path_hint or visit_condition"
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'run_production_eval.py' } | Select-Object ProcessId,CommandLine | Format-List
Get-Process -Id 62800,48140 | Select-Object Id,ProcessName,StartTime,CPU,Path | Format-Table -AutoSize
nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits
```

## Files Touched

### Lane 1 diff surface inspected

- `src/query/pipeline.py`
- `src/query/query_router.py`
- `src/query/reranker.py`
- `src/query/vector_retriever.py`
- `src/store/lance_store.py`
- `src/store/relationship_store.py`
- `tests/test_candidate_pool_wiring.py`

### Files written by QA

- `docs/LANE1_QA_REPORT_2026-04-13.md`

## Coordinator Read

Reject the current Lane 1 handoff as a final QA pass.

The code changes look directionally plausible and the unit-test surface is green, but the evidence package is not valid yet. The next acceptable step is a **single clean rerun** of Lane 1 with:

1. repo-local `.venv`
2. explicit `--config config/config.tier1_clean_2026-04-13.yaml`
3. one writer only
4. fresh compare report against `docs/production_eval_results_post_cdrl_path_patch_400_2026-04-13.json`

Until that exists, Lane 1 should not be marked PASS or merged into demo-readiness claims.
