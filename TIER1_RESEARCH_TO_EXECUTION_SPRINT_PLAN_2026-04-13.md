# Tier1 Research To Execution Sprint Plan 2026-04-13

## Purpose

This is the coordinator-facing sprint/slice plan for the Tier 1 cleanup lane.

It exists so future coordinators and agents do **not** have to repeat the same research, argument, or guesswork. The research phase is considered complete enough to move into disciplined execution.

## Frozen Conclusions

These points are now treated as settled unless new hard evidence disproves them:

1. Tier 1 regex must be treated as a **candidate generator**, not the truth layer.
2. `PO` is overloaded and should eventually split into at least:
   - `BUSINESS_PO`
   - `REPORT_ID`
3. No future full Tier 1 rerun should happen before:
   - adversarial gate pass
   - preserve-set pass
   - shadow-run review
4. Security/control namespaces must be blocked by **shape-aware rules**, not flat prefix guesses.
5. Ambiguous identifiers must fail closed unless there is positive business context.
6. The long-term production model is:
   - stage
   - audit
   - promote
   not direct write into the authoritative store.

## Research Already Completed

These lanes are done enough that they should be reused, not redone:

- Regex/code hardening:
  - `34b64d8` Tighten Tier 1 PO and part boundary guards
- Corpus confusion audit:
  - `d0476bb` docs: audit tier1 PO and PART confusion sets
  - `54eadec` docs: add tier1 regex corpus rerun audit
- Pre-rerun gate:
  - `f3bafb7` Add Tier 1 regex pre-rerun gate
  - `a45e62f` strengthen tier1 regex gate curated cases
  - `1620084` docs: formalize tier1 regex acceptance gate
- External research synthesis:
  - `e94d704` docs: add Tier 1 regex research synthesis

Primary reference docs:

- [docs/TIER1_REGEX_ACCEPTANCE_GATE_2026-04-12.md](./docs/TIER1_REGEX_ACCEPTANCE_GATE_2026-04-12.md)
- [docs/TIER1_REGEX_CORPUS_AUDIT_2026-04-12.md](./docs/TIER1_REGEX_CORPUS_AUDIT_2026-04-12.md)
- [docs/TIER1_REGEX_CORPUS_AUDIT_2026-04-12_RERUN.md](./docs/TIER1_REGEX_CORPUS_AUDIT_2026-04-12_RERUN.md)
- [docs/TIER1_REGEX_GATE_RUNBOOK_2026-04-12.md](./docs/TIER1_REGEX_GATE_RUNBOOK_2026-04-12.md)
- [docs/TIER1_REGEX_RESEARCH_SYNTHESIS_2026-04-12.md](./docs/TIER1_REGEX_RESEARCH_SYNTHESIS_2026-04-12.md)
- [TIER1_PROACTIVE_QUALITY_PLAN_2026-04-12.md](./TIER1_PROACTIVE_QUALITY_PLAN_2026-04-12.md)

## Current Objective

Get to a clean, trustworthy Tier 1 rerun once, then use that cleaned store as the baseline for the next retrieval/router/structured-answer work.

## Current Status

### Done

- Regex hardening is in place for known `PO` and `PART` collision classes.
- Corpus-derived confusion sets and preserve sets are documented.
- Automated pre-rerun gate exists and passes on the current hardened code.
- External best-practice research is complete enough to guide execution.

### Not Done

- The disciplined `5,000-10,000` chunk shadow run has not yet been frozen as the approval artifact.
- The one clean full Tier 1 rerun has not yet been frozen as the new authoritative baseline.
- The 400-query baseline has not yet been rerun on the cleaned store.

## Sprint / Slice Plan

## Slice 1: Freeze Pre-Rerun Gate

### Goal

Confirm that the current code and curated cases pass the automated Tier 1 gate before any extraction work is attempted.

### Inputs

- `scripts/audit_tier1_regex_gate.py`
- `tests/test_tier1_regex_gate.py`
- `tests/test_extraction.py`

### Command

```powershell
cd C:\HybridRAG_V2
.\.venv\Scripts\python.exe scripts\audit_tier1_regex_gate.py
```

### Done Definition

- curated adversarial cases all pass
- preserve-set cases survive
- no dangerous `PO` / `PART` sampled leaks
- no invalid phone regressions

### Notes

- If this fails, stop and patch before any shadow run.

## Slice 2: Execute Shadow Tier 1 Run

### Goal

Run Tier 1 on a bounded `5,000-10,000` chunk sample as the approval mechanism for the full rerun.

### Why

The research phase strongly rejects "validate by spending a full rerun and checking afterward."

### Done Definition

- bounded shadow run completes
- top `PO` and `PART` values are extracted and reviewed
- preserve sentinels still appear
- blocked namespaces are absent from top values
- measured sample precision is acceptable

### Approval Bar

- `100%` adversarial fixture pass
- zero blocked-namespace leakage in top-50 `PO` / `PART`
- audited precision target:
  - `>=97% PO`
  - `>=95% PART`

## Slice 3: Approve Or Reject Full Tier 1 Rerun

### Goal

Make a written go/no-go decision using the shadow-run evidence.

### Done Definition

- one short approval artifact exists
- it cites:
  - gate result
  - shadow-run counts
  - top-value audit
  - sample precision
  - preserve-set result

### Rule

- If shadow run is dirty, do **not** escalate to full rerun.

## Slice 4: Run One Clean Full Tier 1 Rerun

### Goal

Execute the full rerun once on the hardened path, not repeatedly.

### Done Definition

- clean Tier 1 output is written to the intended authoritative store
- counts by key entity type are frozen
- sample pollution checks are repeated
- artifact path and commit SHA are recorded

### Minimum Required Checks

- top 20 `PO` values
- top 30 `PART` values
- preserve-set spot checks
- no reappearance of known security/control junk families

## Slice 5: Rebaseline On Cleaned Store

### Goal

Rerun the 400-query evaluation pack on the cleaned store to get the first trustworthy post-clean baseline.

### Done Definition

- new `PASS / PARTIAL / MISS` counts are frozen
- routing accuracy is frozen
- biggest remaining failure families are named

### Why

- This is where retrieval, routing, and structured-answer work should start from.

## Slice 6: Turn Tier 1 Into A Production Gate

### Goal

Make the Tier 1 hardening proactive for future network-drive additions so this is not a retroactive cleanup problem again.

### Required Design

- new data lands in staging
- Tier 1 runs on staged delta
- automated gate runs
- only clean deltas are promoted to the authoritative store

### Structural Follow-On

- plan the `BUSINESS_PO` vs `REPORT_ID` split
- keep security/control IDs out of business-facing slots

## What Future Coordinators Should Not Redo

Do **not** spend another cycle rediscovering these points:

- "`PO` and `PART` are polluted in the old live store" is already proven.
- "A full rerun is expensive enough that shadow validation is mandatory" is already proven.
- "Regex-only truth is brittle" is already proven.
- "Shape-aware blocking beats naive prefix-only blocking" is already proven.
- "Ambiguous unlabeled identifiers should fail closed" is already proven.

If a future agent wants to challenge any of those, require new evidence, not opinion.

## Coordinator Handoff Notes

When handing this lane to a new coordinator or agent, the short version is:

1. read the five Tier 1 reference docs listed above
2. run the automated gate
3. run the shadow Tier 1 slice
4. approve or reject the full rerun
5. rerun the 400-query baseline on the cleaned store
6. only then begin broader retrieval/router tuning

## One-Paragraph Summary

The Tier 1 lane is no longer in research mode. The project already has regex hardening, confusion-set evidence, a pre-rerun gate, and external best-practice synthesis. The next correct move is a gated shadow run followed by one clean full rerun only if the shadow evidence is clean. That cleaned store then becomes the baseline for the next retrieval and routing work. Future deltas should follow the same stage-audit-promote model so dirty entities never reach production again.
