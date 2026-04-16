# Lane 1 Latency Gate Follow-Up Evidence

Date: `2026-04-13`

## Scope

This follow-up only adjusted retrieval-side metadata path probing after the initial Lane 1 rerun showed a severe latency regression. The goal was to reduce the cost of narrow path-heavy lookups without unwinding the recall gains from the earlier retrieval/router burn-down work.

Canonical repo: `C:\HybridRAG_V2`

Rerun hardware: `physical GPU 1 -> cuda:0 (NVIDIA GeForce RTX 3090)`

## What Changed

- `src/store/lance_store.py`
  - Added `allow_tail_fallback` to `metadata_path_search(...)`.
  - Reduced the head probe budget from `max(desired * 8, 32)` to `max(desired * 4, 16)`.
  - Reduced the tail probe budget from `max(desired * 24, 96)` to `max(desired * 8, 32)`.
- `src/query/vector_retriever.py`
  - Passed the tail-fallback decision explicitly into `metadata_path_search(...)`.
  - Kept tail fallback enabled for true breadth queries such as multi-CDRL cross-tree prompts and A027 subtype aggregate prompts.
  - Disabled tail fallback when typed metadata already returned candidates.
  - Disabled tail fallback for narrow exact-ish PO, dated shipment, CAP, A027, and single-CDRL lookups.
- `tests/test_candidate_pool_wiring.py`
  - Added assertions that narrow shipment and typed CAP lookups disable path tail fallback.
  - Added assertions that true breadth queries keep path tail fallback enabled.

## Validation

- `.\.venv\Scripts\python.exe -m py_compile src\query\vector_retriever.py src\store\lance_store.py tests\test_candidate_pool_wiring.py`
- `.\.venv\Scripts\python.exe -m pytest tests\test_candidate_pool_wiring.py -q`
  - Result: `26 passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_query_router.py tests\test_retrieval_metadata_store.py -q`
  - Result: `34 passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_tier1_clean_store_audit.py -q`
  - Result: `3 passed`
- `.\.venv\Scripts\python.exe -m pytest tests\test_ingest_integrity.py -q`
  - Result: `10 passed`

## Delta vs Prior Lane 1 400 Rerun

Compared:

- baseline: `docs/production_eval_results_lane1_retrieval_router_400_2026-04-13.json`
- new: `docs/production_eval_results_lane1_latency_followup_400_2026-04-13.json`
- standard delta artifact: `docs/PRODUCTION_EVAL_DELTA_LANE1_LATENCY_FOLLOWUP_400_2026-04-13.md`

Headline delta:

- PASS: `249 -> 249` (`+0`)
- PARTIAL: `72 -> 71` (`-1`)
- MISS: `79 -> 80` (`+1`)
- routing correct: `301 -> 300` (`-1`)
- retrieval P50 ms: `6990 -> 6085` (`-905`, about `-13%`)
- retrieval P95 ms: `35109 -> 25997` (`-9112`, about `-26%`)
- wall-clock P50 ms: `10682 -> 9036` (`-1646`)
- wall-clock P95 ms: `43969 -> 34867` (`-9102`)

Interpretation:

- The latency gate materially reduced the regression and kept the headline PASS count flat at `249`.
- Quality churn was slightly negative in this follow-up: `PARTIAL -1`, `MISS +1`, and `routing correct -1` versus the prior Lane 1 rerun.
- This rerun should be read as a latency win, not a net quality win.
- Verdict churn remains real: the rerun traded a small amount of recall in some families for a meaningful latency win.

## Notable Improved IDs vs Prior Lane 1 Rerun

- `PQ-200`: `PARTIAL -> PASS`, retrieval `20186ms -> 9186ms`
- `PQ-255`: `MISS -> PASS`, retrieval `10444ms -> 30226ms`
- `PQ-385`: `PARTIAL -> PASS`, retrieval `4829ms -> 5757ms`
- `PQ-419`: `MISS -> PARTIAL`, retrieval `4436ms -> 4690ms`
- Additional improved IDs from the delta artifact:
  - `PQ-226`, `PQ-242`, `PQ-397`, `PQ-402`, `PQ-450`

Note on slower-but-better wins:

- `PQ-255`, `PQ-385`, and `PQ-419` improved in verdict but not latency.
- Inference: the tail gate changed candidate mix rather than guaranteeing per-query speedups; these queries appear to have landed on slower but more accurate hybrid/rerank or typed-metadata paths after the narrower path probe budget changed early candidate ordering.
- This inference is based on unchanged route shapes plus changed verdict/latency, not on a deeper per-query internal trace.

## Regressions vs Prior Lane 1 Rerun

- Regressed IDs:
  - `PQ-103`, `PQ-154`, `PQ-170`, `PQ-283`, `PQ-306`, `PQ-340`, `PQ-356`, `PQ-399`, `PQ-440`, `PQ-449`
- Family churn from the compare artifact:
  - `CDRLs`: `+1 PASS`, `-4 PARTIAL`, `+3 MISS`
  - `Logistics`: `-1 PASS`, `+2 PARTIAL`, `-1 MISS`
  - `Program Management`: `-1 PASS`, `+1 PARTIAL`
- Worst outlier in the rerun remained `PQ-103` at roughly `90s`, so the path-tail gate is not the only latency driver in the current system.

## Position vs Post-CDRL Pre-Lane-1 Baseline

Compared:

- baseline: `docs/production_eval_results_post_cdrl_path_patch_400_2026-04-13.json`
- new: `docs/production_eval_results_lane1_latency_followup_400_2026-04-13.json`
- standard delta artifact: `docs/PRODUCTION_EVAL_DELTA_POST_CDRL_TO_LANE1_LATENCY_FOLLOWUP_400_2026-04-13.md`

Headline delta:

- PASS: `226 -> 249` (`+23`)
- PARTIAL: `78 -> 71` (`-7`)
- MISS: `96 -> 80` (`-16`)
- routing correct: `298 -> 300` (`+2`)
- retrieval P50 ms: `3695 -> 6085` (`+2390`)
- retrieval P95 ms: `16233 -> 25997` (`+9764`)

Family delta:

- `CDRLs`: `+11 PASS`, `-2 PARTIAL`, `-9 MISS`
- `Logistics`: `+21 PASS`, `-13 PARTIAL`, `-8 MISS`
- `Cybersecurity`: `-5 PASS`, `+5 PARTIAL`, `+0 MISS`

Interpretation:

- Lane 1 still holds a real overall quality gain versus the post-CDRL baseline.
- The latency gate recovered part of the demo-risk latency spike, but the rerun is still slower than the pre-Lane-1 baseline.
- Cyber remains mixed versus the pre-Lane-1 baseline even after the follow-up.

## Demo-Relevant Cyber Read

Canonical May 2 demo docs still keep cyber in scope:

- `docs/MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md`
  - says the safest live persona modules are in logistics, field engineering, and cybersecurity
- `docs/PRODUCTION_EVAL_400_QUALITY_AUDIT_2026-04-12.md`
  - explicitly names `PQ-255` and `PQ-318` as strong demo candidates

Status of the cyber IDs QA called out:

- Improved:
  - `PQ-200`: `PARTIAL -> PASS`
  - `PQ-385`: `PARTIAL -> PASS`
  - `PQ-419`: `MISS -> PARTIAL`
  - `PQ-255`: `MISS -> PASS`
- Unchanged but still not clean:
  - `PQ-196`: `PARTIAL -> PARTIAL`
  - `PQ-201`: `PARTIAL -> PARTIAL`
  - `PQ-262`: `PARTIAL -> PARTIAL`
  - `PQ-475`: `PARTIAL -> PARTIAL`
  - `PQ-476`: `PARTIAL -> PARTIAL`
  - `PQ-479`: `PARTIAL -> PARTIAL`
  - `PQ-318`: `PARTIAL -> PARTIAL`

Conclusion:

- The follow-up improved several cyber/demo-relevant IDs, but cyber is still not fully safe for open-ended live demo use.
- `P95 = 25997ms` is much better than `35109ms`, but still too slow for a relaxed enterprise demo unless the live script stays narrow and rehearsed.

## Commands Run

```powershell
.\.venv\Scripts\python.exe -m py_compile src\query\vector_retriever.py src\store\lance_store.py tests\test_candidate_pool_wiring.py
.\.venv\Scripts\python.exe -m pytest tests\test_candidate_pool_wiring.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_query_router.py tests\test_retrieval_metadata_store.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_tier1_clean_store_audit.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_ingest_integrity.py -q
$env:CUDA_VISIBLE_DEVICES='1'; .\.venv\Scripts\python.exe scripts\run_production_eval.py --queries tests\golden_eval\production_queries_400_2026-04-12.json --results-json docs\production_eval_results_lane1_latency_followup_400_2026-04-13.json --report-md docs\PRODUCTION_EVAL_RESULTS_LANE1_LATENCY_FOLLOWUP_400_2026-04-13.md
.\.venv\Scripts\python.exe scripts\compare_production_eval_results.py --baseline docs\production_eval_results_lane1_retrieval_router_400_2026-04-13.json --new docs\production_eval_results_lane1_latency_followup_400_2026-04-13.json --markdown docs\PRODUCTION_EVAL_DELTA_LANE1_LATENCY_FOLLOWUP_400_2026-04-13.md
.\.venv\Scripts\python.exe scripts\compare_production_eval_results.py --baseline docs\production_eval_results_post_cdrl_path_patch_400_2026-04-13.json --new docs\production_eval_results_lane1_latency_followup_400_2026-04-13.json --markdown docs\PRODUCTION_EVAL_DELTA_POST_CDRL_TO_LANE1_LATENCY_FOLLOWUP_400_2026-04-13.md
```
