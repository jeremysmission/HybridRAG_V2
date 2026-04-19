# GUI Operator Readiness Audit — 2026-04-13

**Scope:** HybridRAG V2 400-query evaluation GUI as a repeated-run operator surface.

## Verdict

- **ENGINEERING-ONLY**
- **Not yet operator-ready** for standardized repeated 400-query use

## What Works

- launcher boots
- smoke path works
- results persist
- compare and history concepts exist
- stop is partially implemented

## What Blocks Operator Readiness

1. **Portability blockers**
   - hardcoded `C:\HybridRAG_V2\docs` paths in:
     - `src/gui/eval_panels/results_panel.py`
     - `src/gui/eval_panels/history_panel.py`
   - failure mode is silent: history/results appear empty on a clone or different install path

2. **Provenance gap**
   - result JSONs do not clearly persist:
     - config path
     - query pack path or ID
     - Lance/store path
   - results/compare views do not show enough run metadata to audit repeated runs safely

3. **No operator runbook**
   - current slice doc is an engineering sprint doc, not a cold-start operator guide

## Highest-Value Fixes

1. Replace hardcoded docs paths with repo-relative/V2-root-relative resolution
2. Add a `Run Info` frame to the results view
3. Persist run provenance in result JSON
4. Add overwrite confirmation for manual output paths
5. Write a one-page operator quick-start doc

## Coordinator Read

- This is close to operator-ready, but not there yet.
- The blocker is not core functionality.
- The blocker is **trust and repeatability**:
  - portability
  - provenance
  - onboarding

## Signoff Still Needed

- non-author smash test
- portability test on a different checkout path
- repeated-run stability
- misuse-path validation
- cold-read operator runbook test
