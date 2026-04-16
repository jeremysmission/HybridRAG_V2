# Lane 1 Retrieval + Router Burn-Down Evidence

Date: 2026-04-13

Owner: Lane 1

Canonical repo: `C:\HybridRAG_V2`

Baseline compared against:
- [docs/PRODUCTION_EVAL_RESULTS_POST_CDRL_PATH_PATCH_400_2026-04-13.md](/C:/HybridRAG_V2/docs/PRODUCTION_EVAL_RESULTS_POST_CDRL_PATH_PATCH_400_2026-04-13.md)
- [docs/production_eval_results_post_cdrl_path_patch_400_2026-04-13.json](/C:/HybridRAG_V2/docs/production_eval_results_post_cdrl_path_patch_400_2026-04-13.json)

New measured artifacts:
- [docs/PRODUCTION_EVAL_RESULTS_LANE1_RETRIEVAL_ROUTER_400_2026-04-13.md](/C:/HybridRAG_V2/docs/PRODUCTION_EVAL_RESULTS_LANE1_RETRIEVAL_ROUTER_400_2026-04-13.md)
- [docs/production_eval_results_lane1_retrieval_router_400_2026-04-13.json](/C:/HybridRAG_V2/docs/production_eval_results_lane1_retrieval_router_400_2026-04-13.json)
- [docs/PRODUCTION_EVAL_DELTA_LANE1_RETRIEVAL_ROUTER_400_2026-04-13.md](/C:/HybridRAG_V2/docs/PRODUCTION_EVAL_DELTA_LANE1_RETRIEVAL_ROUTER_400_2026-04-13.md)

## What Changed

- `src/store/lance_store.py`
  - Changed metadata path recall to prefer `chunk_index = 0` rows and dedupe by `source_path`, so path-heavy queries retrieve distinct files instead of many neighboring chunks from one file.
- `src/query/vector_retriever.py`
  - Expanded path-hint generation for:
    - raw PO numbers
    - procurement item/vendor queries
    - A027 subtype, contract, and month/year hints
    - shipment site/date/mode queries with better site extraction
    - multi-CDRL cross-tree queries
  - Added breadth-first behavior for cross-family queries so one folder family does not consume the entire metadata-path candidate pool.
  - Added path-hit prioritization that favors exact PO / contract / date matches and logistics/CDRL corpus paths over DIDs, old references, and archive noise.
- `src/query/query_router.py`
  - Added deterministic guards for:
    - `show me the purchase order ...` -> `ENTITY`
    - narrow dated shipment lookups -> `ENTITY`
    - `where are ... documents stored` A027 organization questions -> `SEMANTIC`
  - Added PO-number expansion for procurement-style queries.
- `src/query/pipeline.py`
  - Fixed the live visit-priority ordering bug in `_prioritize_visit_condition_results()` so curated field-visit artifacts sort ahead of fixture/manual noise.
- `src/query/reranker.py`
  - Strengthened the reranker passage for metadata-path matches by explicitly labeling them and including the filename.
- `tests/test_candidate_pool_wiring.py`
  - Added focused coverage for the new path-hint, routing, and visit-priority behavior.

## Score Delta

- Baseline: `226/400 PASS`, `304/400 PASS+PARTIAL`, `298/400 routing correct`
- New run: `249/400 PASS`, `321/400 PASS+PARTIAL`, `301/400 routing correct`
- Delta: `+23 PASS`, `+17 PASS+PARTIAL net`, `+3 routing correct`

## Miss Families Improved

- Logistics / procurement improved materially.
  - Family delta: `+22 PASS`, `-7 MISS`
  - Clear flips: `PQ-113`, `PQ-223`, `PQ-224`, `PQ-225`, `PQ-227`, `PQ-228`, `PQ-231`, `PQ-233`, `PQ-234`, `PQ-237`, `PQ-283`, `PQ-285`, `PQ-291`, `PQ-294`, `PQ-343`, `PQ-345`, `PQ-457`
- Shipment / site-date retrieval improved.
  - Exact dated shipment and packing-list lookups now consistently surface the intended logistics folders earlier.
  - Example flip: `PQ-234` `PARTIAL -> PASS`
- CDRL / A027 path-heavy retrieval improved.
  - Family delta: `+10 PASS`, `-12 MISS`
  - Clear flips: `PQ-103`, `PQ-136`, `PQ-137`, `PQ-147`, `PQ-192`, `PQ-202`, `PQ-204`, `PQ-208`, `PQ-210`, `PQ-257`, `PQ-374`, `PQ-383`
- Router correctness improved on the measured set.
  - Key routing fixes landed for `PQ-167`, `PQ-223`, `PQ-318`

## Regressions

- Cybersecurity family regressed overall in this run.
  - Family delta: `-7 PASS`, `+6 PARTIAL`, `+1 MISS`
  - Notable regressions: `PQ-196`, `PQ-200`, `PQ-201`, `PQ-262`, `PQ-385`, `PQ-419`, `PQ-475`, `PQ-476`, `PQ-479`
- Some logistics breadth queries regressed.
  - Notable regressions: `PQ-118`, `PQ-226`
- Some broad or comparative CDRL semantics remain weak or regressed.
  - Notable regressions: `PQ-326`, `PQ-376`, `PQ-450`

## Residual Risks

- The remaining stubborn misses are still concentrated in broad semantic CDRL content questions rather than exact path retrieval:
  - `PQ-109`
  - `PQ-158`
  - `PQ-160`
  - `PQ-161`
- The A027 exact-family path fixes helped aggregate and deliverable lookup families, but some cybersecurity semantic/tabular cases moved from `PASS` to `PARTIAL` or `MISS`.
- Latency increased materially because metadata-path recall now fetches diverse file-level candidates instead of stopping at the first chunk cluster.

## Latency Notes

- Baseline pure retrieval latency: `P50 3695ms`, `P95 16233ms`
- New pure retrieval latency: `P50 6990ms`, `P95 35109ms`
- Net latency delta: `+3295ms P50`, `+18876ms P95`
- The increase is consistent with:
  - file-level metadata path dedupe
  - broader path-group coverage for CDRL/A027/procurement/shipment families
  - more breadth-first path retrieval for cross-family questions

## Commands Run

```powershell
nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits

.\.venv\Scripts\python.exe -m pytest tests\test_candidate_pool_wiring.py -q

$env:CUDA_VISIBLE_DEVICES='0'
.\.venv\Scripts\python.exe scripts\run_production_eval.py `
  --queries C:\WINDOWS\TEMP\lane1_focus_queries_2026-04-13.json `
  --results-json C:\WINDOWS\TEMP\lane1_focus_results_2026-04-13.json `
  --report-md C:\WINDOWS\TEMP\lane1_focus_results_2026-04-13.md

$env:CUDA_VISIBLE_DEVICES='1'
.\.venv\Scripts\python.exe scripts\run_production_eval.py `
  --queries tests\golden_eval\production_queries_400_2026-04-12.json `
  --results-json docs\production_eval_results_lane1_retrieval_router_400_2026-04-13.json `
  --report-md docs\PRODUCTION_EVAL_RESULTS_LANE1_RETRIEVAL_ROUTER_400_2026-04-13.md

.\.venv\Scripts\python.exe scripts\compare_production_eval_results.py `
  --baseline docs\production_eval_results_post_cdrl_path_patch_400_2026-04-13.json `
  --new docs\production_eval_results_lane1_retrieval_router_400_2026-04-13.json `
  --markdown docs\PRODUCTION_EVAL_DELTA_LANE1_RETRIEVAL_ROUTER_400_2026-04-13.md
```

## Bottom Line

- This lane produced a real measured gain on the canonical 400.
- The strongest gains are in logistics/procurement, shipment/date, and A027/CDRL path-heavy retrieval.
- The main follow-on work is not more shipment/PO hinting. It is the remaining broad semantic CDRL-content misses and the cybersecurity regressions introduced while biasing retrieval toward stronger file-level path evidence.
