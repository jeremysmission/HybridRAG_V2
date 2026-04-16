"""Test module for the benchmark gui panels behavior. The checks here explain what the repository expects to keep working."""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))
os.environ["HYBRIDRAG_HEADLESS"] = "1"

import tkinter as tk  # noqa: E402

from src.gui.helpers.safe_after import drain_ui_queue  # noqa: E402
from src.gui.eval_panels.benchmark_runners import (  # noqa: E402
    AggregationBenchmarkRunner,
    CountBenchmarkRunner,
    RagasEvalRunner,
)


@pytest.fixture
def withdrawn_root():
    """Support this test module by handling the withdrawn root step."""
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


def _collect_runner_events(runner_cls, **kwargs):
    """Support this test module by handling the collect runner events step."""
    events = []
    done = threading.Event()

    def on_event(kind: str, payload: dict) -> None:
        events.append((kind, payload))
        if kind == "done":
            done.set()

    runner = runner_cls(on_event=on_event)
    runner.start(**kwargs)
    assert done.wait(timeout=60), "runner did not emit terminal done"
    if runner._thread is not None:
        runner._thread.join(timeout=5)
    return events


def test_aggregation_runner_self_check_writes_output(tmp_path: Path):
    """Verify that aggregation runner self check writes output behaves the way the team expects."""
    from scripts.run_aggregation_benchmark_2026_04_15 import DEFAULT_MANIFEST

    output_path = tmp_path / "aggregation_output.json"
    events = _collect_runner_events(
        AggregationBenchmarkRunner,
        manifest_path=DEFAULT_MANIFEST,
        answers_path=None,
        output_path=output_path,
        min_pass_rate=1.0,
    )
    done = [payload for kind, payload in events if kind == "done"]
    assert len(done) == 1
    assert done[0]["status"] == "PASS"
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["pass_count"] == 12
    assert payload["gate_pass"] is True


def test_count_runner_missing_targets_emits_failed_done(tmp_path: Path):
    """Verify that count runner missing targets emits failed done behaves the way the team expects."""
    events = _collect_runner_events(
        CountBenchmarkRunner,
        targets_path=tmp_path / "missing.json",
        lance_db=tmp_path / "missing_lancedb",
        entity_db=tmp_path / "missing.sqlite3",
        output_dir=tmp_path / "out",
        modes=("raw_mentions",),
        include_deferred=False,
        predictions_json=None,
    )
    done = [payload for kind, payload in events if kind == "done"]
    assert len(done) == 1
    assert done[0]["status"] == "FAILED"
    assert "Target set not found" in (done[0]["error"] or "")


def test_ragas_runner_analysis_only_writes_output(tmp_path: Path):
    """Verify that ragas runner analysis only writes output behaves the way the team expects."""
    from scripts.run_ragas_eval import DEFAULT_QUERIES

    output_path = tmp_path / "ragas_output.json"
    events = _collect_runner_events(
        RagasEvalRunner,
        queries_path=DEFAULT_QUERIES,
        output_path=output_path,
        limit=3,
        analysis_only=True,
        top_k=5,
    )
    done = [payload for kind, payload in events if kind == "done"]
    assert len(done) == 1
    assert done[0]["status"] == "PASS"
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["summary"]["surface"] == "RAGAS"
    assert payload["summary"]["analysis_only"] is True
    assert payload["summary"]["readiness"]["total_queries"] >= 1


def test_aggregation_panel_dispatches_done_and_output_state(withdrawn_root, tmp_path: Path):
    """Verify that aggregation panel dispatches done and output state behaves the way the team expects."""
    from src.gui.eval_panels.aggregation_panel import AggregationPanel

    panel = AggregationPanel(withdrawn_root)
    panel.pack()
    withdrawn_root.update_idletasks()

    out = tmp_path / "aggregation.json"
    out.write_text("{}", encoding="utf-8")
    panel._dispatch_event("progress", {"current": 6, "total": 12})
    panel._dispatch_event(
        "done",
        {
            "status": "PASS",
            "error": None,
            "elapsed_s": 1.2,
            "summary": {
                "benchmark_id": "aggregation_benchmark_2026-04-15",
                "mode": "self-check",
                "gate_pass": True,
                "pass_count": 12,
                "total_items": 12,
                "pass_rate": 1.0,
            },
            "artifact_paths": {"output_json": str(out)},
        },
    )
    drain_ui_queue()
    assert panel._progress_label.cget("text") == "6 / 12"
    assert "benchmark: aggregation_benchmark_2026-04-15" in panel._var_summary.get()
    assert "Output JSON:" in panel._var_artifact.get()
    assert str(panel._btn_open.cget("state")) != "disabled"


def test_count_panel_dispatches_done_and_artifact_state(withdrawn_root, tmp_path: Path):
    """Verify that count panel dispatches done and artifact state behaves the way the team expects."""
    from src.gui.eval_panels.count_panel import CountPanel

    panel = CountPanel(withdrawn_root)
    panel.pack()
    withdrawn_root.update_idletasks()

    json_path = tmp_path / "count.json"
    md_path = tmp_path / "count.md"
    json_path.write_text("{}", encoding="utf-8")
    md_path.write_text("# ok\n", encoding="utf-8")
    panel._dispatch_event("progress", {"current": 3, "total": 7})
    panel._dispatch_event(
        "done",
        {
            "status": "PASS",
            "error": None,
            "elapsed_s": 2.5,
            "lane_name": "count_benchmark_tranche1_frozen",
            "summary": {
                "selected_targets": 7,
                "expected_exact": 7,
                "expected_total": 7,
                "prediction_total": 0,
                "prediction_exact": 0,
                "prediction_max_abs_error": None,
            },
            "artifact_paths": {
                "output_json": str(json_path),
                "output_md": str(md_path),
            },
        },
    )
    drain_ui_queue()
    assert panel._progress_label.cget("text") == "3 / 7"
    assert "lane:       count_benchmark_tranche1_frozen" in panel._var_summary.get()
    assert "JSON:" in panel._var_artifacts.get()
    assert str(panel._btn_open_json.cget("state")) != "disabled"
    assert str(panel._btn_open_md.cget("state")) != "disabled"


def test_ragas_panel_dispatches_done_and_artifact_state(withdrawn_root, tmp_path: Path):
    """Verify that ragas panel dispatches done and artifact state behaves the way the team expects."""
    from src.gui.eval_panels.ragas_panel import RagasPanel

    panel = RagasPanel(withdrawn_root)
    panel.pack()
    withdrawn_root.update_idletasks()

    json_path = tmp_path / "ragas.json"
    json_path.write_text("{}", encoding="utf-8")
    panel._dispatch_event("progress", {"current": 4, "total": 10})
    panel._dispatch_event(
        "done",
        {
            "status": "PASS",
            "error": None,
            "elapsed_s": 1.4,
            "proof_text": "eligible=9/10; phase2c_ready=8/10; ragas_installed=no",
            "summary": {
                "queries_pack_name": "production_queries_400_2026-04-12.json",
                "analysis_only": True,
                "readiness": {
                    "eligible_for_retrieval_metrics": 9,
                    "fully_phase2c_enriched": 8,
                    "total_queries": 10,
                },
                "dependencies": {
                    "ragas_installed": False,
                },
                "metric_summaries": [],
            },
            "artifact_paths": {
                "output_json": str(json_path),
            },
        },
    )
    drain_ui_queue()
    assert panel._progress_label.cget("text") == "4 / 10"
    assert "mode:       analysis-only" in panel._var_summary.get()
    assert "Artifact:" in panel._var_artifact.get()
    assert "Proof:" in panel._var_artifact.get()
    assert str(panel._btn_open.cget("state")) != "disabled"


def test_eval_gui_exposes_aggregation_and_count_tabs():
    """Verify that eval gui exposes aggregation and count tabs behaves the way the team expects."""
    from src.gui import eval_gui as gui_mod

    labels = [label for label, _cls in gui_mod.TABS]
    assert "Aggregation" in labels
    assert "Count" in labels
    assert "RAGAS" in labels
