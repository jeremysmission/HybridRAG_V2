# Phase 2C Backfill Targets — 2026-04-12

Scope: focused target list for filling `reference` / `reference_contexts` gaps in `tests/golden_eval/production_queries_400_2026-04-12.json` without changing the scoring lane design.

Snapshot basis: current live 400-query corpus as probed locally on 2026-04-12 late evening MDT. Re-run `python scripts/run_ragas_eval.py --analysis-only` before using this doc if the corpus has changed again.

## Snapshot

- Total query rows: `400`
- Retrieval-side RAGAS eligible now (`reference_contexts` present): `275`
- Fully Phase 2C enriched (`reference` + `reference_contexts` present): `272`
- Missing `reference_contexts`: `125`
- Missing `reference`: `126`
- Fastest wins: `3` queries already have `reference_contexts` and only need a short `reference` answer string

## Fastest Wins First

Backfill these first. They already have `reference_contexts`, so only the answer string is missing:

- `PQ-351` — Field Engineer / `SEMANTIC` / Cybersecurity
- `PQ-370` — Cybersecurity / `SEMANTIC` / Cybersecurity
- `PQ-493` — Aggregation / Cross-role / `SEMANTIC` / CDRLs

These are the cheapest way to move the fully enriched subset from `272` to `275`.

## Highest-Leverage Missing `reference_contexts`

Prioritize by evaluation value, not by raw count alone:

1. `AGGREGATE` gaps: `26`
2. `TABULAR` gaps: `17`
3. `ENTITY` gaps: `21`
4. `SEMANTIC` gaps: `61`

Rationale:

- `AGGREGATE` and `TABULAR` queries are the most likely to expose retrieval-context quality differences once the clean store lands.
- `ENTITY` is next because it helps separate retrieval coverage from structured lookup quality.
- `SEMANTIC` has the largest raw gap, but it is the least urgent bucket for proving retrieval-side differentiation because the corpus already has broad semantic coverage.

## Family Priorities

Missing `reference_contexts` by family:

- `CDRLs`: `42`
- `Logistics`: `31`
- `Program Management`: `20`
- `Cybersecurity`: `17`
- `Site Visits`: `6`
- `Systems Engineering`: `5`
- `Engineering`: `2`
- `SysAdmin`: `1`
- `Asset Mgmt`: `1`

Recommended Phase 2C order:

1. `CDRLs`
2. `Logistics`
3. `Program Management`
4. `Cybersecurity`
5. Everything else

This order maximizes coverage in the heaviest families while also improving the cross-role retrieval lanes most likely to matter during clean-store eval.

## Concrete Starting Set

Start with these missing-`reference_contexts` queries:

- `PQ-147` — sites with 2024 CAP filings and incident numbers
- `PQ-148` — open purchase orders across active option years
- `PQ-149` — sites with installation visits documented
- `PQ-203` — 2024 OCONUS shipments and sites
- `PQ-204` — monitoring system ACAS deliverable timeline
- `PQ-205` — 2024 weekly variance report distribution
- `PQ-206` — sites with ATO re-authorization packages since 2019
- `PQ-210` — overlap between A001 CAP and A002 MSR site sets
- `PQ-118` — Sustainment option year 2 procurement records
- `PQ-124` — 2025 calibration records and covered equipment
- `PQ-122` — recommended spares parts list fields
- `PQ-101` — latest weekly hours variance for FY2024

Why these:

- They cover the `AGGREGATE` and `TABULAR` lanes first.
- They touch the largest missing families.
- They are likely to produce high-signal retrieval-context metrics once grounded.

## Working Rule

Do not widen Phase 2C into broad answer polishing. The goal is to backfill enough `reference_contexts` and short `reference` strings to unlock retrieval-side RAGAS metrics on the most decision-useful subset first.
