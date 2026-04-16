# Queries To Avoid For Demo — 2026-04-13

**Purpose:** Consolidate the current query IDs that should stay out of the live demo lane, even if they benchmark as `PASS` or look superficially impressive.

**Rule:** If a query is on this list, do not use it on stage without an explicit fresh re-verification against the current machine, store, and rubric.

## Keep Off Stage — Aggregation / Structural Risk

These remain unsafe because they are aggregation-heavy, substrate-dependent, gold-weak, or structurally beyond the current honest product boundary.

- `PQ-146`
- `PQ-147`
- `PQ-148`
- `PQ-150`
- `PQ-153`
- `PQ-156`
- `PQ-203`
- `PQ-204`
- `PQ-208`
- `PQ-210`
- `PQ-263`
- `PQ-264`
- `PQ-323`
- `PQ-324`
- `PQ-374`
- `PQ-380`
- `PQ-381`
- `PQ-444`
- `PQ-492`
- `PQ-500`

## Keep Off Stage — Narration-Unsafe Even If They Score PASS

These are risky because their gold/rubric framing is hedged, their answer shape is weakly grounded, or they can create false confidence on stage.

- `PQ-102`
- `PQ-107`
- `PQ-118`
- `PQ-143`
- `PQ-148`
- `PQ-151`
- `PQ-154`
- `PQ-156`
- `PQ-204`
- `PQ-334`
- `PQ-348`
- `PQ-358`
- `PQ-379`

## Why These Stay Off Stage

- Some ask for `how many` or `full set` while the current gold only supports `at least N`.
- Some depend on broad aggregation that is still not honest enough to present as solved.
- Some treat folder-mining or file-family evidence as if it were the same thing as grounded content extraction.
- Some are benchmark-acceptable but still unsafe for live operator narration.

## Safe Starting Points Instead

Use the current canonical packet and reboot handover to choose from the safer live-query pool:

- `docs/MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md`
- `docs/REBOOT_HANDOVER_2026-04-13.md`
- `docs/COORDINATOR_CONTINUITY_NOTES_2026-04-13.md`
