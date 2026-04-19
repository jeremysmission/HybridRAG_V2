# Production-Workstation Promotion Audit — 2026-04-13

**Mode:** Read-only sidecar synthesis preserved for coordinator use.

## Executive Summary

- The next authoritative production-workstation run is **not worth spending yet**.
- The promotion sequence is broadly sound:
  - Forge export
  - export integrity
  - staged V2 import
  - post-ingest validation
  - frozen 400-query rerun
  - frozen demo-safe rerun
- The blockers are now concrete:
  1. both canonical repos are still dirty in promotion-critical surfaces
  2. Lane 1 retrieval/router work still needs a final QA verdict
  3. `scripts/run_production_eval.py` still has a wrong-pack default foot-gun
  4. current measurement is ambiguous between the clean Tier 1 baseline and the active default store
  5. the demo-safe pack still needs to exist as a frozen file
  6. the Forge -> V2 metadata-contract decision must be explicit: amend now or waive now
- The single biggest hidden promotion risk is **measurement ambiguity**, not an obvious crash:
  - the accepted `226 PASS` baseline was measured on the clean Tier 1 substrate
  - the default V2 config still points at the non-clean default store
  - a future rerun can silently look like a regression or fake lift just by measuring against a different substrate

## Current Authoritative Facts

- Current accepted 400-query baseline:
  - `226 PASS`
  - `304 PASS+PARTIAL`
  - `96 MISS`
  - `298 routing-correct`
- Current authoritative store facts:
  - `10,435,593` chunks
  - `19,959,604` entities
  - `59` relationships
- Current clean Tier 1 audit:
  - PASS
  - sentinels preserved
  - notable caveat: `ORG=0`
- Current lane state:
  - Lane 2: QA PASS
  - Lane 3: QA PASS
  - Lane 1: still needs final QA
- Current OCR state:
  - Tesseract usable
  - Poppler missing
  - text-first scope remains acceptable

## Promotion Sequence

1. Freeze both repos at clean tagged SHAs.
2. Run Forge workstation precheck and confirm scope.
3. Run fresh Forge export.
4. Run Forge export integrity gate.
5. Review run report and skip manifest.
6. Run V2 staged-import preflight and plan.
7. Run V2 canary dry-run.
8. Back up the active store explicitly.
9. Run full staged import into the intended store.
10. Run post-ingest health and Tier 1 clean audit.
11. Run frozen 400-query eval against the intended authoritative store.
12. Compare against the accepted `226 PASS` baseline.
13. Run frozen demo-safe pack.
14. Package all artifacts, SHAs, hashes, and reports into one timestamped promotion directory.

## Must-Freeze Items

- Forge SHA
- V2 SHA
- Forge `config.yaml`
- V2 `config.yaml`
- 400-query pack hash
- demo-safe pack hash
- source root path policy
- output store path
- Tier 1 clean store path
- GPU selection rule
- OCR scope decision
- metadata-contract decision

## Must-Pass Before Run

- both repos clean on promotion-critical `src/` and `scripts/` surfaces
- Forge precheck PASS
- V2 `health_check.py` PASS
- V2 `validate_setup.py` PASS
- source root readable
- free disk confirmed
- chosen GPU free
- export integrity PASS
- staged-import preflight PASS
- canary dry-run PASS
- benchmark pack hash recorded
- demo-safe pack exists as a real frozen file

## Must-Pass After Run

- export artifacts complete
- export manifest counts consistent
- import row count matches manifest chunk count
- Tier 1 clean audit PASS
- relationship count non-regressive
- `extracted_table_rows=0` explicitly documented if unchanged
- 400-query rerun produces JSON + markdown with provenance
- no unexplained regression beyond noise vs `226 PASS`
- demo-safe packet green
- all artifacts placed under one timestamped promotion run directory

## Highest-Risk Failure Modes

1. **Dirty-tree promotion**
   - result cannot be tied to a trustworthy SHA
2. **Wrong query pack**
   - `run_production_eval.py` default still points at the legacy 25-query pack if `--queries` is omitted
3. **Store-path ambiguity**
   - accepted clean Tier 1 baseline versus active default store can diverge silently
4. **Wrong store target**
   - shadow, sprint, backup, and clean store directories make accidental evaluation on the wrong store easy
5. **Demo-pack contamination**
   - demo-safe packet exists only as an exclusion concept, not yet as a frozen file
6. **Metadata-contract treadmill**
   - another fresh 7-key Forge export lands and V2 keeps doing regex-on-path instead of moving retrieval forward

## Minimum Additional Work Before Promotion Is Worth Doing

1. Finish Lane 1 and get a QA verdict.
2. Commit or revert promotion-critical dirty-tree changes in both repos.
3. Fix the `run_production_eval.py` default-pack foot-gun, or require explicit `--queries`.
4. Resolve clean-store versus active-store measurement ambiguity.
5. Materialize a real frozen demo-safe query-pack file.
6. Record an explicit Forge metadata decision:
   - amend before promotion
   - or waive and treat the run as a limited refresh, not a retrieval-claim run
7. Decide whether `ORG=0` is accepted, fixed, or waived.
8. Keep GUI and other background heavy work off the machine during the promotion window.

## Coordinator Verdict

- **Freeze first, then promote.**
- Do not spend the next authoritative run until:
  - Lane 1 is QA-passed
  - the repo SHAs are clean and tagged
  - store-path ambiguity is resolved
  - the wrong-pack default is removed or neutralized
- If the metadata contract is not amended before the run, downgrade the goal of that run explicitly:
  - valid structured-store refresh
  - **not** a serious retrieval-architecture claim
