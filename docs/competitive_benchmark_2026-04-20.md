# HybridRAG V2 — Competitive Benchmark Note

**Status:** local-only post-push synthesis  
**Updated:** 2026-04-20  
**Attribution:** this note is a synthesis of external analysis and public 2024-2026 sources, not an internal self-rating.

## Purpose

Capture the four quality/perception gaps that most clearly separate HybridRAG V2 from commercial-grade operator experience, even after the strong architecture and deterministic aggregation work landed.

## Inputs

### Internal evidence
- `docs/production_eval_results_lane1_retrieval_router_400_2026-04-13.json`
- `docs/production_eval_results_lane1_latency_followup_400_2026-04-13.json`
- `docs/ragas_frontier_targets_2026-04-20.md`
- main war room outcomes from the merged push

### External analysis / public sources
- RAGAS metrics framework and target floors summarized in `docs/ragas_frontier_targets_2026-04-20.md`
- RAGAS docs and public benchmark commentary cited there
- public RAG evaluation guidance and retrieval benchmark commentary from 2025-2026 source pack used by Researcher

## Four near-term commercial-tier gaps

### 1. Router accuracy gap

**Current evidence**
- `routing_correct = 301 / 400` in `production_eval_results_lane1_retrieval_router_400_2026-04-13.json`
- effective routing accuracy is therefore about `75%`

**Why it matters**
- route errors are multiplicative failures
- they cause bad answers even when the correct subsystem already exists
- commercial products feel “smarter” partly because they route more consistently, not just because they retrieve more text

**Competitive implication**
- this is a near-term trust gap, not an academic gap
- router accuracy improvement has demo value across every persona and every query family

### 2. p95 latency gap

**Current evidence**
- `p95_wall_clock_ms = 43969` in the router-oriented run
- `p95_wall_clock_ms = 34867` in the latency follow-up run

**Why it matters**
- even when answers are correct, 30-44 second tails feel materially worse than commercial-grade UX
- users interpret slow systems as uncertain or brittle

**Competitive implication**
- latency is a perception barrier
- reducing tail latency will likely have more demo impact than adding one more niche executor

### 3. Decision-grade benchmark gap

**Current evidence**
- RAGAS exists and is real in this repo
- but the current contract still mixes path-anchor `reference_contexts` with retrieved chunk text for part of the pack
- the team therefore has partial or caveated metric credibility rather than a clean 391/391 decision-grade run

**Why it matters**
- a partial eval is useful for engineering
- it is not strong enough as an external-facing benchmark claim

**Competitive implication**
- benchmark credibility is part of commercial credibility
- without a clean full-run contract, V2 looks harder to trust than its architecture deserves

### 4. Semantic consistency gap

**Current evidence**
- Researcher’s frontier targets packet explicitly flags ENTITY / semantic quality as the weakest lane
- deterministic structured lanes are stronger than semantic-heavy retrieval lanes

**Why it matters**
- users do not grade systems by subsystem boundaries
- if one family feels sharp and another feels mushy, the whole product feels uneven

**Competitive implication**
- V2 already looks stronger on structured / deterministic queries than many commercial systems
- the next perception lift comes from making semantic-heavy asks feel less like a different product

## Prioritization takeaway

If the goal is to look more commercial-competitive in the next sprint window, the most valuable order is:

1. router accuracy
2. p95 latency
3. decision-grade full RAGAS
4. semantic consistency
5. only then broader aggregation family expansion

This does **not** mean new capabilities stop mattering. It means the next-visible demo lift is more likely to come from:
- fewer wrong routes
- faster answers
- cleaner benchmark credibility
- less uneven semantic behavior

than from adding another aggregation type that commercial rivals may not attempt at all.

## Independent external comparative assessment

An external independent review of the current repo artifacts reached a useful bottom-line judgment:

- **versus typical homegrown RAG:** clearly ahead
- **versus strong domain-tuned homegrown RAG:** competitive, upper-mid tier
- **versus off-the-shelf commercial RAG/chat products:** weaker overall, but stronger on exact domain aggregation and abstention discipline
- **versus heavily customized commercial deployment on the same corpus:** still behind

That assessment lines up with the evidence in-tree:

### Where V2 is strong

- best family-level retrieval artifact shows `323/391` top-1 PASS (`82.6%`) and `374/391` top-5 coverage (`95.7%`)
- AGGREGATE family in that artifact is especially strong at `88/102` PASS and `101/102` top-5
- deterministic aggregation is substantially more mature than what many generic commercial RAG systems attempt
- fail-closed evidence tiers and structured answers are already first-class, not an afterthought

### Where V2 is still below commercial-enterprise polish

- stricter operational evals land around `249/400` PASS and `321/400` PASS+PARTIAL
- router accuracy is only about `75%`
- p95 wall-clock latency is still in the `30-44s` band
- RAGAS readiness is strong, but the current scored lane is not yet decision-grade because of the path-anchor/reference contract gap

### Why that matters

The architecture is already serious. The limiting factor is not whether the system has a credible substrate pattern; it does. The limiting factor is that:

- structured/entity/aggregation lanes are stronger than
- semantic consistency, router reliability, p95 latency, and end-to-end eval maturity

That split is exactly why the roadmap now elevates quality hardening ahead of some broader capability expansion.

## Planned translation into sprint slices

These findings are now represented in:
- `docs/sprint_plan.md`
- `docs/capability_roadmap_2026-04-20.md`

Specifically:
- quality hardening now has its own pillar
- those slices are prioritized before broader capability-expansion work

## Referenced evidence

- `docs/PRODUCTION_EVAL_RESULTS_2026-04-11.md`
- `docs/production_eval_results_lane1_retrieval_router_400_2026-04-13.json`
- `docs/production_eval_results_agent1_baseline_20260415_131731.json`
- `docs/ragas_eval_gui_2026-04-19_004213.json`
- `docs/ragas_gpt4o_391_2026-04-20_partial.txt`
- `docs/ragas_frontier_targets_2026-04-20.md`
- `docs/aggregation_evidence_contract.md`
- `docs/qa/SPRINT_SLICE_AGGREGATION_QA_REPORT_2026-04-19.md`
- `docs/QA_WORKBENCH_QA_READY_CHECKLIST_2026-04-17.md`
