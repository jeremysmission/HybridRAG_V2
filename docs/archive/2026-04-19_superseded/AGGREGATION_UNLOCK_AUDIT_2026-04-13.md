# Aggregation Unlock Audit — 2026-04-13

**Purpose:** Separate near-term honest aggregation unlocks from true graph/global blockers.

## Executive Read

- The current aggregation surface is large, but it is **not primarily a GraphRAG problem**.
- Working split from the sidecar:
  - `70` filed-deliverable-index problems
  - `29` narrow validated count problems
  - `3` logistics row-table problems
  - `1` Tier 1 entity-cleanup problem
  - `1` relationship / multi-hop problem
  - `11` true graph/global-summary problems
  - `4` gold/scope problems
  - `2` keep-off-stage cases
- Coordinator conclusion:
  - roughly `99/121` aggregation-shaped rows are still normalization/index/substrate work
  - only a small residual set is true graph/global work

## Stepwise Roadmap

### Step A

Build a normalized filed-deliverable index with canonical keys for:

- contract
- CDRL family
- artifact subtype
- site
- system
- date/month
- procurement period/status

### Step B

Add narrow logistics row substrate for:

- received POs
- shipments
- calibration
- spares

### Step C

Only after A and B, evaluate the residual graph/global set as a separate lane.

## Highest-Value Families

- A009 / A027 / A002 / A006 / A007 / A013 contract-date-site enumerations
- received-PO period questions
- shipment date/site joins
- CAP / MSR and contract/site intersections

## Low-Value Distractions For Now

- broad graph/global work
- abstract family-comparison prompts
- full-corpus “everything” rollups

## Product Rule

- Do not diagnose every aggregation complaint as “needs GraphRAG.”
- Most of the current aggregation pain is still unresolved artifact normalization and row truth.
