# HybridRAG V2 — Capability Roadmap

**Status:** local-only planning artifact after `V2 merged-for-push v3`  
**Updated:** 2026-04-20  
**Purpose:** define what is shipped today, what is partial, what is missing, and what slices should land next across the five core capability pillars.

## 1. Current State Matrix

| Pillar | Capability | Status | Current state |
|--------|------------|--------|---------------|
| Aggregation capability completion | Failure top-N / ranked failure counts | Shipped | Deterministic failure substrate is live, benchmarked, and push-ready. |
| Aggregation capability completion | Rate-normalized failure answers | Partial | Installed-base denominator landed, but GREEN rate coverage is still narrower than count coverage. |
| Aggregation capability completion | Comparative / time-windowed aggregation | Missing | Current executors are strongest on direct single-slice queries; comparison/trend asks are not yet first-class. |
| Entity relationships | Part / site / vendor / program identity | Partial | Identity exists via aliases and substrates, but relationship coverage is not yet enumerated or benchmarked as a system. |
| Entity relationships | Multi-hop graph-style traversal | Missing | Relationship store exists, but demo-safe multi-hop capability is not a live operator feature. |
| Logistics completion | PO pricing / replacement cost | Shipped | Pricing substrate and replacement-cost style logic are live. |
| Logistics completion | Installed-base / vendor / site history | Shipped | Installed-base substrate, vendor aggregation, and site-history slices landed. |
| Logistics completion | Shipment / in-transit / receipt status | Partial | Source families are known, but end-to-end deterministic shipment visibility is not fully promoted. |
| Maintenance x logistics | Failure counts | Shipped | Failure-event substrate is live. |
| Maintenance x logistics | MSR / ASV / RTS aggregations | Shipped | MSR substrate landed with site/year aggregations. |
| Maintenance x logistics | Cross-domain joins | Missing | There is no banked executor that joins failure, pricing, installed-base, and MSR in one plan. |
| Program management / rollups | Program filters | Partial | Program-aware filtering exists in routing and substrate selection. |
| Program management / rollups | Program-level portfolio views | Missing | No dedicated PM rollup benchmark or portfolio surface is live today. |
| Quality hardening | Router accuracy | Partial | Routing is serviceable but still around the mid-70% band, which is below commercial-grade expectations. |
| Quality hardening | Latency stage budgets | Partial | p95 wall clock remains roughly 30-44s on older eval evidence, and stage-level budgets are not yet first-class release gates. |
| Quality hardening | Decision-grade RAGAS coverage | Partial | RAGAS exists and is useful, but still needs a credible full-run contract. |
| Quality hardening | Semantic consistency | Partial | ENTITY / semantic-heavy questions remain noticeably weaker than deterministic structured lanes. |
| Quality hardening | Canonical release scoreboard | Missing | Multiple eval artifacts still tell different stories; there is no single trusted release scoreboard artifact. |
| Quality hardening | Merge / integration discipline | Partial | Merged-tree push discipline improved today, but versioned interface checks and merged-tree CI are not yet formalized. |

## 2. Gap Inventory By Pillar

### Pillar 1 — Aggregation capability completion

**Shipped today**
- failure top-N counts
- vendor aggregation
- site-history aggregation
- ASV completions per site/year
- inventory recommender / replacement-cost foundations

**Partially shipped**
- rate-normalized queries where denominator exists
- comparative aggregation via ad hoc combinations rather than a first-class executor

**Missing**
- time-windowed and period-over-period aggregations
- cross-program/site comparative rollups
- benchmark packs for broader aggregation families

**Dependencies**
- denominator completeness
- canonical time normalization
- cross-substrate join planning

### Pillar 2 — Entity relationships

**Shipped today**
- alias-backed entity identity for key systems/sites
- relationship and entity infrastructure in store layer

**Partially shipped**
- practical relationship use inside deterministic query answers
- relationship provenance for cross-sub questions

**Missing**
- relationship coverage matrix
- benchmarked multi-hop queries
- graph-style relationship traversal at the operator layer

**Dependencies**
- relationship-store coverage
- vendor/site/part normalization
- PM and cross-domain query definitions

### Pillar 3 — Logistics completion

**Shipped today**
- PO pricing substrate
- installed-base substrate
- vendor spend aggregation
- first-install date / site history

**Partially shipped**
- receipt / open-order / lead-time analytics
- inventory recommendation confidence calibration

**Missing**
- shipment/in-transit visibility
- vendor performance rollups
- deterministic “received vs ordered vs outstanding as of date” completion

**Dependencies**
- procurement date coverage
- shipment/receipt family extraction
- stronger join layer between pricing, installed-base, and receipt families

### Pillar 4 — Maintenance aggregations + cross-domain

**Shipped today**
- failure-event counts
- MSR ASV/RTS substrate

**Partially shipped**
- maintenance burden summaries by site
- failure-rate style views where denominator exists

**Missing**
- cost x failure joins
- maintenance burden x supply-risk joins
- scheduled maintenance rollups

**Dependencies**
- cross-substrate executor
- robust site/system/year canonicalization
- pricing and installed-base stability

### Pillar 5 — Program management / rollups

**Shipped today**
- basic program-aware routing/filtering

**Partially shipped**
- program filters inside some deterministic answers

**Missing**
- program portfolio views
- executive / PM benchmark pack
- health dashboard slices backed by deterministic metrics

**Dependencies**
- entity relationship coverage
- cross-domain executor
- clear PM question families and truth packs

### Pillar 6 — Quality hardening

> QA strategic framing: do not spend the next sprint inventing a new retrieval trick. Spend it making routing, semantic retrieval, latency, and eval trustworthy enough that the already-strong structured architecture consistently shows through.
>
> Practical planning implication: Pillar 6 should lead the next 2-3 sprints before Pillars 1-5 compete for priority.

**Shipped today**
- strong architecture baseline: hybrid retrieval, deterministic substrates, fail-closed tiering, QA gates

**Partially shipped**
- router, latency, RAGAS, and semantic consistency all have measurable evidence and active diagnostics
- merged-tree push discipline improved materially during the final push gate

**Missing**
- commercial-tier routing accuracy
- stage-budgeted latency discipline by path and family
- full decision-grade 391/391 RAGAS contract
- semantic quality lift on ENTITY-heavy asks
- one canonical release scoreboard
- versioned interface discipline plus merged-tree CI gate

**Dependencies**
- benchmark doctrine
- stable-ID RAGAS migration
- query-path profiling
- entity/relationship tuning
- merged-tree smoke panel and versioned substrate contracts

## 3. Sprint Slice Proposals By Pillar

### Pillar 1 — Aggregation capability completion

#### AGG-01 — Comparative aggregation executor
- Tier: A
- Scope: add “X vs Y” and cross-site / cross-system grouped comparison outputs.
- Why: demo users will compare sites/systems, not only ask single-slice top-N questions.
- Acceptance: 12-query comparative truth pack; deterministic comparison output; no regression to current failure aggregation.
- Dependencies: current substrates, alias stability.

#### AGG-02 — Time-windowed aggregation pack
- Tier: A
- Scope: add monthly / quarterly / rolling-year aggregations plus period-over-period delta logic.
- Why: mission scope includes trend and “as of / over time” views.
- Acceptance: parser + executor handle month/quarter/year windows; benchmark pack includes period delta checks.
- Dependencies: temporal normalization consistency.

### Pillar 2 — Entity relationships

#### ENT-01 — Relationship coverage matrix
- Tier: A
- Scope: enumerate which entity/relationship edges are truly live and queryable today.
- Why: prevents over-claiming and directs the next graph-style work.
- Acceptance: coverage matrix doc, 10 audited multi-hop queries, explicit missing-edge backlog.
- Dependencies: entity + relationship store inspection.

#### ENT-02 — Vendor/part/site relationship joins
- Tier: A
- Scope: formalize vendor-part-site joins for deterministic logistics answers.
- Why: logistics and PM questions require these joins as primitives.
- Acceptance: deterministic join path, benchmark pack, provenance on results.
- Dependencies: installed-base + pricing substrates.

### Pillar 3 — Logistics completion

#### LOG-01 — Lead-time and vendor performance rollups
- Tier: A
- Scope: compute vendor performance, lead-time ranges, and procurement reliability rollups.
- Why: pricing alone does not answer the real logistics mission.
- Acceptance: deterministic lead-time queries, vendor performance output, coverage-aware tiering.
- Dependencies: receipt/open-order date coverage.

#### LOG-02 — Shipment / in-transit visibility substrate
- Tier: B
- Scope: build a shipment/receipt substrate for in-transit and received-status questions.
- Why: “where is it / has it arrived / what is still open” is central to logistics completion.
- Acceptance: shipment-family map, substrate, benchmark pack, provenance.
- Dependencies: shipment/receipt family mining.

### Pillar 4 — Maintenance aggregations + cross-domain

#### MXL-01 — Cross-substrate planner executor
- Tier: A
- Scope: join failure, pricing, installed-base, and MSR substrates in one deterministic plan.
- Why: cross-domain joins unlock the most valuable maintenance x logistics questions.
- Acceptance: three demo-worthy cross-domain queries return deterministic tables plus sources.
- Dependencies: all four substrates stable, consistent canonical filters.

#### MXL-02 — Cost x failure burden rollups
- Tier: A
- Scope: combine failure frequency and replacement cost into ranked risk outputs.
- Why: this is the first operationally meaningful cross-domain maintenance/logistics answer family.
- Acceptance: benchmark/truth pack of at least 8 queries, live CLI/GUI output, provenance from both domains.
- Dependencies: MXL-01.

### Pillar 5 — Program management / rollups

#### PM-01 — Program portfolio views
- Tier: A
- Scope: add cross-program rollups and side-by-side program comparisons.
- Why: PM stakeholders need top-down views rather than only part/site answers.
- Acceptance: two program comparison families with deterministic output and sources.
- Dependencies: entity relationships, cross-substrate executor.

#### PM-02 — Program health dashboard slices
- Tier: B
- Scope: define health slices using maintenance, logistics, and cost signals.
- Why: PM-facing demo narratives need stable slices, not ad hoc synthesis.
- Acceptance: documented health slice set, deterministic backing signals, benchmark pack.
- Dependencies: PM-01, MXL-01.

### Pillar 6 — Quality hardening

#### QLT-01 — Router accuracy lift
- Tier: A
- Scope: raise router accuracy from roughly 75% to 90%+, build a locked router gold set by family, and add deterministic pre-router rules for obvious structured intents.
- Why: wrong routing causes bad answers even when the right subsystem already exists.
- Acceptance:
  - router accuracy >= 90% on the locked router set.
  - confusion matrix is reported by family: `SEMANTIC`, `ENTITY`, `AGGREGATE`, `TABULAR`, `cross-sub`, `inventory`, `PO`.
  - deterministic pre-router rules catch obvious structured intents before LLM routing.
  - every miss is classified as rules, aliases, or prompt-model issue.
  - routing becomes a release gate rather than a background metric.
- Dependencies: routing confusion matrix, ambiguous-intent review set.

#### QLT-02 — Stage-budget latency discipline
- Tier: A
- Scope: instrument route, retrieve, rerank, aggregate, and generate stages; define budgets by path; short-circuit deterministic paths; cache repeated benchmark/demo queries aggressively.
- Why: latency is a perception barrier that keeps V2 below commercial-grade experience.
- Acceptance:
  - stage budgets are documented and enforced.
  - deterministic aggregate and cross-sub paths are sub-second.
  - semantic path has a documented bounded budget.
  - p50 and p95 are reported by query family on every run.
  - no regression on benchmark quality.
- Dependencies: query-path profiling, batching/packing work, OOM-backoff tuning.

#### QLT-03 — Full decision-grade RAGAS run
- Tier: A
- Scope: move from partial RAGAS to a credible full 391/391 run with valid context metrics.
- Why: partial evals are not enough for external credibility.
- Acceptance: full run completed; non-LLM context metrics are credible under stable-ID or aligned-context contract.
- Dependencies: stable-ID context references, RAGAS contract repair.

#### QLT-04 — Semantic consistency lift
- Tier: A
- Scope: raise ENTITY/semantic performance from the current weak point to at least 0.75-equivalent quality, with explicit retrieval error taxonomy.
- Why: semantic-heavy queries underperform structured lanes and create uneven UX.
- Acceptance:
  - retrieval error buckets are reported every eval run: wrong family, wrong doc type, wrong time slice, right doc low rank, no useful evidence.
  - tuning decisions are made against bucket counts, not only headline score.
  - per-family reporting prevents structured-lane strength from masking semantic weakness.
  - ENTITY-family lift to >= 0.75 with no regression to TABULAR / AGGREGATE.
  - bucket-level regression tests exist.
- Dependencies: entity retriever tuning, relationship-aware retrieval, hybrid scoring review.

#### QLT-05 — Canonical release scoreboard
- Tier: A
- Scope: declare one canonical release scoreboard with four sections: router, semantic retrieval, deterministic aggregation exactness, and UX/CLI/GUI smoke.
- Why: today’s push showed that multiple evals can tell different stories; a release needs one trusted scoreboard.
- Acceptance:
  - `python scripts/run_release_scoreboard.py` produces one artifact under one path.
  - any team member can reproduce the same scoreboard numbers.
  - banked truth packs are SHA-locked.
  - RAGAS is supporting evidence until stable IDs land, not the only story.
- Dependencies: benchmark doctrine, truth-pack freeze discipline, stable artifact pathing.

#### QLT-06 — Merge / integration discipline
- Tier: A
- Scope: treat lane-specific executors and store contracts as versioned interfaces and add a merged-tree CI gate before push-ready claims.
- Why: today’s near-miss class would have been caught earlier by a merged-tree gate and permanent smoke panel.
- Acceptance:
  - push-ready requires green merged-tree CI.
  - versioned contract breaks fail loud.
  - a push-gate smoke panel always runs on the merged tree, starting with the six known critical checks.
  - CLI output is ASCII-safe by default to avoid the Unicode / codepage crash class.
- Dependencies: merged-tree smoke suite, CI entrypoint, CLI output hygiene.

## 4. Cross-Pillar Dependency Map

| Slice | Blocked by | Unblocks |
|-------|------------|----------|
| AGG-01 | current substrates only | PM-01, MXL-01 |
| AGG-02 | temporal normalization consistency | PM-02, LOG-01 |
| ENT-01 | none | ENT-02, PM-01 |
| ENT-02 | ENT-01, installed-base/pricing stability | LOG-01, PM-01 |
| LOG-01 | receipt/open-order date coverage, ENT-02 | MXL-02, PM-02 |
| LOG-02 | shipment family mining | future shipment-status Q&A |
| MXL-01 | AGG-01, ENT-02, substrate stability | MXL-02, PM-02 |
| MXL-02 | MXL-01, LOG-01 | PM-02 |
| PM-01 | ENT-01, MXL-01 | PM-02 |
| PM-02 | PM-01, MXL-02, AGG-02 | executive demo / PM benchmark lane |
| QLT-01 | routing diagnostics | better perceived quality across all pillars |
| QLT-02 | latency profiling | better demo trust across all pillars |
| QLT-03 | stable-ID context references | trustworthy benchmark ladder |
| QLT-04 | entity/relationship tuning, QLT-03 | stronger semantic lane and PM queries |
| QLT-05 | truth-pack freeze discipline, benchmark doctrine | one trusted release gate for all pillars |
| QLT-06 | merged-tree CI, versioned interfaces | safer promotions across all pillars |

## 5. Proposed Sprint Order

1. **Quality hardening first**
   - competitive positioning is limited more by route, latency, benchmark trust, and merge discipline than by one more niche aggregation type
   - improvements here help every already-landed capability feel stronger
   - this pillar should lead the next 2-3 sprints before broader expansion work competes for priority
2. **Aggregation completion second**
   - highest immediate demo value
   - smallest dependency surface
   - closes the current “mostly works but not comprehensive” gap
3. **Entity relationships + logistics third**
   - needed for clean vendor/site/program joins
   - enables richer deterministic logistics answers
4. **Maintenance x logistics fourth**
   - cross-domain value spike
   - depends on the earlier relationship/logistics cleanup
5. **Program management fifth**
   - highest-level rollups should come after the lower-level joins are proven
6. **Operator/benchmark architecture in parallel**
   - keeps the benchmark lane honest
   - prevents future push/QA friction from slowing capability work

## 6. Demo-Scope Completion Definition

Aggregation capability is demo-scope complete when all of the following are true:
- direct top-N and grouped count questions are GREEN where data exists
- rate questions are GREEN where denominator exists and YELLOW/RED otherwise
- comparative and time-windowed aggregation queries are benchmarked
- at least one cross-domain maintenance x logistics query family is live
- PM/portfolio queries have a dedicated deterministic benchmark lane
- router accuracy is at or above 90% on the demo pack
- p95 latency is close enough to interactive use that operators stay engaged
