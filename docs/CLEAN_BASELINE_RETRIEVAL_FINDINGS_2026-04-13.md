# Clean Baseline Retrieval Findings -- 2026-04-13

**Scope:** clean Tier 1 baseline results from `docs/production_eval_results_clean_tier1_2026-04-13.json`, with emphasis on CDRLs and Logistics.

**Goal:** identify the concrete ranking and metadata opportunities that remain before the next clean rerun and before we trust RAGAS-style retrieval metrics.

## Executive Summary

The clean Tier 1 baseline is good enough to show the shape of the remaining problem:

- the store is not randomly missing the right family
- the main weakness for many of the `PARTIAL` rows is ranking, not recall
- the main weakness for `MISS` rows is still family recall and routing, especially on CDRLs and Logistics

That distinction matters.

- **`PASS` rows:** the right family is already at top-1
- **`PARTIAL` rows:** the right family is already in top-5, but not at top-1
- **`MISS` rows:** the right family is not in top-5

So the next retrieval gains are not broad embedding churn. The clean path is:

1. push family/path metadata into reranking
2. use exact identifier cues more aggressively for CDRL / PO / shipment style questions
3. reserve more invasive retrieval changes for the true miss families only

## Headline Numbers

From the 400-query clean baseline:

- `PASS`: `158`
- `PARTIAL`: `96`
- `MISS`: `146`
- routing correct: `287 / 400`

By family, the two highest-value target sets are:

| Family | Total | PASS | PARTIAL | MISS | Routing correct |
|---|---:|---:|---:|---:|---:|
| CDRLs | 127 | 11 | 30 | 86 | 98 |
| Logistics | 101 | 16 | 36 | 49 | 67 |
| Cybersecurity | 63 | 42 | 19 | 2 | 40 |
| Program Management | 48 | 41 | 6 | 1 | 38 |
| Site Visits | 21 | 18 | 3 | 0 | 18 |
| Systems Engineering | 13 | 11 | 2 | 0 | 9 |
| Field Engineering | 12 | 6 | 0 | 6 | 6 |

## What The Baseline Is Really Telling Us

### 1. `PARTIAL` is mostly a ranking problem

For the families that matter most to demo confidence, `PARTIAL` rows are already landing the right family somewhere in top-5:

- CDRLs: `30 / 30` partials have `any_top5_in_family = true`
- Logistics: `36 / 36` partials have `any_top5_in_family = true`
- Cybersecurity: `19 / 19`
- Program Management: `6 / 6`
- Site Visits: `3 / 3`
- Systems Engineering: `2 / 2`

But those same rows do **not** reach top-1:

- CDRLs: `0 / 30` partials have `top_in_family = true`
- Logistics: `0 / 36`
- Cybersecurity: `0 / 19`
- Program Management: `0 / 6`
- Site Visits: `0 / 3`
- Systems Engineering: `0 / 2`

That is a very specific opportunity:

- the right family is already being retrieved
- the reranker is not promoting it enough
- source-path and filename metadata should be able to help

### 2. `MISS` is the true recall gap

For the same families:

- CDRLs: `0 / 86` misses have the right family in top-5
- Logistics: `0 / 49`
- Cybersecurity: `0 / 2`
- Program Management: `0 / 1`
- Field Engineering: `0 / 6`

These are the queries that need better family/path matching, better query expansion, or stronger exact-identifier handling before we can call the baseline clean.

## CDRLs: Concrete Retrieval Opportunities

CDRLs are the biggest combined problem:

- `127` total
- `30` partials
- `86` misses

Representative partials:

- `PQ-104` - IMS / deliverable locator
- `PQ-108` - configuration change requests under CDRL A050
- `PQ-128` - Maintenance Service Reports
- `PQ-133` - installation / acceptance test report docs
- `PQ-144` - CCI control mappings in an RMF security plan

Representative misses:

- `PQ-103` - A002 maintenance service reports
- `PQ-109` - A008 Program Management Plan
- `PQ-130` - Corrective Action Plan for IGSI-1811
- `PQ-136` - ACAS scan results under A027
- `PQ-137` - SCAP scan results archived for monitoring systems

### CDRL-specific opportunities

1. **Path-aware reranking**
   - Many CDRL files encode the family in the folder name or filename.
   - The clean baseline already gets those families into top-5 for partials.
   - The reranker should see `source_path`, not only chunk text.

2. **Exact identifier expansion**
   - CDRL questions often include exact IDs like `A002`, `A008`, `A027`, `A050`, `IGSI-1811`.
   - These identifiers should be preserved and used as hard retrieval clues.

3. **Family lexicon boosting**
   - CDRL families often use telltale terms that should be treated as retrieval anchors:
     - `Maintenance Service Report`
     - `Program Management Plan`
     - `Corrective Action Plan`
     - `ACAS`
     - `SCAP`
     - `RMF`
     - `A0xx` deliverable codes

## Logistics: Concrete Retrieval Opportunities

Logistics is the second big problem:

- `101` total
- `36` partials
- `49` misses

Representative partials:

- `PQ-111` - packing list for a shipment
- `PQ-112` - pre-amplifier parts and specifications
- `PQ-114` - parts catalogs for PVC components
- `PQ-118` - procurement records for an option-year period
- `PQ-121` - DD250 acceptance forms

Representative misses:

- `PQ-113` - exact purchase order lookup
- `PQ-117` - coax cable types for antenna installations
- `PQ-120` - obstruction lighting requirements
- `PQ-123` - S4 HANA / AssetSmart fixes list
- `PQ-206` - site/submission history for ATO Re-Authorization packages

### Logistics-specific opportunities

1. **Path / filename ranking**
   - The right retrieval candidate often exists, but not at top-1.
   - Shipping, procurement, and packing-list folders are strong signals and should be promoted earlier.

2. **Identifier-heavy query handling**
   - Real PO numbers, CLIN numbers, and shipment IDs should be preserved as query anchors.
   - Exact identifiers plus the surrounding logistics vocabulary are the highest-value cues in this family.

3. **Document-family expansion**
   - `shipment`
   - `packing list`
   - `procurement`
   - `purchase order`
   - `DD250`
   - `received PO`
   - `open PO`
   - `backordered`

## Concrete Ranking Opportunity

The most obvious low-risk improvement is to make reranking path-aware.

Why:

- the baseline shows `PARTIAL` rows already have the right family in top-5
- the top-1 miss is usually a family/path ranking problem
- `source_path` already exists on every chunk result
- adding it to the reranker input is cheap and does not change extraction semantics

I implemented that small fix in the reranker:

- `src/query/reranker.py` now feeds `source_path` into the FlashRank passage text
- new test:
  - `tests/test_reranker_path_aware.py`

This is intentionally narrow:

- it does not change the store
- it does not change extraction
- it does not change the router
- it only gives the reranker more evidence when the folder or filename is the real signal

## What To Focus On Next

### High value

- CDRL and Logistics path-aware ranking
- exact identifier handling for PO / DD250 / A0xx style queries
- preserving top-5 family recall while improving top-1 family rank

### Lower priority until after that

- broad embedding or model swaps
- aggressive retrieval rewrites
- new aggregation authoring

## Bottom Line

The clean baseline says we are not far off.

- **CDRLs:** lots of family recall, weak top-1 family rank
- **Logistics:** same pattern, with more true misses
- **Best next lever:** path-aware reranking using source-path metadata plus exact identifier cues

That gives us the best chance of improving the clean rerun and the later RAGAS pass without destabilizing the rest of the pipeline.
