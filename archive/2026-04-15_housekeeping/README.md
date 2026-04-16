# Archive Manifest

This folder holds low-risk housekeeping moves made on 2026-04-15.

What was moved here:
- Top-level coordination notes, handoffs, pointers, and status memos that were dated and no longer part of the active run path.
- Older `docs/` run notes and generated result artifacts that had been superseded by newer runs.
- Temporary runtime captures and scratch directories from GUI/eval sessions.
- Legacy `tests/golden_eval/v1_reference/tuning_scripts` files that appear orphaned because they point at a missing `tools/autotune` path.

What was intentionally left in place:
- Active source code under `src/`, `scripts/`, and `tools/`.
- Current launch/install entrypoints.
- Core guides, runbooks, and theory/architecture docs that still look useful.
- Generated artifacts that are still part of the current baseline or still referenced by active docs.

This is an archive, not a deletion pass. Files were moved here so the main repo surface is easier to navigate while still preserving history and recoverability.
