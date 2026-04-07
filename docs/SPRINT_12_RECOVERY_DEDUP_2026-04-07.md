# Sprint 12 Recovery Dedup 2026-04-07

## Purpose

Turn the dedup stage into a trustworthy recovery gate for the full source backup.

This sprint exists to reduce the rebuilt corpus before rechunking, embedding, or AWS enrichment work. The immediate target is not perfect canonicalization. The immediate target is a dedup path that is:

- restart-safe
- operator-visible
- reviewable
- honest about what is still deferred or untrusted

---

## Why This Sprint Starts Now

`CorpusForge` chunk/export is now good enough to stop being the primary blocker.

The next major risk is historical ingest drift:

- old transferred lists may include skipped files that were never hashed
- parser/defer policy drift across repos may have hidden duplicate families
- the real source backup will be large enough that restart cost matters
- the duplicate-review path is only fully trustworthy at the document level right now
- Beast is still generating structured extraction outputs that may remain useful during recovery and must not be discarded casually

So Sprint 12 starts before the full source backup lands by hardening the dedup lane around those risks.

---

## Sprint Goal

Make recovery dedup operationally safe for the incoming source backup.

That means:

- legacy skipped files can be backfilled into `file_state`
- dedup reporting is clear enough for operator review
- the first full backup run can produce `canonical_files.txt` without silent accounting drift
- duplicate-family review starts at the document level, not the weaker chunk-level review path
- current Beast outputs are treated as reusable sidecar data unless a later step explicitly supersedes them

---

## Scope

### In Scope

- legacy skipped-file state backfill workflow
- document-level dedup review workflow
- dedup preflight and restart accounting
- canonical file list generation
- operator-visible risk notes for deferred formats and placeholder-only formats

### Not In Scope

- full canonical rebuild
- AWS enrichment at corpus scale
- final structured promotion over the rebuilt corpus
- full chunk-level human review tooling

---

## Immediate Slices

### 12.1 Legacy Skip-State Audit

Goal:

- define the operator workflow for backfilling deferred/unsupported files into `file_state`
- confirm that legacy skipped files no longer poison restart discovery time

Status:

- started
- `CorpusForge` now has a `--dry-run` mode on `scripts/backfill_skipped_file_state.py`
- operator runbook added in `CorpusForge/docs/LEGACY_SKIP_STATE_AUDIT_2026-04-07.md`

### 12.2 Document-Level Dedup Review Path

Goal:

- rely on the document-level review tooling first
- explicitly avoid depending on chunk-level review as the primary human review lane until it is improved

### 12.3 Canonical List Readiness

Goal:

- produce a clean `canonical_files.txt` output path
- document how it becomes the input to the rebuild sprint

### 12.4 Deferred/Placeholder Risk Disclosure

Goal:

- make sure dedup and rebuild operators know which families are:
  - fully parseable
  - placeholder-only
  - hash-skipped by profile
  - unsupported

---

## Exit Criteria

This sprint is complete when:

- legacy skipped/deferred files can be backfilled into state without poisoning parseable files
- document-level dedup review is the accepted human-review lane
- `canonical_files.txt` is ready to drive the rebuild sprint
- restart accounting risk is explicitly controlled rather than guessed

---

## Follow-On Sprint Order

After this sprint:

1. `Sprint 13` Canonical Rebuild
2. `Sprint 14` Structured Promotion On The Rebuilt Corpus
3. `Sprint 15` Operator Hardening Back To Demo
