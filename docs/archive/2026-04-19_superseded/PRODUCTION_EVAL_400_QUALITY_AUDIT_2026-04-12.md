# Production Eval 400 Quality Audit - 2026-04-12

**Agent:** Agent A  
**Repo:** `C:\HybridRAG_V2`  
**Primary corpus:** `tests/golden_eval/production_queries_400_2026-04-12.json`  
**Scope:** live-demo suitability audit, not scoring-lane relabeling

## Executive Summary

The 400-query corpus is substantially stronger than the first production pack, but it is not uniformly "demo ready."

The strongest slice is now very strong: exact-ID logistics, CDRL, shipment, site-visit, and cybersecurity artifact lookups are narrow, manually defensible, and easy to narrate live. The weakest slice is also obvious: cross-role aggregation, cross-tree comparison, and early folder-mining questions often prove that the corpus contains a family of artifacts, but not the exact answer phrased by the question.

This audit uses a deliberately stricter live-demo bar than the retrieval eval bar:

- `demo_safe` means narrow, directly grounded, easy to narrate, and not dependent on broad aggregation.
- `retrieval_only_safe` means the retrieval evidence is good enough to show sources, but the answer synthesis or live narration is still broader than it should be.
- `needs_tighter_reference` means the question could be usable, but the current `reference` / `reference_contexts` are weaker than the query wording.
- `avoid_for_demo` means over-broad, self-admitted partial, polluted-adjacent, or too cross-role/cross-tree to trust on stage.

**Key call:** I did **not** clear any `AGGREGATE` query into `demo_safe`. Some are good retrieval probes. None are the right "clean first impression" demo questions yet.

## Audit Method

I did not treat all 400 rows equally. This was a stratified audit:

1. Full inspection of all cross-role / likely aggregation-demo queries
2. Full inspection of queries whose references self-admit incompleteness or partial enumeration
3. Full inspection of likely live openers: exact PO, exact deliverable ID, shipment, training, site-visit, and month-file lookups
4. Representative sampling across persona, query-type, and family buckets to catch weaker inherited patterns

## Counts By Bucket

| Bucket | Count | Read |
|---|---:|---|
| `demo_safe` | 258 | Strong live-demo material; narrow and defensible |
| `retrieval_only_safe` | 71 | Good retrieval evidence, but answer/narration bar is still lower than live-demo bar |
| `needs_tighter_reference` | 24 | Query may be salvageable, but current gold answer/context is too loose |
| `avoid_for_demo` | 47 | Over-broad, partial, polluted-adjacent, or stage-risky |
| **Total** | **400** | |

### Important Sub-findings

- `Aggregation / Cross-role` contributed **0** `demo_safe` rows in this audit.
- `ENTITY` and single-file `TABULAR` queries dominate the `demo_safe` bucket.
- `AGGREGATE` is the main driver of both `retrieval_only_safe` and `avoid_for_demo`.

## Top 20 Safest Demo Candidates

These are the cleanest live-demo candidates in the current 400. They are narrow, path-grounded, and easy to explain without overclaiming.

| Query ID | Persona | Why it is safe |
|---|---|---|
| `PQ-223` | Logistics Lead | Exact PO, vendor, item, value, and contract period are encoded in one received-PO folder path |
| `PQ-224` | Logistics Lead | Exact PO-to-part lookup; single received-PO folder cleanly answers it |
| `PQ-225` | Logistics Lead | Exact supplier + cost lookup for a named install artifact; strong procurement story |
| `PQ-232` | Logistics Lead | Exact calibration PO under a named sustainment year; narrow and source-grounded |
| `PQ-234` | Logistics Lead | Single packing-list spreadsheet retrieval for one dated shipment |
| `PQ-343` | Logistics Lead | Exact high-value PO lookup with quantity, vendor line, and value encoded in path |
| `PQ-103` | Program Manager | Exact CDRL code lookup (`A002`) with a canonical deliverable family |
| `PQ-276` | Program Manager | Exact person + exact certificate location; very easy to narrate honestly |
| `PQ-401` | Program Manager | Single-file FEP Monthly Actuals retrieval; clean spreadsheet demo |
| `PQ-446` | Program Manager | Exact IGSI deliverable lookup for a named SEMP artifact |
| `PQ-130` | Field Engineer | Exact incident ID (`IGSI-1811`) tied to one corrective-action-plan family |
| `PQ-239` | Field Engineer | Exact work-note family locator for transmitter tuning instructions |
| `PQ-247` | Field Engineer | Site-visit traveler names are encoded in the trip folder itself |
| `PQ-355` | Field Engineer | Exact annual inventory deliverable ID and filing location |
| `PQ-413` | Field Engineer | Single monthly outage spreadsheet retrieval with exact filename grounding |
| `PQ-418` | Field Engineer | Exact site/month audit-log location with concrete file names |
| `PQ-255` | Cybersecurity / Network Admin | Exact A027 deliverable ID for one October 2025 ACAS scan submission |
| `PQ-307` | Cybersecurity / Network Admin | Exact MSR deliverable ID lookup under one site folder |
| `PQ-318` | Cybersecurity / Network Admin | Exact A027 plan-and-controls storage path with a concrete January 2025 file |
| `PQ-360` | Cybersecurity / Network Admin | Exact STIG bundle archive retrieval for one dated Eareckson package |

### Near-Miss Alternates

- `PQ-314` - also strong; older MSR existence/locator
- `PQ-452` - exact IATP filing location
- `PQ-457` - exact January 2026 packing-list lookup

## Top Risky Inherited Queries To Keep Off Stage

These are mostly early-authored questions that look stronger than they are. They are the clearest examples of "we can retrieve the family, but we should not narrate this as an authoritative answer."

| Query ID | Why it should not be used live |
|---|---|
| `PQ-102` | Asks for 2024 Monthly Actuals rollup across months, but the gold answer only proves that files exist |
| `PQ-105` | Asks for PMR cost/schedule variances, but the reference only identifies PMR decks, not the actual variances |
| `PQ-106` | Asks for Sources Sought response status; reference explicitly says specific files were not surfaced |
| `PQ-107` | "How many CDRL deliverable types" is answered as an `at least` count with mixed family definitions |
| `PQ-118` | Real procurement family, but still phrased as a broader option-year procurement enumeration than the evidence supports |
| `PQ-120` | FAA lighting requirement question is answered with a folder locator, not the requirement content |
| `PQ-143` | Scope drift: "since 2020" answer mixes a 2019 reauthorization package and a 2021 software change |
| `PQ-146` | Corpus-wide MSR folder count from one parent folder; good retrieval family probe, weak live-demo narration |
| `PQ-148` | Self-admitted partial answer; explicitly says broader open-purchase enumeration is unsafe pre-cleanup |
| `PQ-151` | Asks for a December variance trend; reference only lists the five weekly files |
| `PQ-154` | Explicitly says 2025 Monthly Actuals are not fully enumerated yet |
| `PQ-156` | 2024 A009 set is an `at least four` surfaced subset, not a trustworthy year-complete answer |

## Pattern Findings

### Persona Patterns

- **Logistics Lead is the strongest demo lane.**
  Exact received-PO, shipment, calibration, and packing-list questions are excellent because the answer is often encoded directly in the folder/file name.
- **Field Engineer is the next strongest lane.**
  Site-visit, incident, and field-note questions narrate well when tied to exact dates, trip folders, or incident IDs.
- **Cybersecurity / Network Admin is strong on exact artifact IDs, weaker on timeline/comparison questions.**
  A027/A002/A007 exact deliverable lookups are solid. Broad WX29, ATO, or Pending-vs-Final comparison questions are much weaker.
- **Program Manager is mixed.**
  Exact weekly-variance / Monthly Actuals / SEMP file lookups are good. "Latest status," "variances," and trend questions are often under-grounded.
- **Aggregation / Cross-role is not a live-demo lane yet.**
  It is useful for retrieval stress-testing and future clean-store eval, but it is not the right stage material now.

### Query-Type Patterns

- **`ENTITY` is the strongest query type.**
  Exact PO numbers, exact deliverable IDs, exact incident IDs, and exact person/document lookups are the cleanest material in the file.
- **`TABULAR` is strong when it points to one spreadsheet/file.**
  It weakens quickly when the wording asks for a comparison or interpreted difference not visible in filenames.
- **`SEMANTIC` is strong only when it is really a narrow locator/explainer.**
  It gets weaker when the wording implies status, comparison, trend, or specification extraction from files that are only path-grounded.
- **`AGGREGATE` is the weakest live-demo type.**
  Some rows are good retrieval probes. None clear the "first-tier live demo" bar yet.

### Family Patterns

- **Strongest families for live demo:** `Logistics`, `CDRLs`, exact `Program Management` file series, exact `Cybersecurity` deliverables
- **Mixed families:** `Site Visits`, `Systems Engineering`
- **Weakest live-demo patterns:** cross-family `Program Management` rollups, cross-tree `Cybersecurity` / `CDRLs` comparisons, and broad procurement enumeration

### Cohort / Authoring Patterns

- **The 100-series is the weakest inherited cohort.**
  It contains the highest concentration of early folder-mining questions whose answers prove artifact existence more than the exact user ask.
- **The 200-300 range is the strongest retrieval-first authoring window.**
  These rows are much more often exact-anchor, exact-file, or exact-deliverable queries.
- **The 400-series is split.**
  It contains many of the best exact file locators, but it also contains the dense cross-reference stress pack. That pack is valuable for eval pressure, not live demo narration.

## Operational Recommendation

If the team needs a live-demo shortlist right now:

1. Pull only from the `demo_safe` bucket
2. Prefer exact-ID / exact-file lookups over any aggregation
3. Keep `retrieval_only_safe` for backstage rehearsal or retrieval evidence screenshots
4. Treat `needs_tighter_reference` as the best small cleanup target set
5. Keep `avoid_for_demo` out of the May 2 script unless they are rewritten and independently re-verified
