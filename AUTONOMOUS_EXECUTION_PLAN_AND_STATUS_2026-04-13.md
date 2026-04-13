# Autonomous Execution Plan And Status 2026-04-13

## Purpose

This is the active coordinator/work log for unattended Beast-side progress while the user is at work.

If the machine crashes or a new coordinator has to resume, start here.

## Immediate Goal

Advance the next agreed dependency:

- use the now-clean Tier 1 baseline to drive the first measured retrieval and
  routing fixes

The current execution order is:

1. keep the clean Tier 1 rerun and clean-store baseline frozen
2. fix any correctness gaps in the baseline/reporting path
3. extract the highest-yield miss families from the clean baseline
4. land the smallest high-value retrieval/routing fixes
5. rerun the clean 400 baseline after each meaningful retrieval slice

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

## Slice E: Freeze clean baseline and follow-on priorities

### Goal

Capture the clean-store baseline as the new truth source and freeze the first
evidence-driven follow-on plan.

### Frozen artifacts

- `docs/PRODUCTION_EVAL_RESULTS_CLEAN_TIER1_2026-04-13.md`
- `docs/production_eval_results_clean_tier1_2026-04-13.json`
- `docs/CLEAN_TIER1_BASELINE_FOLLOWON_PRIORITIES_2026-04-13.md`

### Headline

- clean baseline:
  - `158 PASS`
  - `96 PARTIAL`
  - `146 MISS`
  - `287/400 routing correct`
- dominant miss families:
  - `CDRLs: 86`
  - `Logistics: 49`

### Status

- Completed

## Slice F: Fix clean-baseline correctness and retrieval wiring

### Goal

Eliminate obvious correctness gaps before deeper follow-on work.

### Landed fixes

- fixed the markdown persona scorecard label mismatch:
  - `Cybersecurity / Network Admin` no longer shows `0/0`
- fixed retrieval candidate-pool wiring:
  - reranker can now actually see the configured wider candidate pool on the
    live pipeline path instead of only `top_k`

### Files

- `scripts/run_production_eval.py`
- `src/query/vector_retriever.py`
- `src/query/pipeline.py`
- `scripts/boot.py`
- `src/api/server.py`
- `src/gui/launch_gui.py`
- `scripts/run_golden_eval.py`
- `scripts/run_ragas_eval.py`
- `tests/test_candidate_pool_wiring.py`

### Verification

- `python -m pytest -q tests/test_candidate_pool_wiring.py`
- `python -m pytest -q tests/test_reranker_path_aware.py`

### Status

- Completed

## Active Next Slice

- start the first real follow-on retrieval hardening work
- primary target:
  - CDRL family retrieval
- secondary target:
  - Logistics site/date/shipment retrieval

## Slice G: Measure post-retrieval patch clean baseline

### Goal

Re-run the clean-store 400 baseline after the first retrieval/routing patch set
so the next engineering pass stays evidence-driven.

### Included patch set

- retrieval candidate-pool wiring fix
- fallback router now applies guarded query rewrites
- deterministic CDRL query expansion
- deterministic shipment/date query expansion
- corrected clean markdown persona scorecard row

### Active launch

- launched:
  - `2026-04-13 12:39 America/Denver`
- command:

```powershell
.\.venv\Scripts\python.exe scripts\run_production_eval.py `
  --config config\config.tier1_clean_2026-04-13.yaml `
  --report-md docs\PRODUCTION_EVAL_RESULTS_POST_METADATA_PATH_PATCH_2026-04-13.md `
  --results-json docs\production_eval_results_post_metadata_path_patch_2026-04-13.json
```

- active process observed:
  - launcher:
    - `224320` (`C:\HybridRAG_V2\.venv\Scripts\python.exe`)
  - child:
    - `224760` (`C:\Users\jerem\AppData\Local\Programs\Python\Python312\python.exe`)
  - child CPU / working set at `2026-04-13 12:42 America/Denver`:
    - about `695.62` CPU seconds
    - about `5.07 GB` working set
- logs:
  - `logs\production_eval_post_metadata_path_patch_20260413_123900.out.log`
  - `logs\production_eval_post_metadata_path_patch_20260413_123900.err.log`
- artifacts at checkpoint:
  - `docs\PRODUCTION_EVAL_RESULTS_POST_METADATA_PATH_PATCH_2026-04-13.md`
  - `docs\production_eval_results_post_metadata_path_patch_2026-04-13.json`
  - neither existed yet at the `12:42` checkpoint

### Resume rule

- do **not** relaunch this post-patch clean baseline if either process
  `224320` or `224760` is still alive
- first inspect the log pair above, then check whether the report/json outputs
  already exist before launching anything new

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

### Replacement relaunch

- backup of the first clean store:
  - `data/index/clean/tier1_clean_20260413_prelegacypo_backup`
- relaunched:
  - `2026-04-13 09:59 America/Denver`
- launcher:
  - `scripts/run_tier1_clean_launcher.py`
- run id:
  - `20260413_095955`
- launcher PID:
  - `204468`
- child PID:
  - `213116`
- manifest:
  - `logs/tier1_clean_runs/tier1_clean_run_20260413_095955.json`
- stdout/stderr log:
  - `logs/tier1_clean_runs/tier1_clean_run_20260413_095955.log`
- completed:
  - `2026-04-13 11:05 America/Denver`
- final audited result:
  - verdict: `PASS`
  - entities: `5,781,766`
  - relationships: `59`
  - `PO`: `119,812`
  - `PART`: `316,184`
  - blocked namespace hits: `none`
  - PO preserve sentinels: `pass`
  - PART preserve sentinels: `pass`
- audit artifact:
  - `docs/TIER1_CLEAN_RERUN_RESULTS_2026-04-13.md`

### Status

- Completed and approved as the clean Tier 1 baseline store

## Slice E: Clean-store evaluation prep

### Goal

Once a clean Tier 1 store exists, prepare the next 400-query baseline rerun against that cleaned store.

### Clean-store baseline launch

- initial baseline attempt failed fast on a runner bug:
  - `NameError: _resolve_cli_path is not defined`
- root cause:
  - `if __name__ == "__main__": sys.exit(main())` was above the helper
    definition, so `main()` could execute before `_resolve_cli_path`
    existed
- local fix:
  - moved the `__main__` block to the bottom of
    `scripts/run_production_eval.py`
- relaunch command:

```powershell
.\.venv\Scripts\python.exe scripts\run_production_eval.py `
  --queries tests\golden_eval\production_queries_400_2026-04-12.json `
  --config config\config.tier1_clean_2026-04-13.yaml `
  --results-json docs\production_eval_results_clean_tier1_2026-04-13.json `
  --report-md docs\PRODUCTION_EVAL_RESULTS_CLEAN_TIER1_2026-04-13.md
```

### Current live state at lunch-break checkpoint

- launched:
  - `2026-04-13 11:07 America/Denver`
- active eval PID:
  - `206972`
  - executable:
    - `C:\Users\jerem\AppData\Local\Programs\Python\Python312\python.exe`
  - CPU at checkpoint:
    - `628.33`
  - working set at checkpoint:
    - about `6.1 GB`
- duplicate near-idle process also present with same command line:
  - PID `213380`
  - executable:
    - `C:\HybridRAG_V2\.venv\Scripts\python.exe`
  - CPU at checkpoint:
    - `0.03`
- clean-store output files did **not** exist yet at the checkpoint, so do
  **not** assume completion and do **not** relaunch a second baseline while
  PID `206972` is still alive

### Status

- Completed

### Final clean-store baseline result

- completed:
  - `2026-04-13 11:30 America/Denver`
- result artifacts:
  - `docs\production_eval_results_clean_tier1_2026-04-13.json`
  - `docs\PRODUCTION_EVAL_RESULTS_CLEAN_TIER1_2026-04-13.md`
- headline:
  - `PASS: 158/400` (`40%`)
  - `PASS + PARTIAL: 254/400` (`64%`)
  - `MISS: 146/400`
  - routing correct: `287/400` (`72%`)
- latency:
  - pure retrieval `P50 433ms / P95 2711ms`
  - wall clock incl. router `P50 2628ms / P95 5528ms`
- important interpretation:
  - the cleaned store improved the truthful baseline enough to justify
    shifting focus away from Tier 1 cleanup and toward targeted
    retrieval/routing follow-on work
  - routing improved materially versus the earlier dirty-store baseline
  - retrieval is still strongest for Program Manager / Field Engineer lanes
    and remains weakest in the identifier-heavy Logistics lane

### Immediate next follow-on lane

- analyze the cleaned baseline by miss family and query slice
- identify the highest-yield fix targets from the cleaned store rather than
  guessing from the older dirty baseline
- expected first targets:
  - Logistics / shipping / procurement family misses
  - identifier/path-heavy retrieval misses
  - remaining router weak spots on the real provider path

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
8. before launching any new clean-store eval, check whether PID `206972`
   or another `run_production_eval.py` process is already active:
   - `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*run_production_eval.py*config.tier1_clean_2026-04-13.yaml*' } | Select-Object ProcessId,CommandLine`

## Short Summary

The unattended Beast-side mission has now cleared the major data-trust dependency. The replacement isolated clean Tier 1 rerun completed and the clean-store audit is a full PASS: blocked namespaces are gone from the audited `PO` / `PART` path, and both the PO and PART preserve sentinels survive in the corrected store. The follow-on clean-store 400-query baseline also completed successfully and is now frozen in local artifacts. The next immediate dependency is no longer “make Tier 1 clean.” It is “use the clean baseline to identify the highest-yield retrieval and routing fixes on the rebuilt store.”
