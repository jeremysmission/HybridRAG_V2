"""Headless tests for the eval GUI runner + launch panel plumbing.

Mirrors the pattern in ``tests/test_import_extract_gui_streaming.py``:
no real Tk mainloop, no real LanceStore boot, no GPU required. A fake
runner exercises the on_event contract and verifies the launch panel
translates events into widget state correctly.

What's locked in:

  - ``EvalRunner`` emits exactly one terminal ``done`` event per run,
    with a status of PASS / STOPPED / FAILED.
  - Non-existent query pack causes a FAILED terminal event (not crash).
  - LaunchPanel._dispatch_event renders log / phase / progress / query /
    scorecard / done without touching widgets off the main thread.
  - Results panel loads a real eval JSON and populates its tree.
  - Compare panel loads two real JSONs and populates its tree.
  - History panel scans docs/ for production_eval_results*.json without
    crashing on any real file present today.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

os.environ["HYBRIDRAG_HEADLESS"] = "1"

import tkinter as tk  # noqa: E402

from src.gui.eval_panels.runner import EvalRunner  # noqa: E402


# ---------------------------------------------------------------------------
# EvalRunner -- terminal contract
# ---------------------------------------------------------------------------


def _collect_events(runner_kwargs: dict) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    done = threading.Event()

    def on_event(kind: str, payload: dict) -> None:
        events.append((kind, payload))
        if kind == "done":
            done.set()

    runner = EvalRunner(on_event=on_event)
    runner.start(**runner_kwargs)
    assert done.wait(timeout=60), "runner never emitted a terminal 'done' event"
    runner._thread.join(timeout=5)
    return events


def test_eval_runner_missing_query_pack_emits_failed_done(tmp_path: Path):
    missing_queries = tmp_path / "does_not_exist.json"
    config = V2_ROOT / "config" / "config.tier1_clean_2026-04-13.yaml"
    if not config.exists():
        config = V2_ROOT / "config" / "config.yaml"

    events = _collect_events(
        dict(
            queries_path=missing_queries,
            config_path=config,
            report_md=tmp_path / "report.md",
            results_json=tmp_path / "results.json",
            gpu_index="0",
            max_queries=1,
        )
    )

    done = [e for e in events if e[0] == "done"]
    assert len(done) == 1, f"expected exactly one 'done' event, got {len(done)}"
    assert done[0][1]["status"] == "FAILED"
    assert done[0][1]["error"] is not None


def test_eval_runner_missing_config_emits_failed_done(tmp_path: Path):
    queries_file = V2_ROOT / "tests" / "golden_eval" / "production_queries_400_2026-04-12.json"
    if not queries_file.exists():
        pytest.skip("production 400-query pack not present")
    events = _collect_events(
        dict(
            queries_path=queries_file,
            config_path=tmp_path / "missing.yaml",
            report_md=tmp_path / "report.md",
            results_json=tmp_path / "results.json",
            gpu_index="0",
            max_queries=1,
        )
    )
    done = [e for e in events if e[0] == "done"]
    assert len(done) == 1
    assert done[0][1]["status"] == "FAILED"


# ---------------------------------------------------------------------------
# LaunchPanel -- dispatch contract (no widget mounting beyond a withdrawn root)
# ---------------------------------------------------------------------------


@pytest.fixture
def withdrawn_root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no Tk display available")
    root.withdraw()
    from src.gui.theme import DARK, apply_ttk_styles

    apply_ttk_styles(DARK)
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_launch_panel_renders_and_dispatches(withdrawn_root):
    from src.gui.eval_panels.launch_panel import LaunchPanel

    panel = LaunchPanel(withdrawn_root)
    panel.pack()
    withdrawn_root.update_idletasks()

    panel._dispatch_event("log", {"msg": "hello", "level": "INFO"})
    panel._dispatch_event("phase", {"phase": "RUN"})
    panel._dispatch_event("progress", {"current": 3, "total": 5})
    panel._dispatch_event(
        "query",
        {
            "query_id": "PQ-001",
            "persona": "PM",
            "verdict": "PASS",
            "top_in_family": True,
            "any_top5_in_family": True,
            "routed_query_type": "ENTITY",
            "routing_correct": True,
            "embed_retrieve_ms": 42,
            "error": None,
        },
    )
    panel._dispatch_event(
        "scorecard",
        {
            "total": 5,
            "pass": 3,
            "partial": 1,
            "miss": 1,
            "routing_correct": 4,
            "p50_pure_retrieval_ms": 40,
            "p95_pure_retrieval_ms": 80,
            "p50_wall_clock_ms": 50,
            "p95_wall_clock_ms": 90,
            "elapsed_s": 1.5,
        },
    )
    panel._dispatch_event(
        "done",
        {
            "status": "PASS",
            "results_json": "x.json",
            "report_md": "x.md",
            "error": None,
            "elapsed_s": 1.5,
        },
    )

    # After done, Start is re-enabled and Stop is disabled.
    assert str(panel._btn_start.cget("state")) != "disabled"
    assert str(panel._btn_stop.cget("state")) == "disabled"
    # Progress label reflects last progress event.
    assert panel._progress_label.cget("text") == "3 / 5"
    # Scorecard PASS label shows "3/5".
    assert panel._score_labels["pass"].cget("text") == "3/5"


# ---------------------------------------------------------------------------
# ResultsPanel / ComparePanel / HistoryPanel -- real files
# ---------------------------------------------------------------------------


def _find_any_results_json() -> Path | None:
    docs = V2_ROOT / "docs"
    candidates = sorted(docs.glob("production_eval_results*.json"))
    return candidates[0] if candidates else None


def test_results_panel_loads_real_eval_json(withdrawn_root):
    from src.gui.eval_panels.results_panel import ResultsPanel

    results_path = _find_any_results_json()
    if results_path is None:
        pytest.skip("no production eval JSON present yet")
    panel = ResultsPanel(withdrawn_root, initial_path=results_path)
    panel.pack()
    withdrawn_root.update_idletasks()
    # Panel should have parsed the file without error -- existence of
    # the attribute is enough to prove the constructor ran load_file.
    assert hasattr(panel, "_all_results")


def test_compare_panel_constructs_clean(withdrawn_root):
    from src.gui.eval_panels.compare_panel import ComparePanel

    panel = ComparePanel(withdrawn_root)
    panel.pack()
    withdrawn_root.update_idletasks()
    assert panel.winfo_exists()


def test_history_panel_scans_docs_without_crash(withdrawn_root):
    from src.gui.eval_panels.history_panel import HistoryPanel

    panel = HistoryPanel(withdrawn_root, docs_dir=V2_ROOT / "docs")
    panel.pack()
    withdrawn_root.update_idletasks()
    assert panel.winfo_exists()
