# HybridRAG V2 — Sprint Plan

**Status:** post-push authoritative tracker  
**Updated:** 2026-04-20  
**Depth:** 7 sprints planned  
**Source inputs:** main war room, `INFRASTRUCTURE_INVENTORY.md`, `post_push_known_gaps.md`, `SPRINT_SLICE_AGGREGATION_CAPABILITY_2026-04-18.md`, `SPRINT_SLICE_AGGREGATION_FAILURE_RATE_2026-04-18.md`

## Sprint 1 — Demo Integrity + Push-Gate Hygiene

### SP1-01 — Top-K semantics unification
- Scope: reconcile `--top-k` override behavior across `ask.py`, `QueryPipeline.query()`, `retrieve_context()`, and `run_production_eval.py`.
- Why it matters: current benchmark runs can silently diverge from real retrieval behavior, making A/B numbers partially invalid.
- Acceptance:
  - `--top-k N` genuinely overrides the adaptive path, or the CLI flag is removed and docs updated.
  - cache keys align to actual retrieval behavior.
  - `run_production_eval.py` honors `config.yaml` top-k.
  - a regression test verifies three-layer Top-K consistency.
- Dependencies: pushed v3 tree, current query pipeline.
- Tier: A
- Target sprint: 1

### SP1-02 — Cross-substrate factory config-path binding
- Scope: replace hardcoded `data_dir="data"` binding in `boot.py` / cross-substrate assembly with config-driven paths.
- Why it matters: alternate data roots or non-default configs can silently bind joins to the wrong substrate.
- Acceptance: `CrossSubstrateExecutor` takes `data_dir` from config; regression test covers alternate data root.
- Dependencies: current boot/config path.
- Tier: A
- Target sprint: 1

### SP1-03 — Temporal normalization consistency
- Scope: align sidecar temporal normalization with parser coverage for `OY1`-`OY5` and `New Base Year`.
- Why it matters: typed metadata hits currently lag query parsing for higher option years and NBY-style questions.
- Acceptance: sidecar and parser recognize the same temporal families; regression tests cover `OY3`, `OY5`, and `NBY`.
- Dependencies: retrieval metadata store, parser tests.
- Tier: A
- Target sprint: 1

### SP1-04 — Smoke-result artifact ignore rule
- Scope: add `.gitignore` coverage for `tests/smoke_results/**/*.json` and `tests/smoke_results/**/*.md`.
- Why it matters: runtime evidence should not re-enter push gates as accidental source deltas.
- Acceptance: smoke-result artifacts remain untracked by default; historical artifacts remain intact.
- Dependencies: none.
- Tier: A
- Target sprint: 1

### SP1-05 — Sanitize workflow rewrite
- Scope: replace the current sanitize flow with attribution-only scrubbing plus staging-mode execution on a disposable branch/worktree/copy.
- Why it matters: the current script mutates legitimate domain vocabulary (`NEXION`, `ISTO`, `IGS`) and is unsafe on the working tree.
- Acceptance:
  - domain terms pass through unchanged.
  - attribution, secrets, and hardware refs are scrubbed.
  - sanitizer hard-fails on `master`.
  - workflow is documented and encoded in code, not tribal memory.
- Dependencies: today’s push-gate findings.
- Tier: A
- Target sprint: 1

### SP1-06 — Workstation-safe validation metadata refresh
- Scope: refresh workstation-safe validation report text so it matches the current banned-token set and current hygiene doctrine.
- Why it matters: operator-facing validation artifacts are stale and can mislead future push operators.
- Acceptance: report reflects current token policy (`IGS`, `NEXION`, `ISTO`, `RTX 3090` lineage) and current push gate notes.
- Dependencies: sanitize workflow rewrite.
- Tier: B
- Target sprint: 1

## Sprint 2 — Quality Hardening + Commercial-Tier Perception

### SP2-01 — Router accuracy lift
- Scope: raise routing accuracy from the current ~75% band to 90%+ on the 400-query eval.
- Why it matters: wrong routes generate bad answers even when the correct subsystem already exists.
- Acceptance:
  - router accuracy >= 90% on the next 400-query eval.
  - ambiguous-intent regression tests exist.
  - routing confusion matrix is published with before/after.
- Dependencies: current router traces, ambiguous-intent audit set.
- Tier: A
- Target sprint: 2

### SP2-02 — p95 latency reduction
- Scope: reduce p95 wall-clock latency from the current ~30-44s band to <= 15s on a representative query mix.
- Why it matters: users disengage on slow responses even when quality is high.
- Acceptance:
  - p95 <= 15s on a representative mix.
  - no regression on benchmark accuracy.
  - latency note documents batching/packing/OOM-backoff choices.
- Dependencies: current latency traces, query-path profiling.
- Tier: A
- Target sprint: 2

### SP2-03 — Full decision-grade RAGAS run
- Scope: move from partial RAGAS coverage to a credible full-run contract with valid non-LLM context metrics.
- Why it matters: partial benchmark slices are not enough for external credibility.
- Acceptance:
  - full 391-query run is possible.
  - stable-ID or aligned reference-context contract exists.
  - RAGAS report clearly distinguishes readiness-only from valid metric rows.
- Dependencies: stable retrieval/source IDs, RAGAS contract repair.
- Tier: A
- Target sprint: 2

### SP2-04 — Semantic consistency lift
- Scope: lift weak semantic/ENTITY consistency, currently anchored by the weakest RAGAS family score.
- Why it matters: uneven quality across query families creates the “serious homegrown” perception gap.
- Acceptance:
  - ENTITY-family benchmark rises to >= 0.75.
  - no regression on TABULAR / AGGREGATE.
  - hybrid entity+vector scoring and/or relationship-aware retrieval is benchmarked.
- Dependencies: RAGAS full-run contract, entity-retriever tuning.
- Tier: A
- Target sprint: 2

## Sprint 3 — Aggregation Capability Completion

### SP3-01 — Comparative top-N aggregation pack
- Scope: add comparative aggregations across programs, systems, sites, and years for the already-landed substrates.
- Why it matters: demo credibility depends on more than single-filter top-N; users will ask comparison questions.
- Acceptance:
  - at least 12 new GREEN/YELLOW comparative queries added to truth packs.
  - executor supports `compare X vs Y` style grouped output.
  - no regression to current failure aggregation queries.
- Dependencies: current failure, installed-base, and pricing substrates.
- Tier: A
- Target sprint: 3

### SP3-02 — Time-windowed and period-over-period aggregations
- Scope: support month/quarter/range-based aggregation windows and period-over-period deltas.
- Why it matters: the mission implies trend and “as of / over time” questions, not only one-shot totals.
- Acceptance:
  - month, quarter, and rolling-year filters parse deterministically.
  - trend output works for at least two demo families.
  - benchmark pack includes period-over-period checks.
- Dependencies: temporal normalization consistency, query parser extensions.
- Tier: A
- Target sprint: 3

### SP3-03 — Rate-normalized aggregation promotion
- Scope: promote count-only slices to true rate slices wherever denominator coverage exists.
- Why it matters: Q3-style “failure rate” asks remain only partially complete without denominator-backed GREEN paths.
- Acceptance:
  - rate-capable queries return GREEN when denominator exists.
  - missing denominator returns YELLOW/RED honestly.
  - truth pack includes exact rate checks.
- Dependencies: installed-base substrate coverage.
- Tier: A
- Target sprint: 3

## Sprint 4 — Entity Relationships + Logistics Completion

### SP4-01 — Relationship coverage matrix and live join audit
- Scope: enumerate which part, program, site, vendor, maintenance, and shipment relationships are truly queryable today.
- Why it matters: richer Q&A depends on knowing which edges are live versus inferred.
- Acceptance:
  - relationship coverage matrix doc exists.
  - at least 10 representative multi-hop queries are audited.
  - missing edges are turned into explicit slice backlog items.
- Dependencies: entity store, relationship store, current cross-sub executors.
- Tier: A
- Target sprint: 4

### SP4-02 — Vendor / part / site relationship joins
- Scope: make vendor-to-part-to-site relationships deterministic and queryable across pricing and installed-base substrates.
- Why it matters: logistics and sourcing questions need more than standalone vendor spend totals.
- Acceptance:
  - deterministic join path exists.
  - queries like “top vendors for installed parts at site X” work with provenance.
  - benchmark coverage added.
- Dependencies: po_pricing + installed_base substrates.
- Tier: A
- Target sprint: 4

### SP4-03 — Lead-time and vendor performance rollups
- Scope: add vendor performance and lead-time analytics on top of Lane 2 pricing/procurement work.
- Why it matters: logistics completion is not credible without vendor and lead-time views.
- Acceptance:
  - lead-time distributions available where date coverage exists.
  - vendor performance rollups exposed via deterministic executor.
  - low-coverage cases tier down honestly.
- Dependencies: PO family date coverage fixes, vendor/site joins.
- Tier: A
- Target sprint: 4

### SP4-04 — In-transit / shipment visibility substrate
- Scope: add shipment/in-transit visibility as a first-class logistics substrate.
- Why it matters: replacement cost and installed-base are not enough for operational logistics questions.
- Acceptance:
  - shipment-family source map and substrate exist.
  - “where is it / in transit / received yet” queries are benchmarked.
  - provenance paths are populated.
- Dependencies: logistics family maps, receipt/shipment raw corpus families.
- Tier: B
- Target sprint: 4

## Sprint 5 — Maintenance × Logistics Cross-Domain

### SP5-01 — Cross-substrate planner executor
- Scope: join `failure_events`, `po_pricing`, `installed_base`, and `msr_substrate` in a single deterministic plan.
- Why it matters: the highest-value mission questions are cross-domain, not single-substrate.
- Acceptance:
  - at least 3 cross-domain demo queries work end-to-end.
  - executor returns deterministic tables plus sources.
  - fail-closed behavior remains intact for unresolved filters.
- Dependencies: all four substrates stable and benchmarked.
- Tier: A
- Target sprint: 5

### SP5-02 — Cost × failure burden rollups
- Scope: answer questions like “which parts fail most often and cost the most to replace?”
- Why it matters: this is the first business-value bridge between maintenance and logistics.
- Acceptance:
  - exact rollups for frequency + replacement cost are available.
  - benchmark/truth pack covers at least 8 queries.
  - provenance includes both maintenance and pricing sources.
- Dependencies: SP5-01.
- Tier: A
- Target sprint: 5

### SP5-03 — Site maintenance burden + supply risk
- Scope: combine maintenance burden, installed-base exposure, and long lead-time risk by site.
- Why it matters: this is the operator/PM view of where programs are vulnerable.
- Acceptance:
  - site-level risk output works for at least 5 real sites.
  - deterministic scoring method is documented.
  - out-of-range or low-coverage cases tier down honestly.
- Dependencies: SP5-01, SP4-03.
- Tier: B
- Target sprint: 5

## Sprint 6 — Program Management Rollups

### SP6-01 — Program portfolio rollups
- Scope: add cross-program portfolio views and program-to-program comparisons.
- Why it matters: PM-level questions need a top-down layer, not only site/part detail.
- Acceptance:
  - portfolio-level rollups exist for at least two programs/systems.
  - program comparison queries are benchmarked.
  - provenance paths remain visible.
- Dependencies: entity relationship coverage, cross-domain executor.
- Tier: A
- Target sprint: 6

### SP6-02 — Program health dashboard slices
- Scope: define and expose health slices combining failure, logistics, and maintenance signals.
- Why it matters: this is the presentation layer for executive and PM stakeholders.
- Acceptance:
  - health slice doc and demo queries exist.
  - each signal has a deterministic source.
  - low-confidence slices downgrade rather than narrate.
- Dependencies: SP5-01, SP6-01.
- Tier: B
- Target sprint: 6

### SP6-03 — PM benchmark pack
- Scope: add a benchmark/truth-pack family specifically for PM and rollup questions.
- Why it matters: PM-facing capability should have its own gate rather than inheriting maintenance/logistics packs.
- Acceptance:
  - 20+ PM queries added with tier targets.
  - benchmark runner reports PM family separately.
- Dependencies: PM slice definitions.
- Tier: B
- Target sprint: 6

## Sprint 7 — Operator Surface + Retrieval Architecture

### SP7-01 — RAGAS contract repair
- Scope: fix path-anchor versus chunk-text mismatch and add ID-based RAGAS options.
- Why it matters: current RAGAS is useful but partially under-reports quality for this corpus contract.
- Acceptance:
  - valid RAGAS cohorts are separated from readiness-only rows.
  - ID-based or aligned-context metrics are available.
  - per-family RAGAS reporting is explicit.
- Dependencies: benchmark doctrine, stable retrieval/source IDs.
- Tier: A
- Target sprint: 7

### SP7-02 — Forge → V2 contract upgrade
- Scope: enrich ingest/schema handoff so more structure survives into retrieval and aggregation layers.
- Why it matters: reducing post-hoc inference lowers error pressure across all pillars.
- Acceptance:
  - richer schema fields survive ingest.
  - regression test verifies handoff.
  - at least one downstream executor consumes the richer schema directly.
- Dependencies: import/export pipeline ownership.
- Tier: B
- Target sprint: 7

### SP7-03 — Hierarchical retrieval / parent-section expansion
- Scope: add parent-section expansion for long-form enterprise docs.
- Why it matters: improves evidence quality on structured documents where one chunk is too narrow.
- Acceptance:
  - bounded-latency parent expansion path exists.
  - retrieval benchmark shows lift on long-form cohort.
- Dependencies: retrieval metadata richness.
- Tier: B
- Target sprint: 7

### SP7-04 — GUI promotion + production QA
- Scope: merge local GUI improvements, then run production-branch GUI QA.
- Why it matters: operator trust depends on evidence surface as much as backend quality.
- Acceptance:
  - promoted GUI branch passes harness + human QA.
  - no regression in core query path.
- Dependencies: GUI lane stabilization, current production branch.
- Tier: C
- Target sprint: 7

## Sprint Audit Summary

- Planned sprints: 7
- Planned slices: 24
- Themes:
  - Sprint 1: demo integrity + push-gate hygiene
  - Sprint 2: quality hardening + commercial-tier perception
  - Sprint 3: aggregation capability completion
  - Sprint 4: entity relationships + logistics completion
  - Sprint 5: maintenance x logistics cross-domain
  - Sprint 6: program management rollups
  - Sprint 7: operator surface + retrieval architecture
- Pillar coverage:
  - Quality hardening: Sprint 2
  - Aggregation completion: Sprints 3, 5, 6
  - Entity relationships: Sprint 4
  - Logistics completion: Sprints 4, 5
  - Maintenance cross-domain: Sprint 5
  - Program management: Sprint 6

Signed: Agent-C | C:\HybridRAG_V2 | 2026-04-20 MDT
