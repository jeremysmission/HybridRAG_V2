# RAGAS GUI Panel Run Note — 2026-04-15

Scope:
- adds a real `RAGAS` panel under `src/gui/eval_panels/ragas_panel.py`
- mounts the panel into both `src.gui.eval_gui` and `src.gui.qa_workbench`
- wraps `scripts/run_ragas_eval.py` with a background thread runner in
  `src/gui/eval_panels/benchmark_runners.py`

What the panel does:
- lets the operator pick a query JSON
- accepts an optional limit
- supports analysis-only mode
- writes a proof JSON artifact under `docs/`
- shows a live log, summary block, and artifact/proof text

Artifact shape:
- `docs/ragas_eval_gui_YYYY-MM-DD_HHMMSS.json`
- contains run id, timestamp, status, readiness summary, dependency
  summary, optional metric summaries, and proof text

Shell integration:
- `Eval GUI` gets a selectable `RAGAS` tab
- `QA Workbench` gets a selectable `RAGAS` tab
- QA Workbench summary/provenance strip updates on completed RAGAS runs

Validation:
- targeted GUI tests in `tests/test_benchmark_gui_panels.py`
- targeted workbench tests in `tests/test_qa_workbench.py`
- `py_compile` on the touched GUI + runner + script files
