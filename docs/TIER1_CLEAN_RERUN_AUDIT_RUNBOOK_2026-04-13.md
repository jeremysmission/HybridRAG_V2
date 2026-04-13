# Tier 1 Clean Rerun Audit Runbook - 2026-04-13

Run this immediately after the isolated clean Tier 1 rerun finishes.

## Purpose

This is the post-rerun acceptance audit for the finished clean store.
It inspects the entity and relationship SQLite stores and answers one
question:

> Did the clean Tier 1 rerun actually produce an acceptable store?

The audit is read-only. It does not rerun extraction and does not mutate
the stores.

## Default Target

The current isolated clean-rerun target is:

- `data/index/clean/tier1_clean_20260413/entities.sqlite3`

The script does **not** hardcode only that path. Pass any entity store path
with `--entity-db` if the target moves.

## Exact Command

```powershell
cd C:\HybridRAG_V2
.\.venv\Scripts\python.exe scripts\audit_tier1_clean_store.py
```

Useful variants:

```powershell
.\.venv\Scripts\python.exe scripts\audit_tier1_clean_store.py --json
.\.venv\Scripts\python.exe scripts\audit_tier1_clean_store.py --markdown docs\TIER1_CLEAN_RERUN_RESULTS_2026-04-13.md
.\.venv\Scripts\python.exe scripts\audit_tier1_clean_store.py --entity-db data\index\clean\tier1_clean_20260413\entities.sqlite3
.\.venv\Scripts\python.exe scripts\audit_tier1_clean_store.py --entity-db <path-to-entities.sqlite3> --relationship-db <optional-sibling-path>
```

## What The Audit Reports

The audit prints and optionally exports:

- total entity rows
- extracted table rows
- relationship rows
- entity counts by type
- top-N `PO` values
- top-N `PART` values
- blocked namespace hits in those top values
- preserve-sentinel checks for the real procurement and hardware values
- relationship predicate summary
- a PASS / FAIL verdict

## Pass / Fail

Pass means:

- the entity store is readable and non-empty
- the relationship store is readable and non-empty
- the preserve sentinels are still present
- the top `PO` values do not surface blocked namespaces such as:
  - `IR-*` lookalikes
  - security-control family codes
  - `FSR-*`, `UMR-*`, `ASV-*`, `RTS-*` noise
- the top `PART` values do not surface blocked namespaces such as:
  - STIG / platform codes
  - `CCI-*`, `SV-*`, `CCE-*`, `CVE-*`, `RHSA-*`, `APP-*`
  - lowercase underscore security tokens
  - service-state debris

Fail means:

- the entity store is empty or unreadable
- the relationship store is empty or unreadable
- any preserve sentinel is missing
- any blocked namespace still shows up in the top `PO` / `PART` values

## How To Read The Markdown Artifact

If you pass `--markdown`, the script writes a human-readable results file.
That file is meant to become the clean-rerun results doc for the run.

Recommended output path:

```powershell
docs\TIER1_CLEAN_RERUN_RESULTS_2026-04-13.md
```

## Residual Blind Spots

- The audit checks the finished store, not the rerun execution path.
- Top-N inspection is intentionally shallow; it is an acceptance gate, not a
  full-corpus proof.
- The audit does not prove downstream query routing quality.
- If the rerun target changes, rerun the audit with the new `--entity-db`
  path and regenerate the Markdown artifact.
