# Source Of Truth Map — 2026-04-12

**Purpose:** Define which docs are canonical, which are historical, and which are unsafe for current operator or QA use.
**Rule:** If a doc conflicts with a live repo-local probe, the live repo-local probe wins.

## Canonical

| Need | Canonical source | Why |
|---|---|---|
| Live counts and reproducible evidence | `docs/AUTHORITATIVE_FACTS_AND_SOURCES_2026-04-12.md` | Probe-backed current facts with exact paths and commands |
| Current demo claims, guardrails, and pre-demo checks | `docs/MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md` | Current operator-facing May 2 packet |
| Honesty boundary on what V2 can and cannot claim | `docs/V2_DEMO_READINESS_GAP_ANALYSIS_2026-04-12.md` | Current RED/YELLOW read on retrieval, aggregation, router, and stage risk |
| Which legacy docs are retired or unsafe | `docs/STALE_DOC_RETIREMENT_MAP_2026-04-12.md` | Current stale-doc disposition map |

## Historical But Still Useful

Use these for context, not as final truth when counts or readiness claims disagree:

- `docs/CRASH_RECOVERY_2026-04-12.md`
- `docs/COORDINATOR_STATE_2026-04-11.md`
- `docs/PRODUCTION_EVAL_RESULTS_2026-04-11.md`
- `docs/PRODUCTION_EVAL_400_RATIONALE_2026-04-12.md`
- `docs/DEMO_DAY_RESEARCH_2026-04-12.md`
- `docs/CANARY_INJECTION_METHODOLOGY_2026-04-12.md`

## Unsafe Or Non-Canonical

Do not use these as current truth without reissue or direct reprobe:

- Untracked `docs/COORDINATOR_STATE_2026-04-12_evening.md`
- `docs/DEMO_DAY_CHECKLIST_2026-04-07.md`
- `docs/DEMO_SCRIPT_2026-04-05.md`
- `docs/ENVIRONMENT_ASSUMPTIONS_2026-04-08.md`
- `docs/SPRINT_SYNC.md`

## Conflict Resolution

1. For chunk, entity, relationship, or extracted-table counts: use direct repo-local probes.
2. For May 2 operator behavior: use the canonical demo packet unless it conflicts with live probes.
3. For claim boundaries: use the readiness gap analysis over older scripts, checklists, or sprint language.
4. If a doc is untracked or locally modified and conflicts with a tracked canonical doc, treat it as non-canonical until reissued.

## Short Operator Rule

When in doubt:

- counts -> live repo-local probes
- demo posture -> `MAY2_CANONICAL_DEMO_PACKET_2026-04-12.md`
- stale-doc calls -> `STALE_DOC_RETIREMENT_MAP_2026-04-12.md`
