# Current-System 400-Query Baseline

Run date: 2026-04-12  
Store: current master, live 10.4M-chunk LanceDB store  
Query pack: `tests/golden_eval/production_queries_400_2026-04-12.json`

This baseline is truthful after a small harness fix in `scripts/run_production_eval.py`:
the 400-pack uses `expected_document_family` fallback signals when the old 25-query
hardcoded family map does not apply.

## Headline

- PASS: 148 / 400 (37.0%)
- PARTIAL: 107 / 400 (26.8%)
- MISS: 145 / 400 (36.3%)
- Routing correct: 259 / 400 (64.8%)
- PASS + PARTIAL: 255 / 400 (63.8%)
- Pure retrieval P50 / P95: 149 ms / 9120 ms
- Wall clock P50 / P95: 1977 ms / 10389 ms
- Router P50 / P95: 1130 ms / 1769 ms

## Per Persona

| Persona | Total | PASS | PARTIAL | MISS | Routing |
|---|---:|---:|---:|---:|---:|
| Program Manager | 80 | 39 | 20 | 21 | 59 / 80 |
| Logistics Lead | 80 | 11 | 30 | 39 | 42 / 80 |
| Field Engineer | 80 | 40 | 16 | 24 | 60 / 80 |
| Cybersecurity / Network Admin | 80 | 30 | 22 | 28 | 46 / 80 |
| Aggregation / Cross-role | 80 | 28 | 19 | 33 | 52 / 80 |

## Per Query Type

| Type | Total | PASS | PARTIAL | MISS | Routing |
|---|---:|---:|---:|---:|---:|
| TABULAR | 75 | 32 | 20 | 23 | 62 / 75 |
| AGGREGATE | 106 | 40 | 25 | 41 | 77 / 106 |
| ENTITY | 117 | 31 | 33 | 53 | 65 / 117 |
| SEMANTIC | 102 | 45 | 29 | 28 | 55 / 102 |

## What Is Working

- Program Management and Field Engineering are the strongest personas.
- Cybersecurity is usable, especially for exact scan / reauth lookups.
- 255 / 400 queries hit the expected family in the top-5.
- Routing is imperfect but not the only issue: 90 wrong-route queries still returned PASS/PARTIAL retrieval.

## Main Failure Clusters

1. `CDRLs` family remains the biggest concentration of misses.
   - 82 misses, 36 partial, 9 pass
   - strongest failures are on exact file / deliverable / cross-reference questions

2. `Logistics` is the second major cluster.
   - 53 misses, 34 partial, 14 pass
   - the weak spots are purchase-order, shipment, and open-order lookups

3. Structured exact-match behavior is still uneven.
   - ENTITY: 53 misses
   - TABULAR: 23 misses
   - these are mostly file-location, identifier, and row/table lookups

4. Cross-role aggregation is still incomplete.
   - AGGREGATE: 41 misses
   - the common failure motif is multi-document counting / cross-reference across CDRLs, logistics, and cybersecurity trees

5. Router quality is a real but secondary problem.
   - 141 / 400 routed incorrectly
   - 49 PASS and 41 PARTIAL results still happened on wrong routes, so routing is not the only blocker

## Retrieval vs Router vs Structured Data

- Retrieval is not globally broken. The corpus is usable for real evaluation.
- The remaining misses cluster around polluted structured classes and broad cross-document aggregation.
- Router tuning still matters, but the biggest lift now is cleaning PO / PART pollution and closing exact-match / aggregation gaps.

## Demo-Day Read

This is not demo-clean yet, but it is good enough to anchor truthful baseline tracking.
The next highest-value steps are:

1. clean Tier 1 rerun to de-pollute the structured layer
2. router tuning for Logistics, ENTITY, and AGGREGATE misroutes
3. exact-token / path-aware retrieval improvements for identifier-heavy queries
