# QA Workbench Smoke + Misuse Run Note 2026-04-15

Scope:
- assembled-product smoke for `src.gui.qa_workbench`
- real runner proof where safe on the current workstation
- explicit separation between real validation, headless validation, and remaining human visual confirmation

Primary repo surfaces:
- `tests/test_qa_workbench.py`
- `tests/_qa_workbench_smoke_runner.py`
- `start_qa_workbench.bat`
- `src/gui/qa_workbench.py`

## What this bundle proves

- QA Workbench launcher dry-run is real, not doc-only
- top-level tab order is stable:
  `Overview -> Baseline -> Aggregation -> Count -> Regression -> History / Ledger`
- Baseline nested notebook still exposes:
  `Launch / Results / Compare / History`
- tab switching during active baseline work stays safe
- closing the workbench during active baseline work still hits the runner stop path
- missing-manifest rejection on the Aggregation lane is covered
- double-start warning on the Aggregation lane is covered
- zero-mode rejection on the Count lane is covered
- invalid-fixture handling on the Regression lane is covered
- Aggregation self-check runs end-to-end against the real frozen manifest
- Count benchmark runs end-to-end against the real audited target set and real stores
- Regression fixture runs end-to-end against the frozen schema-pattern harness
- workbench child panels still accept and render benchmark completion state coherently inside the assembled shell

## Files added or updated

- `tests/test_qa_workbench.py`
  - expanded assembled-shell smoke coverage
  - updated installer text expectation after launcher-label cleanup
- `tests/_qa_workbench_smoke_runner.py`
  - manual end-to-end proof driver
  - persists smoke outputs under:
    `tests/smoke_results/qa_workbench_2026-04-15/`

## Validation performed

### Verified on real repo / hardware

- `start_qa_workbench.bat --dry-run --debug-env`
  - PASS
- `python tests/_qa_workbench_smoke_runner.py`
  - PASS
  - output summary:
    `tests/smoke_results/qa_workbench_2026-04-15/qa_workbench_smoke_summary_20260415_172710.json`
  - aggregation proof artifact:
    `tests/smoke_results/qa_workbench_2026-04-15/aggregation_self_check_2026-04-15.json`
  - count proof artifacts:
    `tests/smoke_results/qa_workbench_2026-04-15/count_benchmark_20260415_172709.json`
    `tests/smoke_results/qa_workbench_2026-04-15/count_benchmark_20260415_172709.md`
  - observed results:
    - aggregation self-check: `12/12`
    - count benchmark frozen exact: `7/7`
    - regression fixture: `50/50`

### Verified headless / automated

- `python -m py_compile tests/test_qa_workbench.py tests/_qa_workbench_smoke_runner.py`
  - PASS
- `python -m pytest -q tests/test_qa_workbench.py`
  - PASS
  - result: `20 passed in 5.02s`

Headless pytest coverage now includes:
- shell mounts real tabs in the correct order
- baseline nested notebook labels
- safe tab switching during active baseline run
- coherent summary / provenance refresh on run completion
- close-path stop behavior for the baseline runner
- aggregation panel completion state rendered inside the shell
- aggregation garbage-path and double-start guard rails
- count panel completion state rendered inside the shell
- count no-mode guard rail
- regression panel frozen fixture run inside the shell
- regression invalid-fixture handling
- launcher/import/install expectations

### Still requires human visual confirmation

- one actual on-screen operator click-through of `start_qa_workbench.bat`
  confirming:
  - the window paints correctly
  - live log panes are readable at normal DPI
  - tab switching feels responsive under a real human hand
  - operator-facing labels look correct visually

The current session did successfully instantiate `QAWorkbench()` via Tk and
read the live tab order, but this was still an automated/headless-style proof,
not a human visual walkthrough.

## Important note on count-runner proof

The real count benchmark proof is captured in the standalone smoke driver,
not in the Tk-bound pytest path. That is intentional:
- the standalone smoke driver proves the real runner path on the real stores
- the pytest file proves the assembled-shell state handling around that lane
- keeping them separate avoids brittle cross-thread Tk timing failures while
  preserving real runner evidence

## Operator takeaway

The QA Workbench is now in a materially stronger state than a panel pile:
- launcher dry-run is real
- assembled tab layout is locked
- baseline misuse paths are covered
- aggregation / count / regression all have end-to-end proof on this repo
- remaining gap is visual/operator acceptance, not missing core harness proof
