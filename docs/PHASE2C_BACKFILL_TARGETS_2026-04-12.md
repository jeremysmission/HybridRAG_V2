# Phase 2C Backfill Targets — 2026-04-12

Scope: focused target-selection rules for filling `reference` / `reference_contexts` gaps in `tests/golden_eval/production_queries_400_2026-04-12.json` without changing the scoring lane design.

This file is intentionally not a static snapshot of the live corpus. The 400-query file is moving. Generate the current target list from the live tree with:

```powershell
.\.venv\Scripts\python.exe scripts\report_phase2c_backfill_targets.py
```

For a larger starting set:

```powershell
.\.venv\Scripts\python.exe scripts\report_phase2c_backfill_targets.py --limit 25
```

## Priority Rules

Backfill in this order unless a coordinator explicitly changes the goal:

1. Queries that already have `reference_contexts` and only need a short `reference`
2. `AGGREGATE` gaps
3. `TABULAR` gaps
4. `ENTITY` gaps
5. `SEMANTIC` gaps

Reasoning:

- The first bucket is the cheapest way to increase the fully Phase 2C enriched subset.
- `AGGREGATE` and `TABULAR` are the most likely to expose retrieval-context quality differences during clean-store eval.
- `ENTITY` is next because it helps separate retrieval coverage from structured lookup quality.
- `SEMANTIC` is important, but it is the least urgent bucket for demonstrating retrieval-side differentiation because the corpus already has broader semantic coverage.

## Family Priority Rules

Within a query-type bucket, prioritize in this family order:

1. `CDRLs`
2. `Logistics`
3. `Program Management`
4. `Cybersecurity`
5. `Site Visits`
6. `Systems Engineering`
7. Everything else

This maximizes value in the heaviest families while also improving the cross-role retrieval lanes most likely to matter during clean-store eval.

## Working Rule

Do not widen Phase 2C into broad answer polishing. The goal is to backfill enough `reference_contexts` and short `reference` strings to unlock retrieval-side RAGAS metrics on the most decision-useful subset first.
