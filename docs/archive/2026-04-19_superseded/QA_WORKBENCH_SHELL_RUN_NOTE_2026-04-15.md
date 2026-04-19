# QA Workbench Shell Run Note 2026-04-15

This change adds a launchable QA Workbench shell on top of the existing eval GUI instead of creating a parallel GUI framework.

What landed:

- `src.gui.qa_workbench` as the canonical module entrypoint
- `scripts/qa_workbench.py` as the direct-script shim
- `start_qa_workbench.bat` as the operator launcher
- a Baseline tab that reuses the existing Launch / Results / Compare / History panels
- placeholder tabs for Aggregation, Count, Regression, and History / Ledger with real artifact path expectations
- shared run-summary and provenance cards at the top of the shell

Validation:

- `python -m py_compile` on the new GUI entrypoint and test file
- `pytest -q tests/test_qa_workbench.py`
- `start_qa_workbench.bat --dry-run`

Launch:

- `.venv\\Scripts\\python.exe -m src.gui.qa_workbench`
- or double-click `start_qa_workbench.bat`
