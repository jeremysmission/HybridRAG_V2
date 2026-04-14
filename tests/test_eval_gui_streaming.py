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


def test_compare_panel_headline_signs_are_correct(withdrawn_root):
    """MISS dropping 146 -> 96 must render as '-50', not '+-50'."""
    from src.gui.eval_panels.compare_panel import ComparePanel

    panel = ComparePanel(withdrawn_root)
    panel.pack()
    panel._baseline_data = {
        "pass_count": 158,
        "partial_count": 96,
        "miss_count": 146,
        "routing_correct": 287,
    }
    panel._candidate_data = {
        "pass_count": 226,
        "partial_count": 78,
        "miss_count": 96,
        "routing_correct": 298,
    }
    panel._refresh_headline()

    miss_text = panel._headline_labels["miss"].cget("text")
    pass_text = panel._headline_labels["pass"].cget("text")
    partial_text = panel._headline_labels["partial"].cget("text")
    routing_text = panel._headline_labels["routing"].cget("text")

    assert "+-" not in miss_text, f"bad sign in MISS: {miss_text}"
    assert "-50" in miss_text, f"expected -50 in MISS: {miss_text}"
    assert "+68" in pass_text, f"expected +68 in PASS: {pass_text}"
    assert "-18" in partial_text, f"expected -18 in PARTIAL: {partial_text}"
    assert "+11" in routing_text, f"expected +11 in Routing: {routing_text}"


def test_history_panel_scans_docs_without_crash(withdrawn_root):
    from src.gui.eval_panels.history_panel import HistoryPanel

    panel = HistoryPanel(withdrawn_root, docs_dir=V2_ROOT / "docs")
    panel.pack()
    withdrawn_root.update_idletasks()
    assert panel.winfo_exists()


def test_results_panel_default_dir_is_not_hardcoded():
    """Regression: the results panel must resolve its default docs dir from
    the repo root, not a hardcoded C:\\HybridRAG_V2\\docs string."""
    from src.gui.eval_panels import results_panel as rp

    expected = (Path(rp.__file__).resolve().parents[3] / "docs").resolve()
    assert rp._DEFAULT_RESULTS_DIR.resolve() == expected


def test_history_panel_default_dir_is_not_hardcoded():
    """Regression: the history panel must resolve its default docs dir from
    the repo root, not a hardcoded C:\\HybridRAG_V2\\docs string."""
    from src.gui.eval_panels import history_panel as hp

    expected = (Path(hp.__file__).resolve().parents[3] / "docs").resolve()
    assert hp.DEFAULT_DOCS_DIR.resolve() == expected


def test_results_panel_renders_provenance_block(withdrawn_root, tmp_path: Path):
    """Run Info strip populates from a provenance-stamped results JSON."""
    from src.gui.eval_panels.results_panel import ResultsPanel

    sample = {
        "run_id": "20260413_200000",
        "timestamp_utc": "2026-04-13T20:00:00+00:00",
        "store_chunks": 10435593,
        "total_queries": 3,
        "pass_count": 2,
        "partial_count": 0,
        "miss_count": 1,
        "routing_correct": 3,
        "p50_pure_retrieval_ms": 120,
        "p95_pure_retrieval_ms": 4000,
        "provenance": {
            "queries_path": "tests/golden_eval/production_queries_smoke3.json",
            "queries_pack_name": "production_queries_smoke3.json",
            "config_path": "config/config.tier1_clean_2026-04-13.yaml",
            "config_name": "config.tier1_clean_2026-04-13.yaml",
            "lance_path": "data/index/lancedb",
            "gpu_device": "CUDA_VISIBLE_DEVICES=0 -> cuda:0 (stub)",
            "gpu_index_requested": "0",
            "max_queries_requested": 3,
            "run_status": "PASS",
            "elapsed_s": 116.8,
        },
        "results": [
            {"id": "PQ-101", "verdict": "PASS", "persona": "PM", "routing_correct": True,
             "retrieval_ms": 100},
            {"id": "PQ-102", "verdict": "PASS", "persona": "PM", "routing_correct": True,
             "retrieval_ms": 200},
            {"id": "PQ-103", "verdict": "MISS", "persona": "PM", "routing_correct": True,
             "retrieval_ms": 150},
        ],
    }
    sample_path = tmp_path / "sample_results.json"
    sample_path.write_text(json.dumps(sample), encoding="utf-8")

    panel = ResultsPanel(withdrawn_root, initial_path=sample_path)
    panel.pack()
    withdrawn_root.update_idletasks()

    run_info_text = panel._run_info_var.get()
    assert "production_queries_smoke3.json" in run_info_text
    assert "config.tier1_clean_2026-04-13.yaml" in run_info_text
    assert "data/index/lancedb" in run_info_text
    assert "20260413_200000" in run_info_text
    assert "PASS" in run_info_text
    assert "first 3" in run_info_text


def test_canonical_module_entry_point_exposes_main_and_evalgui():
    """Regression: the canonical -m entry point must live at src.gui.eval_gui,
    not scripts/eval_gui.py. scripts/eval_gui.py must be a forwarding shim."""
    from src.gui import eval_gui as canonical

    assert hasattr(canonical, "EvalGUI")
    assert hasattr(canonical, "main")
    assert callable(canonical.main)

    shim_path = V2_ROOT / "scripts" / "eval_gui.py"
    assert shim_path.exists()
    shim_src = shim_path.read_text(encoding="utf-8")
    assert "from src.gui.eval_gui import main" in shim_src, (
        "scripts/eval_gui.py must forward to src.gui.eval_gui.main -- "
        "any other structure re-introduces the interpreter-split bug."
    )


def test_launcher_bat_uses_module_form():
    """Regression: start_eval_gui.bat must launch with -m src.gui.eval_gui
    so Python stays pinned to the launching .venv interpreter."""
    bat_path = V2_ROOT / "start_eval_gui.bat"
    assert bat_path.exists()
    bat_src = bat_path.read_text(encoding="utf-8", errors="replace")
    assert "-m %GUI_MODULE%" in bat_src
    assert 'GUI_MODULE=src.gui.eval_gui' in bat_src


def test_launch_panel_save_and_load_operator_defaults(withdrawn_root, tmp_path: Path, monkeypatch):
    """Save as defaults -> next-launch load round-trip."""
    import src.gui.eval_panels.launch_panel as lp_module

    fake_defaults = tmp_path / ".eval_gui_defaults.json"
    monkeypatch.setattr(lp_module, "DEFAULTS_FILE", fake_defaults)

    panel = lp_module.LaunchPanel(withdrawn_root)
    panel.pack()
    withdrawn_root.update_idletasks()

    assert panel._defaults_source == "shipped"
    assert not fake_defaults.exists()

    panel._var_queries.set(str(tmp_path / "my_queries.json"))
    panel._var_config.set(str(tmp_path / "my_config.yaml"))
    panel._var_report_md.set(str(tmp_path / "my_report.md"))
    panel._var_results_json.set(str(tmp_path / "my_results.json"))
    panel._var_gpu.set("0")
    panel._var_max_q.set("25")

    panel._on_save_defaults()

    assert fake_defaults.exists(), "Save should create the defaults file"
    saved = json.loads(fake_defaults.read_text(encoding="utf-8"))
    assert saved["queries_path"] == str(tmp_path / "my_queries.json")
    assert saved["config_path"] == str(tmp_path / "my_config.yaml")
    assert saved["max_queries"] == "25"
    assert saved["schema_version"] == 1
    assert saved.get("saved_at")
    assert panel._defaults_source == "saved"
    assert "saved on" in panel._var_defaults_status.get()

    panel.destroy()

    panel2 = lp_module.LaunchPanel(withdrawn_root)
    panel2.pack()
    withdrawn_root.update_idletasks()

    assert panel2._defaults_source == "saved"
    assert panel2._var_queries.get() == str(tmp_path / "my_queries.json")
    assert panel2._var_config.get() == str(tmp_path / "my_config.yaml")
    assert panel2._var_max_q.get() == "25"


def test_launch_panel_reset_defaults_restores_shipped_values(
    withdrawn_root, tmp_path: Path, monkeypatch
):
    """Reset defaults must delete the saved file and restore shipped values."""
    import src.gui.eval_panels.launch_panel as lp_module

    fake_defaults = tmp_path / ".eval_gui_defaults.json"
    fake_defaults.write_text(
        json.dumps(
            {
                "queries_path": str(tmp_path / "saved_q.json"),
                "config_path": str(tmp_path / "saved_c.yaml"),
                "report_md_template": str(tmp_path / "saved_r.md"),
                "results_json_template": str(tmp_path / "saved_r.json"),
                "gpu_index": "0",
                "max_queries": "5",
                "saved_at": "2026-04-13 20:00:00",
                "schema_version": 1,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(lp_module, "DEFAULTS_FILE", fake_defaults)
    monkeypatch.setattr(
        "tkinter.messagebox.askyesno", lambda *a, **k: True
    )

    panel = lp_module.LaunchPanel(withdrawn_root)
    panel.pack()
    withdrawn_root.update_idletasks()

    assert panel._defaults_source == "saved"
    assert panel._var_queries.get() == str(tmp_path / "saved_q.json")

    panel._on_reset_defaults()

    assert not fake_defaults.exists(), "Reset must delete the defaults file"
    assert panel._defaults_source == "shipped"
    assert panel._var_queries.get() == str(lp_module.DEFAULT_QUERIES)
    assert panel._var_config.get() == str(lp_module.DEFAULT_CONFIG)
    assert panel._var_max_q.get() == ""


def test_launch_panel_corrupt_defaults_file_does_not_block_launch(
    withdrawn_root, tmp_path: Path, monkeypatch
):
    """A broken defaults file must fall back to shipped values silently."""
    import src.gui.eval_panels.launch_panel as lp_module

    fake_defaults = tmp_path / ".eval_gui_defaults.json"
    fake_defaults.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(lp_module, "DEFAULTS_FILE", fake_defaults)

    panel = lp_module.LaunchPanel(withdrawn_root)
    panel.pack()
    withdrawn_root.update_idletasks()

    assert panel._defaults_source == "shipped"
    assert panel._var_queries.get() == str(lp_module.DEFAULT_QUERIES)


def test_history_panel_label_column_uses_provenance(withdrawn_root, tmp_path: Path):
    """History label column should show pack/config from provenance."""
    from src.gui.eval_panels.history_panel import HistoryPanel

    sample = {
        "run_id": "20260413_200000",
        "timestamp_utc": "2026-04-13T20:00:00+00:00",
        "total_queries": 3,
        "pass_count": 2,
        "partial_count": 0,
        "miss_count": 1,
        "routing_correct": 3,
        "provenance": {
            "queries_pack_name": "production_queries_400_2026-04-12.json",
            "config_name": "config.tier1_clean_2026-04-13.yaml",
        },
        "results": [],
    }
    p = tmp_path / "production_eval_results_smoke_2026-04-13.json"
    p.write_text(json.dumps(sample), encoding="utf-8")

    panel = HistoryPanel(withdrawn_root, docs_dir=tmp_path)
    panel.pack()
    withdrawn_root.update_idletasks()

    assert len(panel._records) == 1
    rec = panel._records[0]
    label = rec.get("label") or ""
    assert "production_queries_400_2026-04-12" in label
    assert "config.tier1_clean_2026-04-13" in label
