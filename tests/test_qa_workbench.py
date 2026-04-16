"""Test module for the qa workbench behavior. The checks here explain what the repository expects to keep working."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

os.environ["HYBRIDRAG_HEADLESS"] = "1"

import tkinter as tk  # noqa: E402

from src.gui.helpers.safe_after import drain_ui_queue  # noqa: E402


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


def _spin_until(app: tk.Misc, predicate, *, timeout_s: float = 60.0, label: str = "condition") -> None:
    """Support this test module by handling the spin until step."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            app.update_idletasks()
            app.update()
        except tk.TclError:
            break
        drain_ui_queue()
        if predicate():
            return
        time.sleep(0.05)
    pytest.fail(f"timed out waiting for {label}")


def test_qa_workbench_module_exports():
    """Verify that qa workbench module exports behaves the way the team expects."""
    import src.gui.qa_workbench as canonical

    assert hasattr(canonical, "QAWorkbench")
    assert callable(canonical.main)


def test_qa_workbench_shell_mounts_real_lane_tabs():
    """Verify that qa workbench shell mounts real lane tabs behaves the way the team expects."""
    from src.gui.qa_workbench import QAWorkbench, HistoryLedgerPanel
    from src.gui.eval_panels.aggregation_panel import AggregationPanel
    from src.gui.eval_panels.count_panel import CountPanel
    from src.gui.eval_panels.ragas_panel import RagasPanel
    from src.gui.panels.regression_panel import RegressionPanel

    try:
        app = QAWorkbench()
    except tk.TclError:
        pytest.skip("no Tk display available")
    app.withdraw()
    app.update_idletasks()

    labels = [app._notebook.tab(tab_id, "text") for tab_id in app._notebook.tabs()]
    assert labels == [
        "Overview",
        "Baseline",
        "Aggregation",
        "Count",
        "RAGAS",
        "Regression",
        "History / Ledger",
    ]
    assert isinstance(app._aggregation_panel, AggregationPanel)
    assert isinstance(app._count_panel, CountPanel)
    assert isinstance(app._ragas_panel, RagasPanel)
    assert isinstance(app._regression_panel, RegressionPanel)
    assert isinstance(app._history_ledger_panel, HistoryLedgerPanel)

    app.destroy()


def test_qa_workbench_tab_switching_is_safe_during_active_baseline_run():
    """Verify that qa workbench tab switching is safe during active baseline run behaves the way the team expects."""
    from src.gui.qa_workbench import QAWorkbench

    try:
        app = QAWorkbench()
    except tk.TclError:
        pytest.skip("no Tk display available")
    try:
        app.withdraw()
        app.update_idletasks()

        app._on_run_start(
            {
                "queries_path": "C:/tmp/queries.json",
                "config_path": "C:/tmp/config.yaml",
            }
        )

        labels = [
            "Overview",
            "Aggregation",
            "Count",
            "RAGAS",
            "Regression",
            "History / Ledger",
            "Baseline",
        ]
        for label in labels:
            tab_id = next(tab for tab in app._notebook.tabs() if app._notebook.tab(tab, "text") == label)
            app._notebook.select(tab_id)
            app.update_idletasks()
            assert app._notebook.tab(app._notebook.select(), "text") == label
            assert app._header_status.get() == "Running baseline: queries.json / config.yaml"
    finally:
        try:
            app.destroy()
        except Exception:
            pass


def test_qa_workbench_run_done_updates_summary_provenance_and_refreshes_views(monkeypatch):
    """Verify that qa workbench run done updates summary provenance and refreshes views behaves the way the team expects."""
    from src.gui.qa_workbench import QAWorkbench

    try:
        app = QAWorkbench()
    except tk.TclError:
        pytest.skip("no Tk display available")
    try:
        app.withdraw()
        app.update_idletasks()

        refresh_calls = {"history": 0, "overview": 0}
        monkeypatch.setattr(app._history_ledger_panel, "refresh_history", lambda: refresh_calls.__setitem__("history", refresh_calls["history"] + 1))
        monkeypatch.setattr(app._overview_panel, "refresh", lambda: refresh_calls.__setitem__("overview", refresh_calls["overview"] + 1))

        payload = {
            "status": "PASS",
            "run_id": "20260415_140000",
            "timestamp_utc": "2026-04-15T20:00:00+00:00",
            "queries_pack_name": "production_queries_smoke3.json",
            "config_name": "config.tier1_clean_2026-04-13.yaml",
            "store_path": "C:/HybridRAG_V2/data/index/lancedb",
            "provider": "openai",
            "model": "gpt-4o",
            "router_mode": "llm",
            "score_summary": {
                "pass_count": 3,
                "partial_count": 1,
                "miss_count": 0,
                "routing_correct": 4,
            },
            "strongest_areas": ["query_type: SEMANTIC (100%, n=2)"],
            "weakest_areas": ["query_type: AGGREGATE (50%, n=2)"],
            "artifact_paths": {
                "results_json": "docs/production_eval_results_gui_2026-04-15_140000.json",
                "report_md": "docs/PRODUCTION_EVAL_RESULTS_GUI_2026-04-15_140000.md",
            },
            "queries_path": "C:/HybridRAG_V2/tests/golden_eval/production_queries_smoke3.json",
            "config_path": "C:/HybridRAG_V2/config/config.tier1_clean_2026-04-13.yaml",
        }

        app._on_run_done(payload)

        assert app._header_status.get() == "Last baseline run: PASS (20260415_140000)"
        summary = app._summary_var.get()
        provenance = app._provenance_var.get()
        assert "status: PASS" in summary
        assert "queries: production_queries_smoke3.json" in summary
        assert "router:  llm (openai / gpt-4o)" in summary
        assert "results@:  docs/production_eval_results_gui_2026-04-15_140000.json" in summary
        assert "Queries: production_queries_smoke3.json" in provenance
        assert "Artifacts: docs/production_eval_results_gui_2026-04-15_140000.json" in provenance
        assert refresh_calls == {"history": 1, "overview": 1}
    finally:
        try:
            app.destroy()
        except Exception:
            pass


def test_qa_workbench_ragas_run_done_updates_summary_provenance_and_refreshes_views(monkeypatch):
    """Verify that qa workbench ragas run done updates summary provenance and refreshes views behaves the way the team expects."""
    from src.gui.qa_workbench import QAWorkbench

    try:
        app = QAWorkbench()
    except tk.TclError:
        pytest.skip("no Tk display available")
    try:
        app.withdraw()
        app.update_idletasks()

        refresh_calls = {"history": 0, "overview": 0}
        monkeypatch.setattr(app._history_ledger_panel, "refresh_history", lambda: refresh_calls.__setitem__("history", refresh_calls["history"] + 1))
        monkeypatch.setattr(app._overview_panel, "refresh", lambda: refresh_calls.__setitem__("overview", refresh_calls["overview"] + 1))

        payload = {
            "status": "PASS",
            "surface": "RAGAS",
            "run_id": "20260415_150000",
            "timestamp_utc": "2026-04-15T21:00:00+00:00",
            "queries_pack_name": "production_queries_400_2026-04-12.json",
            "analysis_only": True,
            "limit": 10,
            "proof_text": "eligible=300/400; phase2c_ready=260/400; ragas_installed=no",
            "summary": {
                "readiness": {
                    "eligible_for_retrieval_metrics": 300,
                    "fully_phase2c_enriched": 260,
                    "total_queries": 400,
                },
                "dependencies": {
                    "ragas_installed": False,
                    "rapidfuzz_installed": True,
                },
                "metric_summaries": [],
            },
            "artifact_paths": {
                "output_json": "docs/ragas_eval_gui_2026-04-15_150000.json",
            },
        }

        app._on_ragas_run_done(payload)

        assert app._header_status.get() == "Last RAGAS run: PASS (20260415_150000)"
        summary = app._summary_var.get()
        provenance = app._provenance_var.get()
        assert "surface: RAGAS" in summary
        assert "mode:    analysis-only" in summary
        assert "proof:   eligible=300/400; phase2c_ready=260/400; ragas_installed=no" in summary
        assert "Mode: analysis-only" in provenance
        assert "Artifacts: docs/ragas_eval_gui_2026-04-15_150000.json" in provenance
        assert refresh_calls == {"history": 1, "overview": 1}
    finally:
        try:
            app.destroy()
        except Exception:
            pass


def test_qa_workbench_close_during_active_baseline_run_stops_runner():
    """Verify that qa workbench close during active baseline run stops runner behaves the way the team expects."""
    from src.gui.qa_workbench import QAWorkbench

    try:
        app = QAWorkbench()
    except tk.TclError:
        pytest.skip("no Tk display available")

    class FakeRunner:
        def __init__(self) -> None:
            self.is_alive = True
            self.stop_called = False

        def stop(self) -> None:
            self.stop_called = True

    fake_runner = FakeRunner()
    app._baseline_panel._launch_panel._runner = fake_runner

    try:
        app.withdraw()
        app.update_idletasks()
        app._on_run_start(
            {
                "queries_path": "queries.json",
                "config_path": "config.yaml",
            }
        )
        aggregation_tab = next(
            tab for tab in app._notebook.tabs() if app._notebook.tab(tab, "text") == "Aggregation"
        )
        app._notebook.select(aggregation_tab)
        app.update_idletasks()

        assert app._notebook.tab(app._notebook.select(), "text") == "Aggregation"
        assert app._header_status.get() == "Running baseline: queries.json / config.yaml"

        app._on_close()
        assert fake_runner.stop_called is True
    finally:
        try:
            app.destroy()
        except Exception:
            pass


def test_qa_workbench_embedded_aggregation_runner_self_check_smoke(tmp_path: Path):
    """Verify that qa workbench embedded aggregation runner self check smoke behaves the way the team expects."""
    from src.gui.qa_workbench import QAWorkbench

    try:
        app = QAWorkbench()
    except tk.TclError:
        pytest.skip("no Tk display available")
    try:
        app.withdraw()
        app.update_idletasks()

        panel = app._aggregation_panel
        output_path = tmp_path / "aggregation_workbench_smoke.json"
        panel._var_output.set(str(output_path))
        panel._var_answers.set("")

        panel._on_start()
        aggregation_tab = next(
            tab for tab in app._notebook.tabs() if app._notebook.tab(tab, "text") == "Aggregation"
        )
        count_tab = next(
            tab for tab in app._notebook.tabs() if app._notebook.tab(tab, "text") == "Count"
        )
        app._notebook.select(count_tab)
        app.update_idletasks()
        app._notebook.select(aggregation_tab)

        _spin_until(
            app,
            lambda: panel._var_phase.get().startswith("done") and not panel._runner.is_alive,
            timeout_s=60.0,
            label="aggregation runner done",
        )

        assert output_path.exists()
        assert "benchmark: aggregation_benchmark_2026-04-15" in panel._var_summary.get()
        assert "score:     12/12 (1.000)" in panel._var_summary.get()
        assert "Output JSON:" in panel._var_artifact.get()
    finally:
        try:
            app.destroy()
        except Exception:
            pass


def test_qa_workbench_embedded_count_panel_updates_state_in_shell(tmp_path: Path):
    """Verify that qa workbench embedded count panel updates state in shell behaves the way the team expects."""
    from src.gui.qa_workbench import QAWorkbench

    try:
        app = QAWorkbench()
    except tk.TclError:
        pytest.skip("no Tk display available")
    try:
        app.withdraw()
        app.update_idletasks()

        panel = app._count_panel
        json_path = tmp_path / "count_workbench.json"
        md_path = tmp_path / "count_workbench.md"
        json_path.write_text("{}", encoding="utf-8")
        md_path.write_text("# count\n", encoding="utf-8")
        done_payload = {
            "status": "PASS",
            "error": None,
            "elapsed_s": 50.4,
            "lane_name": "count_benchmark_tranche1_frozen",
            "lane_date": "2026-04-15 MDT",
            "summary": {
                "selected_targets": 7,
                "expected_total": 7,
                "expected_exact": 7,
                "prediction_total": 0,
                "prediction_exact": 0,
                "prediction_max_abs_error": None,
                "per_mode_prediction_exact": None,
            },
            "artifact_paths": {
                "output_json": str(json_path),
                "output_md": str(md_path),
            },
        }

        regression_tab = next(
            tab for tab in app._notebook.tabs() if app._notebook.tab(tab, "text") == "Regression"
        )
        history_tab = next(
            tab for tab in app._notebook.tabs() if app._notebook.tab(tab, "text") == "History / Ledger"
        )
        app._notebook.select(regression_tab)
        app.update_idletasks()
        app._notebook.select(history_tab)
        app.update_idletasks()
        count_tab = next(
            tab for tab in app._notebook.tabs() if app._notebook.tab(tab, "text") == "Count"
        )
        app._notebook.select(count_tab)
        panel._dispatch_event("progress", {"current": 7, "total": 7})
        panel._dispatch_event("done", done_payload)

        assert "lane:       count_benchmark_tranche1_frozen" in panel._var_summary.get()
        assert "frozen:     7/7 exact" in panel._var_summary.get()
        json_lines = panel._var_artifacts.get().splitlines()
        assert any(line.startswith("JSON: ") and line.endswith(".json") for line in json_lines)
        assert any(line.startswith("MD:   ") and line.endswith(".md") for line in json_lines)
    finally:
        try:
            app.destroy()
        except Exception:
            pass


def test_qa_workbench_regression_panel_runs_frozen_fixture_in_shell():
    """Verify that qa workbench regression panel runs frozen fixture in shell behaves the way the team expects."""
    from src.gui.qa_workbench import QAWorkbench

    try:
        app = QAWorkbench()
    except tk.TclError:
        pytest.skip("no Tk display available")
    try:
        app.withdraw()
        app.update_idletasks()

        panel = app._regression_panel
        regression_tab = next(
            tab for tab in app._notebook.tabs() if app._notebook.tab(tab, "text") == "Regression"
        )
        app._notebook.select(regression_tab)
        panel._on_run()

        _spin_until(
            app,
            lambda: panel._last_report is not None and panel._run_btn.cget("text") == "Run Regression",
            timeout_s=30.0,
            label="regression panel run",
        )

        assert panel._last_report is not None
        assert panel._last_report.failed == 0
        assert panel._last_report.passed == panel._last_report.total
        assert "Result: PASS" in panel._summary_text.get("1.0", "end")
    finally:
        try:
            app.destroy()
        except Exception:
            pass


def test_qa_workbench_aggregation_panel_rejects_missing_manifest(monkeypatch, tmp_path: Path):
    """Verify that qa workbench aggregation panel rejects missing manifest behaves the way the team expects."""
    from src.gui.qa_workbench import QAWorkbench

    try:
        app = QAWorkbench()
    except tk.TclError:
        pytest.skip("no Tk display available")
    try:
        app.withdraw()
        app.update_idletasks()

        panel = app._aggregation_panel
        missing_manifest = tmp_path / "missing_manifest.json"
        panel._var_manifest.set(str(missing_manifest))
        panel._var_answers.set("")

        errors: list[tuple[str, str]] = []
        monkeypatch.setattr(
            "src.gui.eval_panels.aggregation_panel.messagebox.showerror",
            lambda title, message: errors.append((title, message)),
        )

        panel._on_start()

        assert errors
        assert "Manifest not found" in errors[0][1]
        assert panel._runner.is_alive is False
    finally:
        try:
            app.destroy()
        except Exception:
            pass


def test_qa_workbench_aggregation_panel_double_start_warns(monkeypatch):
    """Verify that qa workbench aggregation panel double start warns behaves the way the team expects."""
    from src.gui.qa_workbench import QAWorkbench

    try:
        app = QAWorkbench()
    except tk.TclError:
        pytest.skip("no Tk display available")

    class BusyRunner:
        @property
        def is_alive(self) -> bool:
            return True

    try:
        app.withdraw()
        app.update_idletasks()

        panel = app._aggregation_panel
        panel._runner = BusyRunner()

        warnings: list[tuple[str, str]] = []
        monkeypatch.setattr(
            "src.gui.eval_panels.aggregation_panel.messagebox.showwarning",
            lambda title, message: warnings.append((title, message)),
        )

        panel._on_start()

        assert warnings
        assert "already in progress" in warnings[0][1]
    finally:
        try:
            app.destroy()
        except Exception:
            pass


def test_qa_workbench_count_panel_requires_at_least_one_mode(monkeypatch, tmp_path: Path):
    """Verify that qa workbench count panel requires at least one mode behaves the way the team expects."""
    from src.gui.qa_workbench import QAWorkbench

    try:
        app = QAWorkbench()
    except tk.TclError:
        pytest.skip("no Tk display available")
    try:
        app.withdraw()
        app.update_idletasks()

        panel = app._count_panel
        targets_path = tmp_path / "targets.json"
        lance_dir = tmp_path / "lance"
        entity_db = tmp_path / "entity.sqlite3"
        targets_path.write_text("{\"lane_name\":\"x\",\"lane_date\":\"x\",\"targets\":[]}", encoding="utf-8")
        lance_dir.mkdir()
        entity_db.write_text("", encoding="utf-8")

        panel._var_targets.set(str(targets_path))
        panel._var_lance_db.set(str(lance_dir))
        panel._var_entity_db.set(str(entity_db))
        panel._var_predictions.set("")
        for var in panel._mode_vars.values():
            var.set(False)

        errors: list[tuple[str, str]] = []
        monkeypatch.setattr(
            "src.gui.eval_panels.count_panel.messagebox.showerror",
            lambda title, message: errors.append((title, message)),
        )

        panel._on_start()

        assert errors
        assert "Select at least one count mode." in errors[0][1]
        assert panel._runner.is_alive is False
    finally:
        try:
            app.destroy()
        except Exception:
            pass


def test_qa_workbench_regression_panel_invalid_fixture_surfaces_error():
    """Verify that qa workbench regression panel invalid fixture surfaces error behaves the way the team expects."""
    from src.gui.qa_workbench import QAWorkbench

    try:
        app = QAWorkbench()
    except tk.TclError:
        pytest.skip("no Tk display available")
    try:
        app.withdraw()
        app.update_idletasks()

        panel = app._regression_panel
        panel._fixture_path_var.set(str(V2_ROOT / "tests" / "regression" / "schema_pattern" / "missing_fixture.json"))
        panel._refresh_fixture_meta()

        summary = panel._summary_text.get("1.0", "end")
        assert "Failed to load fixture" in summary
    finally:
        try:
            app.destroy()
        except Exception:
            pass


def test_baseline_workbench_panel_reuses_eval_tabs(withdrawn_root):
    """Verify that baseline workbench panel reuses eval tabs behaves the way the team expects."""
    from src.gui.qa_workbench import BaselineWorkbenchPanel

    panel = BaselineWorkbenchPanel(withdrawn_root)
    panel.pack()
    withdrawn_root.update_idletasks()

    labels = [panel._notebook.tab(tab_id, "text") for tab_id in panel._notebook.tabs()]
    assert labels == ["Launch", "Results", "Compare", "History"]


def test_artifact_placeholder_panel_lists_expected_paths(withdrawn_root, tmp_path: Path):
    """Verify that artifact placeholder panel lists expected paths behaves the way the team expects."""
    from src.gui.qa_workbench import ArtifactPlaceholderPanel

    ready_file = tmp_path / "ready.txt"
    ready_file.write_text("ok", encoding="utf-8")
    waiting_file = tmp_path / "waiting.txt"

    panel = ArtifactPlaceholderPanel(
        withdrawn_root,
        title="Count",
        status_text="placeholder",
        summary_text="summary",
        artifact_paths=[("Ready", ready_file), ("Waiting", waiting_file)],
    )
    panel.pack()
    withdrawn_root.update_idletasks()

    text = panel._paths_var.get()
    assert "Ready: [ready]" in text
    assert "Waiting: [waiting]" in text


def test_history_ledger_panel_marks_locked_view_as_untouched(withdrawn_root):
    """Verify that history ledger panel marks locked view as untouched behaves the way the team expects."""
    from src.gui.qa_workbench import HistoryLedgerPanel

    panel = HistoryLedgerPanel(withdrawn_root)
    panel.pack()
    withdrawn_root.update_idletasks()

    text = panel._ledger_var.get()
    assert "acceptance-only" in text
    assert "hardtail_v1_10_locked.jsonl" in text


def test_start_qa_workbench_launcher_uses_module_form_and_real_entrypoint():
    """Verify that start qa workbench launcher uses module form and real entrypoint behaves the way the team expects."""
    bat_path = V2_ROOT / "start_qa_workbench.bat"
    assert bat_path.exists()
    bat_src = bat_path.read_text(encoding="utf-8", errors="replace")
    assert 'GUI_MODULE=src.gui.qa_workbench' in bat_src
    assert "-m %GUI_MODULE%" in bat_src
    assert "restore src\\gui\\qa_workbench.py" in bat_src
    assert "restore scripts\\qa_workbench.py" not in bat_src


def test_start_qa_workbench_dry_run_smoke():
    """Verify that start qa workbench dry run smoke behaves the way the team expects."""
    if os.name != "nt":
        pytest.skip("batch dry-run smoke is Windows-only")

    bat_path = V2_ROOT / "start_qa_workbench.bat"
    env = os.environ.copy()
    env["HYBRIDRAG_NO_PAUSE"] = "1"
    proc = subprocess.run(
        ["cmd.exe", "/c", str(bat_path), "--dry-run"],
        cwd=str(V2_ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    assert "HybridRAG V2 QA Workbench launcher -- dry run" in output
    assert "GUI module:      src.gui.qa_workbench" in output
    assert "Proxy present:" in output
    assert "NO_PROXY:" in output


def test_scripts_qa_workbench_shim_forwards_to_main():
    """Verify that scripts qa workbench shim forwards to main behaves the way the team expects."""
    shim_path = V2_ROOT / "scripts" / "qa_workbench.py"
    assert shim_path.exists()
    shim_src = shim_path.read_text(encoding="utf-8")
    assert "from src.gui.qa_workbench import main" in shim_src


def test_install_eval_gui_mentions_workbench_and_verifies_import():
    """Verify that install eval gui mentions workbench and verifies import behaves the way the team expects."""
    installer_path = V2_ROOT / "INSTALL_EVAL_GUI.bat"
    assert installer_path.exists()
    installer_src = installer_path.read_text(encoding="utf-8", errors="replace")
    assert "from src.gui.qa_workbench import QAWorkbench" in installer_src
    assert "Launch with: start_qa_workbench.bat  [recommended management-facing shell]" in installer_src


def test_start_eval_gui_launcher_includes_canonical_path_hints():
    """Verify that start eval gui launcher includes canonical path hints behaves the way the team expects."""
    bat_path = V2_ROOT / "start_eval_gui.bat"
    assert bat_path.exists()
    bat_src = bat_path.read_text(encoding="utf-8", errors="replace")
    assert "Canonical GUI path: %GUI_SCRIPT%" in bat_src
    assert "Canonical module: %GUI_MODULE%" in bat_src
