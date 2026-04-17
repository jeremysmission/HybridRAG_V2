# HybridRAG V2 Staging + Import Runbook (Nightly Forge Handoff)

Date: 2026-04-09  
Owner lane: V2 staging/import automation

## Purpose

Make Forge export intake explicit and operator-visible before touching the live V2 store.

This runbook uses:
- `scripts/stage_forge_import.py` for staging artifacts, canary, delta checks, and explicit execution mode
- `scripts/import_embedengine.py` for actual import logic (unchanged import path)

## Core Rules

1. No hidden source selection:
- Use explicit `--source` OR explicit `--source-root ... --select latest`.
- If `--select latest` is used, candidate exports and tie-break ordering are written to `source_selection.json`.

2. Preflight is always visible:
- Every stage run writes `preflight_report.json`.
- If preflight verdict is `FAIL`, import execution is blocked.

3. Canary and filters are explicit:
- Canary uses `--canary-limit N` and writes a materialized `canary_export/` package.
- Any import-side exclusion uses explicit `--exclude-source-glob` flags and is recorded in artifacts.

## Morning Task (Recommended Sequence)

1. Stage-only plan (no import write):

```powershell
.\.venv\Scripts\python.exe scripts\stage_forge_import.py `
  --source-root C:\CorpusForge\data\production_output `
  --select latest `
  --mode plan
```

2. Canary dry run (operator proof path):

```powershell
.\.venv\Scripts\python.exe scripts\stage_forge_import.py `
  --source-root C:\CorpusForge\data\production_output `
  --select latest `
  --canary-limit 2000 `
  --mode dry-run
```

3. Full import when canary looks correct:

```powershell
.\.venv\Scripts\python.exe scripts\stage_forge_import.py `
  --source C:\CorpusForge\data\production_output\export_20260409_0720 `
  --mode import `
  --create-index
```

## Artifacts Produced Per Stage Run

All artifacts are written under:
- `data/staging/import_runs/stage_<timestamp>_<export_name>/`

Files:
- `source_selection.json`
- `preflight_report.json`
- `delta_validation.json`
- `planned_import_command.txt`
- `stage_result.json`
- optional `canary_export/` (when `--canary-limit > 0`)

Ledger:
- `data/staging/import_runs/import_stage_ledger.jsonl`

## What Delta Validation Reports

Delta compares current staged fingerprint vs previous staged run:
- chunk count delta
- source-file-count delta
- vector dimension change
- embedding model change

This is an operator-facing sanity check, not a hard blocker by itself.

## Fallback Safety (Visible)

If you must protect V2 from known bad source paths before upstream rerun:

```powershell
.\.venv\Scripts\python.exe scripts\stage_forge_import.py `
  --source C:\CorpusForge\data\production_output\export_20260409_0720 `
  --mode dry-run `
  --exclude-source-glob "*.SAO.zip" `
  --exclude-source-glob "*.RSF.zip"
```

The active filter list and counts are recorded in stage artifacts and propagated into import reports.

## QA Evidence Minimum

For signoff, provide:
- stage directory path
- `stage_result.json`
- `preflight_report.json`
- `delta_validation.json`
- import report path from `mode_result.report_path` when mode is `dry-run` or `import`
