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

- Completed
- Frozen and pushed:
  - `config/config.tier1_shadow_2026-04-13.yaml`
  - `scripts/run_tier1_shadow_slice.py`

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

### Current shadow-run evidence

- First sampled shadow slice:
  - `logs\tier1_shadow_slice_20260413_075912.txt`
  - `logs\tier1_shadow_slice_20260413_075912.json`
  - Result: strong improvement, but still leaked embedded/report-code tails
    such as `FSR-L22`, plus non-physical `PART` tails such as
    `CVE-202`, `DO-0003`, `DO-0011`, `IGS-2522`, `MSR-029`, and
    `DV-200`
- Follow-on hardening landed locally:
  - wired `security_standard_exclude_patterns` through all shared Tier 1
    entrypoints
  - narrowed serial regex to reject bare `SN*` words while preserving
    real serials
  - added boundary enforcement to report-ID extraction
  - added corpus-backed rejection families for `CVE` fragments,
    `DO-0003`-style delivery-order codes, `IGS/IGSI` drawing IDs,
    `MSR-*`, `DV-*`, and `IEEE-*`
- Latest shadow slice:
  - `logs\tier1_shadow_slice_20260413_080702.txt`
  - `logs\tier1_shadow_slice_20260413_080702.json`
  - Result:
    - scanned `100,000`
    - selected `10,000` stratified
    - entities `8,579`
    - `PO` top-50 now entirely business-looking purchase-order values
    - `PART` top-50 now dominated by physical parts / serials instead of
      security or program-code junk

### Approval decision

- Approved for isolated full clean Tier 1 rerun
- Rationale:
  - regex gate is green (`40/40`)
  - live-sample dangerous hits remain `0`
  - shadow top-50 `PO` is clean
  - shadow `PART` tail no longer shows the blocked security/governance
    namespaces that previously polluted the store

### Status

- Completed

## Slice D: Full clean Tier 1 rerun in isolated store

### Goal

If the shadow slice is clean, run a full Tier 1 rerun into an isolated clean store, not the main live entity DB.

### Planned command

```powershell
.\.venv\Scripts\python.exe scripts\tiered_extract.py `
  --config config\config.tier1_clean_2026-04-13.yaml `
  --tier 1
```

### Isolated target

- entities:
  - `data/index/clean/tier1_clean_20260413/entities.sqlite3`
- relationships:
  - `data/index/clean/tier1_clean_20260413/relationships.sqlite3`

### First clean run outcome

- first buffered launch:
  - launched: `2026-04-13 08:10 America/Denver`
  - outcome:
    - terminated intentionally after the streaming Tier 1 refactor landed
    - reason:
      - old code buffered all Tier 1 outputs until the end of the run,
        which made progress non-durable and hard to observe
- active relaunched run:
  - launched: `2026-04-13 08:39 America/Denver`
  - launcher:
    - `scripts/run_tier1_clean_launcher.py`
  - run id:
    - `20260413_083954`
  - launcher PID:
    - `200180`
  - child PID:
    - `203152`
  - clean config:
    - `config/config.tier1_clean_2026-04-13.yaml`
  - manifest:
    - `logs/tier1_clean_runs/tier1_clean_run_20260413_083954.json`
  - stdout/stderr log:
    - `logs/tier1_clean_runs/tier1_clean_run_20260413_083954.log`
  - completed:
    - `2026-04-13 09:45 America/Denver`
  - final result:
    - `5,775,224` entities
    - `59` relationships
    - about `65.8` minutes on the streaming path

### Post-run audit result

- blocked-namespace leakage:
  - none
- preserve-set result:
  - `PART` preserve set passed after aligning the audit harness to the
    agreed corpus audit
  - `PO` preserve set failed on two missing legacy 6-digit sentinels:
    - `268235`
    - `250802`

### Root cause of the preserve failure

- the clean rerun was built before the latest legacy-PO fix landed
- direct chunk validation proved both missing values are real labeled
  procurement POs in the corpus:
  - `Purchase Order: 268235`
  - `Purchase Order: 250802`
- the extractor previously handled:
  - `PO-YYYY-NNNN`
  - labeled 10-digit SAP POs
- it did **not** yet handle labeled 6-digit legacy procurement POs

### Fix status

- local fix landed:
  - labeled `PO` extraction now accepts `6`-digit and `10`-digit
    procurement numbers when explicitly labeled
  - ambiguous `8`-digit numerics remain fail-closed
- validation after the fix:
  - direct extraction against the real `268235` / `250802` chunks now
    succeeds
  - regex gate re-run: `40/40` pass
  - fresh `5,000`-chunk shadow slice after the fix remains clean:
    - no blocked-family `PO` / `PART` leakage in the top ranks

### Next launch

- rotate the first clean store aside
- relaunch a replacement isolated clean Tier 1 run into:
  - `data/index/clean/tier1_clean_20260413`
- rerun the clean-store audit immediately after completion

### Status

- Replacement rerun approved and pending relaunch

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
5. read the latest status in Slice D above
6. if the replacement rerun has not started, relaunch via:
   - `.\.venv\Scripts\python.exe scripts\run_tier1_clean_launcher.py --config config\config.tier1_clean_2026-04-13.yaml`
7. after it finishes, rerun:
   - `.\.venv\Scripts\python.exe scripts\audit_tier1_clean_store.py --entity-db data\index\clean\tier1_clean_20260413\entities.sqlite3 --markdown docs\TIER1_CLEAN_RERUN_RESULTS_2026-04-13.md`

## Short Summary

The current unattended Beast-side mission has advanced further: the first streaming clean Tier 1 rerun completed and eliminated the known blocked namespaces from the top `PO` / `PART` values, but it still missed two real legacy 6-digit procurement POs. That legacy-PO recall gap is now fixed in code and revalidated on the real documents. The next unattended step is to relaunch a replacement clean Tier 1 rerun with that fix in place, then use the corrected clean store for the next truthful evaluation baseline.
