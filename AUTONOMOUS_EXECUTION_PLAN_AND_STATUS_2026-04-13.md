# Autonomous Execution Plan And Status 2026-04-13

## Purpose

This is the active coordinator/work log for unattended Beast-side progress while the user is at work.

If the machine crashes or a new coordinator has to resume, start here.

## Immediate Goal

Advance the next agreed dependency:

- prove the Tier 1 path is clean enough to trust

The current execution order is:

1. run the Tier 1 regex gate
2. run a bounded shadow Tier 1 slice
3. approve or reject the full clean Tier 1 rerun
4. if approved, run one clean full Tier 1 rerun in an isolated store
5. rerun the 400-query baseline on the cleaned store

## Current Starting State

- Tier 1 research is complete enough
- regex gate exists and is green-capable
- shadow-slice tooling is being added
- Beast now has a fast local copy of the V2 import/export package at:
  - `C:\CorpusIndexEmbeddingsOnly\export_20260411_0720`
- Beast does **not** have a full off-USB copy of the 700 GB raw source tree
- workstations have their own install/runbook:
  - [WORKSTATION_MANUAL_INSTALL_AND_WORKDAY_ACTIONS_2026-04-13.md](./WORKSTATION_MANUAL_INSTALL_AND_WORKDAY_ACTIONS_2026-04-13.md)

## Autonomous Task Queue

## Slice A: Freeze Tier 1 execution tooling

### Goal

Commit and push the shadow-run config and shadow-slice runner so they are recoverable.

### Files

- `config/config.tier1_shadow_2026-04-13.yaml`
- `scripts/run_tier1_shadow_slice.py`

### Status

- In progress

## Slice B: Freeze regex gate result

### Goal

Run the current gate and capture a dated log artifact.

### Command

```powershell
.\.venv\Scripts\python.exe scripts\audit_tier1_regex_gate.py --json
```

### Current Result

- PASS on Beast
- curated: `40/40`
- sample: `120 selected / 1000 scanned`
- dangerous PART/PO hits: `0`
- invalid phone hits: `0`
- log:
  - `logs\tier1_regex_gate_20260413_073707.txt`

### Status

- Completed

## Slice C: Run bounded shadow Tier 1 slice

### Goal

Run Tier 1 on a sampled slice of the live LanceDB store while writing to an isolated shadow entity DB.

### Initial run already completed

An early safety probe using first `10,000` chunks on the isolated shadow config completed successfully:

- log:
  - `logs\tier1_shadow_run_20260413_073835.txt`
- result:
  - `32` inserted entities
  - mostly `CONTACT` / `DATE`
  - proves isolated write path works

### Next correct run

Use the sampled shadow-slice runner instead of `--limit` first-chunk extraction.

Planned command:

```powershell
.\.venv\Scripts\python.exe scripts\run_tier1_shadow_slice.py `
  --config config\config.tier1_shadow_2026-04-13.yaml `
  --sample-limit 5000 `
  --max-scan-chunks 50000 `
  --reset `
  --json-out logs\tier1_shadow_slice_20260413.json
```

### Approval target

- top `PO` values free of blocked namespaces
- top `PART` values free of blocked namespaces
- preserve-set identifiers survive
- enough evidence to approve or reject the full rerun

### Status

- In progress

## Slice D: Full clean Tier 1 rerun in isolated store

### Goal

If the shadow slice is clean, run a full Tier 1 rerun into an isolated clean store, not the main live entity DB.

### Status

- Pending shadow-run approval

## Slice E: Clean-store evaluation prep

### Goal

Once a clean Tier 1 store exists, prepare the next 400-query baseline rerun against that cleaned store.

### Status

- Pending clean Tier 1 store

## Workstation Coordination Notes

The user can make parallel progress at work using:

- [WORKSTATION_MANUAL_INSTALL_AND_WORKDAY_ACTIONS_2026-04-13.md](./WORKSTATION_MANUAL_INSTALL_AND_WORKDAY_ACTIONS_2026-04-13.md)

Best workstation tasks:

1. update both repos
2. get V2 install green
3. get Forge install green
4. run Forge precheck
5. if desktop is healthy, run the approved Forge Phase 1 rerun
6. validate the export with V2 dry-run import

## Crash Recovery Notes

If Beast crashes, the recovery order is:

1. open this file
2. confirm latest remote state:
   - `git pull origin master`
3. check the Tier 1 gate log:
   - `logs\tier1_regex_gate_20260413_073707.txt`
4. rerun or continue the shadow slice:
   - `scripts\run_tier1_shadow_slice.py`
5. only after shadow approval, move to a full clean rerun

## Short Summary

The current unattended Beast-side mission is simple: freeze the new shadow-slice tooling, run the sampled Tier 1 shadow slice, and use that evidence to decide whether a full clean Tier 1 rerun should be launched into an isolated store. Everything else is downstream of that decision.
