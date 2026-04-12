# Stale Doc Retirement Map — 2026-04-12

**Purpose:** Retire the most dangerous stale operator/demo docs without editing them in place.
**Rule:** Leave retired docs in repo as history. Do not use them as May 2 operator truth.

## Retirement Rule

Any doc still anchored to `17,707`, `40,981`, `8,017,607`, `27.6 million`, `25/25 final`, or `10/10 rehearsal` is non-authoritative for May 2 operations unless it is reissued under a newer dated canonical packet.

## Immediate Retirements

| Rank | Doc | Disposition | Why unsafe now | Replace with |
|---|---|---|---|---|
| 1 | `docs/DEMO_DAY_CHECKLIST_2026-04-07.md` | Retire from operator use now | Expects `17,707` chunks and `40,981` entities, uses a 10-query buffet, and explicitly includes an `AUDIENCE` "ask anything" segment. | `docs/MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md` |
| 2 | `docs/DEMO_SCRIPT_2026-04-05.md` | Retire from stage script use now | Claims `27.6 million` chunks, treats aggregation as a live proof point, and includes risky audience-choice / broad-claim language. | `docs/MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md` |
| 3 | `docs/ENVIRONMENT_ASSUMPTIONS_2026-04-08.md` | Retire from operator use now | Still describes the `17,707` / `40,981` environment, outdated relationship counts, and early-store disk assumptions. | `docs/MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md` plus `docs/BACKGROUND_RUNBOOK_2026-04-12.md` |
| 4 | `docs/SPRINT_SYNC.md` | Retire from readiness use now | Still says Sprint 14/15 are done, records `25/25` and `10/10 rehearsal` language, and overstates current readiness. | `docs/COORDINATOR_STATE_2026-04-12_evening.md` plus `docs/MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md` |
| 5 | `docs/CRASH_RECOVERY_2026-04-12.md` | Historical only for demo ops | Still records `8,017,607` entities and an earlier blocker layout. Good background; wrong as current operator truth. | `docs/MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md` |
| 6 | `docs/V1_VS_V2_COMPARISON_2026-04-07.md` | Retire from talking-point use now | Still compares against the `17,707` / `40,981` world and implies stronger aggregation proof than the current system can honestly claim. | `docs/MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md` |

## Secondary Historical-Only References

| Doc | Why not authoritative |
|---|---|
| `docs/PRODUCTION_EVAL_RESULTS_2026-04-11.md` | Good evidence doc, but its entity-count snapshot is stale and should not be used as the live store count. |
| `docs/PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md` | Good query-design rationale, but still anchored to the earlier `8,017,607` store snapshot. |
| `docs/LAPTOP_CHUNK_COUNT_DRIFT_2026-04-12.md` | Useful investigation history; not a demo-day source of truth. |
| `docs/ENTITY_STORE_AUDIT_2026-04-08.md` | Historical audit of an older, much smaller store state. |

## Canonical Replacements

- Demo claims, counts, and pre-demo checks: `docs/MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md`
- Machine scheduling and dependency gates: `docs/BACKGROUND_RUNBOOK_2026-04-12.md`
- Live lane/blocker status: `docs/COORDINATOR_STATE_2026-04-12_evening.md`
- Honesty boundary on claims: `docs/V2_DEMO_READINESS_GAP_ANALYSIS_2026-04-12.md`
