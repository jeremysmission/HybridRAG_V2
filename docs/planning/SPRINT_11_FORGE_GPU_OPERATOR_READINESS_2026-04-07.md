# Sprint 11 Forge GPU Operator Readiness 2026-04-07

## Purpose

Make `CorpusForge` reliable enough to generate controlled chunk/export batches from a workstation without shell-guessing, silent path failures, or silent drawing-format loss.

## Status

Closed green after QA.

QA-confirmed outcomes:

- repo-root config path behavior is stable
- GUI/CLI deferred-format preflight is stable
- deferred/skipped files enter `file_state` correctly
- parseable files are not marked `indexed` before successful export
- export `manifest.json` now receives finalized skip reasons and elapsed time

This sprint now comes **before** recovery dedup because the current blocker is not only source backup. It is also that `CorpusForge` must become trustworthy for operator-run chunk generation and workstation staging.

---

## Why This Sprint Moved Ahead

Two concrete failures surfaced during the AWS probe attempt:

1. `CorpusForge` CLI/config behavior was still fragile enough to fail with path-related `Errno 2` issues depending on launch location.
2. Drawing/CAD-heavy corpora were being under-accounted for at operator level because deferred formats like `.dwg` could disappear from the run boundary instead of being clearly surfaced and written into skip accounting.

The workstation operator needs to know:

- what will be chunked
- what will be hashed-only and deferred
- what was excluded entirely
- where the output went
- whether the GPU embed/export path is actually healthy

---

## Sprint Goal

Make `CorpusForge` workstation-safe and operator-meaningful for chunk generation.

That means:

- CLI works from outside the repo root
- GUI launch path is stable
- output paths are created automatically
- deferred drawing formats are counted and explained
- unsupported extensions are reported instead of silently disappearing
- a controlled export can be produced for AWS probe work

---

## Scope

### In Scope

- config path normalization to repo-root semantics
- GUI output-path normalization and creation
- preflight discovery summary for:
  - supported files
  - deferred skip-list formats
  - unsupported extensions
- operator-visible drawing/CAD accounting
- controlled workstation export run
- runbook updates

### Not In Scope

- full `.dwg` parsing
- full CAD parser expansion across every deferred binary format
- recovery dedup on the full source tree
- canonical rebuild

Those remain later sprints after Forge is production-usable.

---

## Current Completed Slices

### 11.1 Repo-Root Config Path Fix

Done.

`CorpusForge` config-relative paths now resolve to the repo root instead of the caller's working directory. This fixes the shell-location failure class that caused the earlier AWS probe run to die with `Errno 2`.

### 11.2 GUI Output Path Hardening

Done.

GUI-run output paths are normalized to absolute paths and created before the pipeline thread starts.

### 11.3 Deferred Format Accounting

Done.

Deferred formats such as `.dwg` are now included in the discovery/audit path so they are:

- counted before run
- passed into the skip-manager path
- written into `skip_manifest.json`
- explained to the operator instead of silently disappearing

### 11.4 Unsupported Extension Warning

Done.

Unsupported extensions are now called out explicitly in CLI/GUI preflight messaging.

### 11.5 Hashed Deferred-State Accounting

Done.

`CorpusForge` now records state for files that are intentionally not processed in the current run path:

- duplicate files are written into `file_state` with status `duplicate`
- deferred files are written into `file_state` with status `deferred`
- skipped files are written into `file_state` with status `skipped`

This closes the restart-time failure mode where intentionally skipped files could be rediscovered over and over without ever entering state tracking.

### 11.6 Legacy Skip-State Backfill Utility

Done.

A new backfill utility exists for old corpora that may contain historically skipped or unsupported files that never entered `file_state`:

- `scripts/backfill_skipped_file_state.py`

Safety rule:

- this utility only backfills deferred and unsupported files by default
- it does **not** mark parseable files as already indexed

This gives us a repair path for legacy source trees without poisoning future real chunking runs.

---

## Remaining Slices

### 11.7 Controlled Workstation Export Proof

Goal:

- produce a controlled export from the workstation laptop using `CorpusForge`
- confirm chunk/output path works end to end

### 11.8 Operator-Facing Format Coverage Summary

Goal:

- document exactly which drawing/document types are:
  - parsed now
  - hashed-only/deferred
  - unsupported

### 11.9 GUI Operator Polish

Goal:

- reduce operator guesswork further with clearer preflight and failure text
- ensure source/output run choices are obvious and repeatable

### 11.10 Workstation Desktop Forge Proof

Goal:

- repeat the controlled export on the workstation desktop once installs are fixed

---

## Exit Criteria

This sprint is complete when:

- `CorpusForge` controlled chunk/export works from a workstation
- operator can see which drawing/CAD formats were deferred
- `skip_manifest.json` captures deferred drawing formats cleanly
- intentionally deferred/skipped files enter `file_state` cleanly
- a legacy skipped-file backfill path exists for old source trees
- GUI/CLI no longer depend on the operator launching from the perfect shell location
- the stack can generate a trustworthy controlled export for AWS probe work

---

## Follow-On Sprint Order

After this sprint:

1. `Sprint 12` Recovery Dedup
2. `Sprint 13` Canonical Rebuild
3. `Sprint 14` Structured Promotion On The Rebuilt Corpus
4. `Sprint 15` Operator Hardening Back To Demo
