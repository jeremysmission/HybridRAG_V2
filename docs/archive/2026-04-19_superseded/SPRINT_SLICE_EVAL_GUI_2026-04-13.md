# Sprint Slice: Eval GUI (2026-04-13)

**Owner:** Jeremy Randall (HybridRAG_V2)
**Repo:** HybridRAG_V2
**Date/time:** 2026-04-13, afternoon MDT
**Co-pilot:** CoPilot+

## Goal

Build a dedicated Tkinter GUI (`scripts/eval_gui.py`) for the 400-query production eval
workflow so retrieval/routing patches can be launched, streamed, browsed, compared,
and historically tracked without leaving the desktop app. Eliminate the current
CLI-only `python scripts/run_production_eval.py ...` invocation as the sole entry point.

## Motivation

The production eval is now the regression harness for every retrieval/routing patch
landing on the path to the May 2 demo (CDRL hints landed 12:55, CAP/A027 hints landed
this session). Each iteration requires: edit retriever -> run eval -> diff reports.
The diff/browse half of that loop is currently ad-hoc (read 800 KB markdown + JSON
manually). A GUI collapses this into clicks.

## Scope (v1)

In:
1. **Launch panel** -- pick query pack JSON, pick config YAML, pick report output paths,
   start/stop button, live log tail, phase indicator, progress bar, scorecard on completion.
2. **Results browser panel** -- load any eval results JSON, filterable `ttk.Treeview`
   (pass / partial / miss, persona, miss family, difficulty), per-query drill-down showing
   expected vs. retrieved source paths.
3. **Compare panel** -- pick two result JSONs, side-by-side diff with gain / loss / unchanged
   categorization and per-query routing-result deltas.
4. **History panel** -- scan `docs/` for eval result JSONs, show score-over-time timeline,
   link each entry to its patch commit (best-effort `git log` match on the markdown mtime).
5. **Installer + launcher .bat files** matching `start_gui.bat` / `INSTALL_WORKSTATION.bat`
   conventions; double-click install + double-click run.
6. **Headless unit test** following `tests/test_import_extract_gui_streaming.py` pattern
   (`FakeRoot`, stubbed GUI, runner exercised directly -- no mainloop).

Out of v1 (captured here for future slices):
- Patch preview / diff view (would require git integration beyond "find commit")
- Per-persona drilldown dashboards
- RAGAS / generation-quality metrics (retrieval-only for now)
- Auto-relaunch after retriever edits (would need filesystem watcher)

## Design

### Visual style

Exact match to existing GUIs (verified across HybridRAG3_Educational, CorpusForge,
HybridRAG_V2):

- VS Code dark palette via `src/gui/theme.py` (`DARK` dict, `apply_ttk_styles()`)
- Fonts: Segoe UI 11 base / bold / 15 title / 13 section / 10 small; Consolas 10 mono
- Button hierarchy: `Accent.TButton` (Start, primary) / `TButton` (Browse, secondary)
  / `Tertiary.TButton` (Stop, subtle)
- Traffic-light status colors: `#4caf50` / `#ff9800` / `#f44336`
- Scrollable sections via `src/gui/scrollable.py`

### Threading

Reuse the proven pattern. Zero new threading primitives.

- `src/gui/helpers/safe_after.py` for cross-thread UI updates
- 50 ms `_drain_pump` heartbeat (same as `src/gui/app.py`)
- `EvalRunner` class with `_stop_event: threading.Event` and cooperative stop checks
  inside the eval loop
- Background thread emits structured messages onto a queue.Queue: `log`, `phase`,
  `progress`, `query_result`, `scorecard`, `done`
- Terminal-state contract: exactly one `done` message (PASS / STOPPED / FAILED)

### Module layout

```
scripts/
  eval_gui.py                       # entry point -- creates Tk root, composes panels
src/gui/eval_panels/
  __init__.py
  runner.py                         # EvalRunner class (wraps run_production_eval internals)
  launch_panel.py                   # launch controls + live stream
  results_panel.py                  # load + filter eval results JSON
  compare_panel.py                  # two-file diff view
  history_panel.py                  # docs/ scanner + score timeline
tests/
  test_eval_gui_streaming.py        # headless test -- FakeRoot, stub runner, stub store
start_eval_gui.bat                  # double-click launcher (mirrors start_gui.bat)
INSTALL_EVAL_GUI.bat                # double-click installer (delegates to INSTALL_WORKSTATION.bat)
```

### Integration with existing eval pipeline

`runner.py` imports directly from `scripts/run_production_eval.py` helper functions
(avoid subprocess -- direct calls give real-time progress callbacks per the
`import_extract_gui.py` precedent). Where `run_production_eval.py`'s `main()` is
monolithic, the runner reimplements the per-query loop by importing the same
`VectorRetriever`, `LanceStore`, `QueryRouter`, `QueryPipeline`, scoring helpers,
and `Embedder` that `main()` uses. This way, the patched retriever under test is
exercised through the identical code path.

### GPU policy

`start_eval_gui.bat` sets `CUDA_VISIBLE_DEVICES` default = `0`. Workstations are
single-CUDA-GPU (Blackwell Nvidia: RTX 4000 20 GB desktop, RTX 3000 Pro 12 GB
laptop). User can override before launching if needed. Runner refuses to run if
CUDA is unavailable and logs the resolved GPU name on start.

## Evidence when done

Per the 3-tier testing rule:
- **Tier 1 (easy):** headless unit test passes (`pytest tests/test_eval_gui_streaming.py`);
  GUI boots and renders all 4 panels without errors.
- **Tier 2 (stress):** smoke eval with a small query subset (5-10 queries) launched from
  the GUI, streams progress, completes, results load into the browser panel.
- **Tier 3 (negative):** Stop button mid-run cleanly cancels; invalid query pack shows a
  human-readable error; missing config yaml shows a human-readable error.

## Out-of-band rules honored

- No push (sanitize-before-push rule)
- Local commits only, by Jeremy Randall, no AI attribution
- Smoke test runs on the local CUDA GPU (default CUDA_VISIBLE_DEVICES=0)
- Sprint slice captured (this doc) before implementation kicks off
- Research-first: 4 parallel research agents completed before any code written
  (HybridRAG3, CorpusForge, HybridRAG_V2 deep-dive, Tkinter 2025 patterns)

## Links

- Evidence memos driving the eval loop:
  - `docs/CAP_INCIDENT_PATH_HINTS_2026-04-13.md`
  - `docs/LOGISTICS_PATH_SHAPE_MEMO_2026-04-13.md`
  - `docs/PRODUCTION_EVAL_RESULTS_POST_CDRL_PATH_PATCH_400_2026-04-13.md`
- Autonomous execution plan: `AUTONOMOUS_EXECUTION_PLAN_AND_STATUS_2026-04-13.md`
- Existing GUI precedents:
  - `scripts/import_extract_gui.py` (primary pattern source)
  - `src/gui/app.py` (composition + heartbeat)
  - `src/gui/theme.py` (colors / fonts / ttk styles)
  - `src/gui/helpers/safe_after.py` (threading)
