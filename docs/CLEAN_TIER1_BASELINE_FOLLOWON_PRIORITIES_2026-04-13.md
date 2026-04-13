# Clean Tier 1 Baseline Follow-On Priorities - 2026-04-13

**Scope:** follow-on retrieval priorities from the finished clean Tier 1 baseline.  
**Source artifacts:** `docs/production_eval_results_clean_tier1_2026-04-13.json` and `docs/PRODUCTION_EVAL_RESULTS_CLEAN_TIER1_2026-04-13.md`  
**Use:** input to the next retrieval / routing engineering slice after the clean store audit.

## Executive Read

The clean Tier 1 rerun is usable as a truthful baseline, but it is not demo-clean for broad retrieval claims yet.

Headline numbers:

- `PASS`: **158 / 400**
- `PARTIAL`: **96 / 400**
- `MISS`: **146 / 400**
- `PASS + PARTIAL`: **254 / 400**
- Routing correct: **287 / 400**

The corpus is no longer guesswork. The next engineering work should target the clusters that still account for most misses and partials:

1. `CDRLs`
2. `Logistics`
3. identifier / path-heavy exact-match retrieval
4. broader `ENTITY` and `AGGREGATE` recovery on those same families
5. router tuning last, not first

## Highest-Yield Failure Clusters

### 1) `CDRLs` is still the biggest miss family

`CDRLs` accounts for the largest unresolved slice of the clean baseline:

- `86` misses
- `30` partials
- `11` passes

Most of the failures are exact deliverable / file / cross-reference questions:

- `PQ-103` - A002 / Maintenance Service Report
- `PQ-130` - Fairford CAP / IGSI-1811
- `PQ-146` - folder count across the two monitoring-system trees
- `PQ-147` - CAPs by site in 2024
- `PQ-153` - deliverables under legacy contract `47QFRA22F0009`
- `PQ-159` - Priced Bill of Materials in `A014`
- `PQ-161` - `A025` Computer Operation Manual / Software User Manual
- `PQ-184` - Learmonth CAP under `IGSI-2529`
- `PQ-190` - May 2023 scan report / `IGSI-965`

What this means:

- exact deliverable-family routing is still too weak
- the system needs better folder-title / deliverable-code matching
- aggregation over CDRLs is still not trustworthy enough for broad claims

### 2) `Logistics` is the second major miss family

`Logistics` remains the second-largest unresolved slice:

- `49` misses
- `36` partials
- `16` passes

The failure pattern is consistent:

- exact PO lookups
- packing lists
- shipment / return-shipment lookups
- DD250 / acceptance paperwork
- shipment date and destination questions

Representative misses:

- `PQ-113` - PO `5000585586`
- `PQ-121` - DD250 acceptance forms for Niger transfers
- `PQ-163` - Learmonth shipment / destination type
- `PQ-166` - Ascension Mil-Air shipment
- `PQ-167` - Guam hand-carry shipments
- `PQ-171` / `PQ-172` / `PQ-173` - return shipments
- `PQ-223` / `PQ-226` / `PQ-231` - procurement / PO lookups
- `PQ-234` / `PQ-235` / `PQ-238` - packing list and shipment-date questions

What this means:

- path-aware retrieval for procurement and shipment folders still needs work
- the system is better at broad thematic retrieval than at exact logistics lookups
- this is still a high-value slice because it is the most demo-friendly when it works

### 3) Identifier / path-heavy exact-match retrieval is the biggest technical gap

The miss pattern is dominated by exact identifiers and source-path lookups rather than open-ended language understanding.

Observed concentration:

- `ENTITY` misses: **53**
- `AGGREGATE` misses: **41**
- `TABULAR` misses: **23**
- `SEMANTIC` misses: **28**

The same pattern shows up in the clean-baseline result set as the main source of misses for:

- CDRL deliverable IDs
- PO numbers
- IGSI incident IDs
- contract numbers
- shipment dates / packing lists
- folder / file location queries

Representative identifier-heavy misses:

- `PQ-152` - contract number plus CDRL reports
- `PQ-190` / `PQ-254` / `PQ-259` - deliverable ID lookups
- `PQ-223` / `PQ-231` - exact PO retrieval
- `PQ-255` / `PQ-258` - scan deliverable / contract lookup
- `PQ-263` - `A027` ACAS deliverable count

## Persona Concentration That Matters

The weakest persona is still Logistics Lead:

- `PASS`: 11
- `PARTIAL`: 30
- `MISS`: 39

That is the clearest “next slice” signal in the whole baseline.

The other personas are materially stronger:

- Program Manager: `39 / 20 / 21`
- Field Engineer: `40 / 16 / 24`
- Cybersecurity / Network Admin: `30 / 22 / 28`
- Aggregation / Cross-role: `28 / 19 / 33`

So the highest-yield improvement work should not be generic. It should be biased toward the Logistics and CDRL retrieval surfaces that are still failing exact lookups.

## Suggested Engineering Order

### 1. CDRL / deliverable-family retrieval slices

Target the deliverable families that repeatedly miss:

- `A002` Maintenance Service Report
- `A004` DD250
- `A008` Program Management Plan
- `A013` SEMP
- `A014` Priced BOM
- `A023` ILS
- `A025` Computer Operation Manual / Software User Manual
- `A027` cybersecurity subtypes
- `A031` IMS
- `A050` configuration-change requests

Concrete next work:

- strengthen folder-title matching
- strengthen deliverable-code to folder-family linking
- add exact-token retrieval checks for deliverable IDs and contract numbers

### 2. Logistics slices

Attack the exact-match procurement and shipment families next:

- PO numbers
- DD250 / acceptance paperwork
- packing lists
- shipment manifests
- return-shipment folders
- destination / travel-mode questions

Concrete next work:

- path-aware retrieval for procurement trees
- exact-token retrieval for PO numbers and shipment dates
- ranker support for `PO`, `DD250`, packing list, and shipment-folder hits

### 3. Identifier / path-heavy retrieval

This is the broad technical lever behind both families above.

Concrete next work:

- exact-token fallback for IDs and folder/file names
- path-aware retrieval boost for source-path matches
- better handling of query terms that are clearly identifiers instead of prose

### 4. Aggregation only after the exact-match slices improve

Aggregation still has `41` misses, but most of those failures are downstream of the exact-match weakness.

Do not start with broad aggregation tuning. Start with the exact-match slices above, then revisit:

- CDRL counts
- shipment counts
- cross-folder rollups

### 5. Router tuning is secondary

Routing is useful but not the top bottleneck:

- routing correct: `287 / 400`
- retrieval still passes on many wrong-routed queries

So router tuning should come after the exact-match / path retrieval slices, not before them.

## Concrete Next Retrieval Slices

If you want the shortest path to better numbers, build the next slice around these query families:

- **CDRL exact lookups:** `PQ-103`, `PQ-130`, `PQ-152`, `PQ-159`, `PQ-161`, `PQ-184`, `PQ-190`, `PQ-254`, `PQ-255`, `PQ-258`, `PQ-263`
- **Logistics exact lookups:** `PQ-113`, `PQ-121`, `PQ-163`, `PQ-166`, `PQ-167`, `PQ-171`, `PQ-172`, `PQ-173`, `PQ-223`, `PQ-226`, `PQ-231`, `PQ-234`, `PQ-238`
- **Path / folder / file retrieval:** `PQ-146`, `PQ-147`, `PQ-153`, `PQ-202`, `PQ-223`, `PQ-226`, `PQ-234`, `PQ-249`, `PQ-265`, `PQ-283` to `PQ-291`
- **Cross-role aggregation after exact-match improves:** `PQ-147`, `PQ-150`, `PQ-202`, `PQ-206`, `PQ-203`, `PQ-385`, `PQ-497`

## Evidence References

- Clean baseline JSON: `docs/production_eval_results_clean_tier1_2026-04-13.json`
- Clean baseline markdown: `docs/PRODUCTION_EVAL_RESULTS_CLEAN_TIER1_2026-04-13.md`
- Current clean-baseline headline counts: `docs/PRODUCTION_EVAL_400_BASELINE_2026-04-12.md`
- Clean rerun corpus audit and sentinel set: `docs/TIER1_REGEX_CORPUS_AUDIT_2026-04-12_RERUN.md`

## Bottom Line

The clean store is good enough to use as a real benchmark. The next engineering move is not “more broad tuning.” It is:

1. exact CDRL retrieval
2. exact Logistics retrieval
3. identifier/path-heavy retrieval support
4. then aggregation
5. then router polish

