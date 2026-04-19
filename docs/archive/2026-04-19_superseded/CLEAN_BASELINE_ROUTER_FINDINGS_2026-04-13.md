# Clean Baseline Router Findings

Source of truth for this note:
- `docs/production_eval_results_clean_tier1_2026-04-13.json`
- `scripts/run_production_eval.py`
- `src/query/query_router.py`

## Baseline

On the clean Tier 1 baseline:
- 400 total queries
- 287 routed correctly
- 113 routed incorrectly
- top-level split:
  - `PASS`: 158
  - `PARTIAL`: 96
  - `MISS`: 146

The router is still the main classification bottleneck. Retrieval is often fine once the route is right.

## Biggest Wrong-Route Clusters

The dominant clean-baseline confusions were:

| Expected | Routed | Count | Pattern |
| --- | --- | ---: | --- |
| `SEMANTIC` | `ENTITY` | 37 | Document-content questions over-restricted as single-item lookups |
| `ENTITY` | `TABULAR` | 25 | Shipment / packing-list / report-template lookups treated like spreadsheet queries |
| `SEMANTIC` | `TABULAR` | 15 | Review / response / report-content questions over-restricted as structured lookups |
| `SEMANTIC` | `AGGREGATE` | 8 | Content questions with collection language (`documents`, `actions`, `results`, etc.) |
| `TABULAR` | `ENTITY` | 6 | Some structured lookups still look like single-item factual queries |

The highest-frequency personas in the misses were:
- Logistics Lead
- Cybersecurity / Network Admin
- Program Manager
- Field Engineer

## Smallest Safe Fix

A low-risk provider-agnostic deterministic guard was added in `src/query/query_router.py`:

- `what does ... say about ...`
- `what are ... templates used for ...`
- `what is in the ...`
- `sources sought response`
- `reported in the latest ...`
- `what does ... cover/contain` when the query is clearly about a document/report/plan

This guard intentionally avoids explicit tabular cues like:
- `spreadsheet`
- `table`
- `tracker`
- `inventory`
- `actuals`
- `budget`
- `packing list`
- `purchase order`
- `status of po`
- `show me`

It also excludes scan-report phrasing that has historically been routed correctly as entity-style lookup.

## Effect On The Clean Baseline

Using the stored clean-baseline routes as the comparison set, the new guard changes 8 queries from wrong to right:

- `PQ-105`
- `PQ-106`
- `PQ-109`
- `PQ-135`
- `PQ-158`
- `PQ-160`
- `PQ-181`
- `PQ-195`

Observed clean-baseline routing correctness moves from:
- `287 / 400` correct

to:
- `295 / 400` correct

That is a net gain of 8 routes with no baseline regressions in this lane.

## Remaining Post-Fix Clusters

After the content-question guard, the biggest remaining misses are still:

| Expected | Routed | Count |
| --- | --- | ---: |
| `SEMANTIC` | `ENTITY` | 31 |
| `ENTITY` | `TABULAR` | 25 |
| `SEMANTIC` | `TABULAR` | 13 |
| `SEMANTIC` | `AGGREGATE` | 8 |
| `TABULAR` | `ENTITY` | 6 |

## Recommended Next Smallest Changes

If the next router pass is needed, the best follow-on candidates are narrower than a broad rule rewrite:

- teach `where do I find` / `where can I find` to behave like tabular lookups only when the query also contains explicit structured-artifact cues
- consider a tighter shipment / packing-list policy so the router does not bounce between `ENTITY` and `TABULAR` on the same phrase family
- keep content-style document questions on the semantic path rather than expanding the tabular or entity regexes

## Acceptance Gate

Before calling the clean-store router “good enough” again:

1. Run `python -m pytest -q tests\\test_query_router.py`
2. Re-run the clean-baseline score comparison on `docs/production_eval_results_clean_tier1_2026-04-13.json`
3. Confirm that any further rule change does not regress the document-content queries already fixed here

The router is still not perfect, but this lane removes one of the highest-signal and lowest-risk error clusters without touching retrieval or extraction.
