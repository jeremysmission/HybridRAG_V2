"""HybridRAG V2 QA Workbench shell.

Management-facing shell built on top of the existing eval GUI panels.
The goal is to provide one launchable desktop surface for the current QA
lanes without inventing a parallel framework.
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Optional

V2_ROOT = Path(__file__).resolve().parents[2]
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

from src.gui.eval_gui import _sanitize_tk_env  # noqa: E402

_sanitize_tk_env()

from src.gui.theme import (  # noqa: E402
    DARK,
    FONT,
    FONT_BOLD,
    FONT_MONO,
    FONT_SMALL,
    FONT_TITLE,
    apply_ttk_styles,
)
from src.gui.helpers.safe_after import drain_ui_queue  # noqa: E402
from src.gui.eval_panels.aggregation_panel import AggregationPanel  # noqa: E402
from src.gui.eval_panels.count_panel import CountPanel  # noqa: E402
from src.gui.eval_panels.compare_panel import ComparePanel  # noqa: E402
from src.gui.eval_panels.history_panel import HistoryPanel  # noqa: E402
from src.gui.eval_panels.launch_panel import LaunchPanel  # noqa: E402
from src.gui.eval_panels.overview_panel import OverviewPanel  # noqa: E402
from src.gui.eval_panels.ragas_panel import RagasPanel  # noqa: E402
from src.gui.eval_panels.results_panel import ResultsPanel  # noqa: E402
from src.gui.panels.regression_panel import RegressionPanel  # noqa: E402


LOCAL_ONLY_ROOT = Path(
    os.environ.get("HYBRIDRAG_LOCAL_ONLY_ROOT", str(Path.home() / "HYBRIDRAG_LOCAL_ONLY"))
)


def _artifact_rows(*rows: tuple[str, Path]) -> list[tuple[str, Path]]:
    """Support the qa workbench workflow by handling the artifact rows step."""
    # FLAG: Likely dead code as of 2026-04-15. Repo-wide search only found the
    # definition, not any call sites. Keep for now until a dedicated cleanup
    # pass confirms whether an external/manual workflow still relies on it.
    return list(rows)


class ArtifactPlaceholderPanel(tk.Frame):
    """Real placeholder panel with status + artifact path expectations."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        title: str,
        status_text: str,
        summary_text: str,
        artifact_paths: list[tuple[str, Path]],
    ) -> None:
        super().__init__(parent, bg=DARK["bg"])
        self._title = title
        self._artifact_paths = artifact_paths
        self._status_var = tk.StringVar(value=status_text)
        self._summary_var = tk.StringVar(value=summary_text)
        self._paths_var = tk.StringVar(value=self._format_paths())
        self._build()

    def _format_paths(self) -> str:
        lines: list[str] = []
        for label, path in self._artifact_paths:
            state = "ready" if path.exists() else "waiting"
            lines.append(f"{label}: [{state}] {path}")
        return "\n".join(lines)

    def _build(self) -> None:
        outer = ttk.Frame(self, style="TFrame", padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text=self._title,
            font=FONT_TITLE,
            foreground=DARK["fg"],
            background=DARK["bg"],
        ).pack(anchor="w", pady=(0, 10))

        status_box = tk.Frame(
            outer,
            bg=DARK["panel_bg"],
            highlightthickness=1,
            highlightbackground=DARK["border"],
        )
        status_box.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            status_box,
            text="Lane Status",
            font=FONT_SMALL,
            bg=DARK["panel_bg"],
            fg=DARK["label_fg"],
        ).pack(anchor="w", padx=10, pady=(8, 0))
        tk.Label(
            status_box,
            textvariable=self._status_var,
            font=FONT_BOLD,
            bg=DARK["panel_bg"],
            fg=DARK["accent"],
            justify="left",
            anchor="w",
            wraplength=1120,
        ).pack(anchor="w", fill=tk.X, padx=10, pady=(0, 8))

        tk.Label(
            outer,
            textvariable=self._summary_var,
            font=FONT,
            bg=DARK["bg"],
            fg=DARK["fg"],
            justify="left",
            anchor="w",
            wraplength=1120,
        ).pack(anchor="w", fill=tk.X, pady=(0, 10))

        artifact_box = ttk.LabelFrame(
            outer,
            text="Artifact Paths",
            style="TLabelframe",
            padding=8,
        )
        artifact_box.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            artifact_box,
            textvariable=self._paths_var,
            font=FONT_MONO,
            bg=DARK["bg"],
            fg=DARK["fg"],
            justify="left",
            anchor="nw",
            wraplength=1100,
        ).pack(anchor="w", fill=tk.BOTH, expand=True)


class BaselineWorkbenchPanel(tk.Frame):
    """Baseline tab: nested notebook reusing the existing eval panels."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, bg=DARK["bg"])
        self._on_run_start_cb = None
        self._on_run_done_cb = None
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, style="TFrame", padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        intro = tk.Label(
            outer,
            text=(
                "Baseline QA reuses the existing production eval workflow. "
                "Launch, inspect results, compare two runs, and review history "
                "from the same shell."
            ),
            font=FONT,
            bg=DARK["bg"],
            fg=DARK["fg"],
            justify="left",
            anchor="w",
            wraplength=1120,
        )
        intro.pack(anchor="w", fill=tk.X, pady=(0, 8))

        self._notebook = ttk.Notebook(outer)
        self._notebook.pack(fill=tk.BOTH, expand=True)

        self._launch_panel = LaunchPanel(
            self._notebook,
            on_run_start=self._handle_run_start,
            on_run_done=self._handle_run_done,
        )
        self._results_panel = ResultsPanel(self._notebook)
        self._compare_panel = ComparePanel(self._notebook)
        self._history_panel = HistoryPanel(self._notebook, docs_dir=V2_ROOT / "docs")

        self._notebook.add(self._launch_panel, text="Launch")
        self._notebook.add(self._results_panel, text="Results")
        self._notebook.add(self._compare_panel, text="Compare")
        self._notebook.add(self._history_panel, text="History")

    def set_run_callbacks(self, *, on_run_start=None, on_run_done=None) -> None:
        self._on_run_start_cb = on_run_start
        self._on_run_done_cb = on_run_done

    def _handle_run_start(self, payload: dict) -> None:
        if self._on_run_start_cb:
            self._on_run_start_cb(payload)

    def _handle_run_done(self, payload: dict) -> None:
        results_json = (
            (payload.get("artifact_paths") or {}).get("results_json")
            or payload.get("results_json")
            or ""
        )
        if results_json:
            results_path = Path(results_json)
            if results_path.exists():
                try:
                    self._results_panel.load_file(results_path)
                except Exception:
                    pass
        try:
            self._history_panel.refresh()
        except Exception:
            pass
        if self._on_run_done_cb:
            self._on_run_done_cb(payload)


class HistoryLedgerPanel(tk.Frame):
    """History tab plus benchmark ledger expectations."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, bg=DARK["bg"])
        self._ledger_var = tk.StringVar(value=self._ledger_text())
        self._build()

    def _ledger_text(self) -> str:
        ledger_rows = [
            ("Hardtail ledger (md)", LOCAL_ONLY_ROOT / "HARDTAIL_BENCHMARK_LEDGER_2026-04-15.md"),
            ("Hardtail ledger (json)", LOCAL_ONLY_ROOT / "HARDTAIL_BENCHMARK_LEDGER_2026-04-15.json"),
            ("Baseline pack manifest", LOCAL_ONLY_ROOT / "BASELINE_PACK_MANIFEST_2026-04-15.md"),
            ("Baseline scoring contract", LOCAL_ONLY_ROOT / "BASELINE_SCORING_CONTRACT_2026-04-15.md"),
        ]
        lines = [
            "Locked view remains acceptance-only and untouched in this shell:",
            f"  {LOCAL_ONLY_ROOT / 'eval' / 'hardtail_v1_views' / 'hardtail_v1_10_locked.jsonl'}",
            "",
        ]
        for label, path in ledger_rows:
            state = "ready" if path.exists() else "waiting"
            lines.append(f"{label}: [{state}] {path}")
        return "\n".join(lines)

    def _build(self) -> None:
        outer = ttk.Frame(self, style="TFrame", padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        ledger_frame = ttk.LabelFrame(outer, text="Ledger / Provenance", style="TLabelframe", padding=8)
        ledger_frame.pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            ledger_frame,
            textvariable=self._ledger_var,
            font=FONT_MONO,
            bg=DARK["bg"],
            fg=DARK["fg"],
            justify="left",
            anchor="w",
            wraplength=1100,
        ).pack(anchor="w", fill=tk.X)

        self._history_panel = HistoryPanel(outer, docs_dir=V2_ROOT / "docs")
        self._history_panel.pack(fill=tk.BOTH, expand=True)

    def refresh_history(self) -> None:
        try:
            self._history_panel.refresh()
        except Exception:
            pass


class QAWorkbench(tk.Tk):
    """Top-level QA Workbench shell."""

    def __init__(self) -> None:
        super().__init__()
        self.title("HybridRAG V2 -- QA Workbench")
        self.geometry("1320x900")
        self.minsize(800, 400)
        self.configure(bg=DARK["bg"])
        apply_ttk_styles(DARK)

        self._summary_var = tk.StringVar(value="No completed workbench run in this session.")
        self._provenance_var = tk.StringVar(value=self._default_provenance())
        self._header_status = tk.StringVar(value="Workbench ready")

        self._build_header()
        self._build_status_bar()
        self._build_scroll_area()
        self._build_summary_strip()
        self._build_tabs()
        self._wire_callbacks()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._drain_pump()

    def _default_provenance(self) -> str:
        return (
            f"Repo: {V2_ROOT}\n"
            f"Docs: {V2_ROOT / 'docs'}\n"
            f"Local-only: {LOCAL_ONLY_ROOT}\n"
            f"Python: {sys.executable}"
        )

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=DARK["header_bg"], height=48)
        header.pack(side=tk.TOP, fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header,
            text="HybridRAG V2 -- QA Workbench",
            font=FONT_TITLE,
            bg=DARK["header_bg"],
            fg=DARK["fg"],
            padx=16,
        ).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(
            header,
            textvariable=self._header_status,
            font=FONT,
            bg=DARK["header_bg"],
            fg=DARK["label_fg"],
            padx=16,
        ).pack(side=tk.RIGHT, fill=tk.Y)
        tk.Button(
            header,
            text="Info",
            command=self._open_user_guide,
            bg=DARK["accent"],
            fg=DARK["accent_fg"],
            font=FONT_BOLD,
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=4,
        ).pack(side=tk.RIGHT, padx=(0, 8), pady=8)

    def _open_user_guide(self) -> None:
        guide = V2_ROOT / "docs" / "QA_WORKBENCH_USER_GUIDE_V2.docx"
        if not guide.exists():
            from tkinter import messagebox
            messagebox.showwarning("Info", f"User guide not found:\n{guide}\n\nRun: python scripts/build_user_guides.py")
            return
        os.startfile(str(guide))

    def _build_scroll_area(self) -> None:
        """Create a vertically scrollable canvas between header and status bar."""
        self._scroll_canvas = tk.Canvas(
            self, bg=DARK["bg"], highlightthickness=0, borderwidth=0,
        )
        self._scrollbar = ttk.Scrollbar(
            self, orient=tk.VERTICAL, command=self._scroll_canvas.yview,
        )
        self._scroll_inner = tk.Frame(self._scroll_canvas, bg=DARK["bg"])

        self._scroll_inner.bind(
            "<Configure>",
            lambda _: self._scroll_canvas.configure(
                scrollregion=self._scroll_canvas.bbox("all"),
            ),
        )
        self._canvas_window = self._scroll_canvas.create_window(
            (0, 0), window=self._scroll_inner, anchor="nw",
        )
        self._scroll_canvas.configure(yscrollcommand=self._scrollbar.set)

        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._scroll_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Keep inner frame width in sync with canvas width
        self._scroll_canvas.bind(
            "<Configure>",
            lambda e: self._scroll_canvas.itemconfigure(
                self._canvas_window, width=e.width,
            ),
        )
        # Mousewheel scrolling anywhere in the window
        self.bind_all(
            "<MouseWheel>",
            lambda e: self._scroll_canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units",
            ),
        )

    def _build_summary_strip(self) -> None:
        strip = tk.Frame(self._scroll_inner, bg=DARK["bg"])
        strip.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(8, 0))

        summary_frame = tk.Frame(
            strip,
            bg=DARK["panel_bg"],
            highlightthickness=1,
            highlightbackground=DARK["border"],
        )
        summary_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        tk.Label(
            summary_frame,
            text="Run Summary",
            font=FONT_SMALL,
            bg=DARK["panel_bg"],
            fg=DARK["label_fg"],
        ).pack(anchor="w", padx=10, pady=(8, 0))
        tk.Label(
            summary_frame,
            textvariable=self._summary_var,
            font=FONT_MONO,
            bg=DARK["panel_bg"],
            fg=DARK["fg"],
            justify="left",
            anchor="w",
            wraplength=760,
        ).pack(anchor="w", fill=tk.X, padx=10, pady=(0, 8))

        provenance_frame = tk.Frame(
            strip,
            bg=DARK["panel_bg"],
            highlightthickness=1,
            highlightbackground=DARK["border"],
        )
        provenance_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
        tk.Label(
            provenance_frame,
            text="Provenance",
            font=FONT_SMALL,
            bg=DARK["panel_bg"],
            fg=DARK["label_fg"],
        ).pack(anchor="w", padx=10, pady=(8, 0))
        tk.Label(
            provenance_frame,
            textvariable=self._provenance_var,
            font=FONT_MONO,
            bg=DARK["panel_bg"],
            fg=DARK["fg"],
            justify="left",
            anchor="w",
            wraplength=420,
        ).pack(anchor="w", fill=tk.X, padx=10, pady=(0, 8))

    def _build_tabs(self) -> None:
        self._notebook = ttk.Notebook(self._scroll_inner)
        self._notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))

        self._overview_panel = OverviewPanel(self._notebook)
        self._baseline_panel = BaselineWorkbenchPanel(self._notebook)
        self._aggregation_panel = AggregationPanel(self._notebook)
        self._count_panel = CountPanel(self._notebook)
        self._ragas_panel = RagasPanel(self._notebook)
        self._regression_panel = RegressionPanel(self._notebook)
        self._history_ledger_panel = HistoryLedgerPanel(self._notebook)

        self._notebook.add(self._overview_panel, text="Overview")
        self._notebook.add(self._baseline_panel, text="Baseline")
        self._notebook.add(self._aggregation_panel, text="Aggregation")
        self._notebook.add(self._count_panel, text="Count")
        self._notebook.add(self._ragas_panel, text="RAGAS")
        self._notebook.add(self._regression_panel, text="Regression")
        self._notebook.add(self._history_ledger_panel, text="History / Ledger")

    def _wire_callbacks(self) -> None:
        self._baseline_panel.set_run_callbacks(
            on_run_start=self._on_run_start,
            on_run_done=self._on_run_done,
        )
        self._ragas_panel.set_run_callbacks(
            on_run_start=self._on_ragas_run_start,
            on_run_done=self._on_ragas_run_done,
        )

    def _build_status_bar(self) -> None:
        bar = tk.Frame(self, bg=DARK["panel_bg"], height=24)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)
        tk.Label(
            bar,
            text=f"Repo: {V2_ROOT}",
            font=FONT,
            bg=DARK["panel_bg"],
            fg=DARK["label_fg"],
            padx=10,
        ).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(
            bar,
            text=f"Python: {Path(sys.executable).name}  ({sys.executable})",
            font=FONT,
            bg=DARK["panel_bg"],
            fg=DARK["label_fg"],
            padx=10,
        ).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(
            bar,
            text=f"CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES', '0')}",
            font=FONT,
            bg=DARK["panel_bg"],
            fg=DARK["label_fg"],
            padx=10,
        ).pack(side=tk.RIGHT, fill=tk.Y)

    def _format_summary(self, payload: dict) -> str:
        status = payload.get("status") or "?"
        run_id = payload.get("run_id") or "?"
        stamp = payload.get("timestamp_utc") or "?"
        queries = payload.get("queries_pack_name") or Path(payload.get("queries_path") or "").name or "?"
        config = payload.get("config_name") or Path(payload.get("config_path") or "").name or "?"
        store = payload.get("store_path") or "?"
        provider = payload.get("provider") or "?"
        model = payload.get("model") or "?"
        router = payload.get("router_mode") or "?"
        score = payload.get("score_summary") or {}
        strongest = ", ".join(payload.get("strongest_areas") or []) or "n/a"
        weakest = ", ".join(payload.get("weakest_areas") or []) or "n/a"
        artifacts = payload.get("artifact_paths") or {}
        return (
            f"status: {status}    run_id: {run_id}    timestamp: {stamp}\n"
            f"queries: {queries}\n"
            f"config:  {config}\n"
            f"store:   {store}\n"
            f"router:  {router} ({provider} / {model})\n"
            f"score:   pass={score.get('pass_count', '?')}  partial={score.get('partial_count', '?')}  "
            f"miss={score.get('miss_count', '?')}  routing={score.get('routing_correct', '?')}\n"
            f"strongest: {strongest}\n"
            f"weakest:   {weakest}\n"
            f"results@:  {artifacts.get('results_json', payload.get('results_json', '?'))}\n"
            f"report@:   {artifacts.get('report_md', payload.get('report_md', '?'))}"
        )

    def _format_provenance(self, payload: dict) -> str:
        artifacts = payload.get("artifact_paths") or {}
        return (
            f"Repo: {V2_ROOT}\n"
            f"Docs: {V2_ROOT / 'docs'}\n"
            f"Queries: {payload.get('queries_pack_name') or Path(payload.get('queries_path') or '').name or '?'}\n"
            f"Config: {payload.get('config_name') or Path(payload.get('config_path') or '').name or '?'}\n"
            f"Store: {payload.get('store_path') or '?'}\n"
            f"Artifacts: {artifacts.get('results_json', payload.get('results_json', '?'))}"
        )

    def _format_ragas_summary(self, payload: dict) -> str:
        summary = payload.get("summary") or {}
        readiness = summary.get("readiness") or {}
        dependencies = summary.get("dependencies") or {}
        metrics = summary.get("metric_summaries") or []
        artifacts = payload.get("artifact_paths") or {}
        metric_text = "none"
        if metrics:
            metric_text = ", ".join(
                f"{item.get('name')} mean={item.get('mean')} n={item.get('count')}"
                for item in metrics
            )
        return (
            f"surface: RAGAS    status: {payload.get('status', '?')}    run_id: {payload.get('run_id', '?')}\n"
            f"queries: {payload.get('queries_pack_name') or Path(payload.get('queries_path') or '').name or '?'}\n"
            f"mode:    {'analysis-only' if payload.get('analysis_only') else 'execute'}    limit: {payload.get('limit') if payload.get('limit') is not None else 'all'}\n"
            f"ready:   {readiness.get('eligible_for_retrieval_metrics', 0)}/{readiness.get('total_queries', 0)} retrieval-eligible\n"
            f"phase2c: {readiness.get('fully_phase2c_enriched', 0)}/{readiness.get('total_queries', 0)}\n"
            f"deps:    ragas={'yes' if dependencies.get('ragas_installed') else 'no'}  rapidfuzz={'yes' if dependencies.get('rapidfuzz_installed') else 'no'}\n"
            f"metrics: {metric_text}\n"
            f"proof:   {payload.get('proof_text') or summary.get('proof_text') or '-'}\n"
            f"json@:   {artifacts.get('output_json', '?')}"
        )

    def _format_ragas_provenance(self, payload: dict) -> str:
        artifacts = payload.get("artifact_paths") or {}
        return (
            f"Repo: {V2_ROOT}\n"
            f"Docs: {V2_ROOT / 'docs'}\n"
            f"Queries: {payload.get('queries_pack_name') or Path(payload.get('queries_path') or '').name or '?'}\n"
            f"Mode: {'analysis-only' if payload.get('analysis_only') else 'execute'}\n"
            f"Artifacts: {artifacts.get('output_json', '?')}"
        )

    def _on_run_start(self, payload: dict) -> None:
        queries_name = Path(payload.get("queries_path") or "").name or "?"
        config_name = Path(payload.get("config_path") or "").name or "?"
        self._header_status.set(f"Running baseline: {queries_name} / {config_name}")

    def _on_run_done(self, payload: dict) -> None:
        self._header_status.set(f"Last baseline run: {payload.get('status', '?')} ({payload.get('run_id', '?')})")
        self._summary_var.set(self._format_summary(payload))
        self._provenance_var.set(self._format_provenance(payload))
        self._refresh_readonly_views()

    def _on_ragas_run_start(self, payload: dict) -> None:
        queries_name = Path(payload.get("queries_path") or "").name or "?"
        mode = "analysis-only" if payload.get("analysis_only") else "execute"
        self._header_status.set(f"Running RAGAS: {queries_name} / {mode}")

    def _on_ragas_run_done(self, payload: dict) -> None:
        self._header_status.set(f"Last RAGAS run: {payload.get('status', '?')} ({payload.get('run_id', '?')})")
        self._summary_var.set(self._format_ragas_summary(payload))
        self._provenance_var.set(self._format_ragas_provenance(payload))
        self._refresh_readonly_views()

    def _refresh_readonly_views(self) -> None:
        try:
            self._history_ledger_panel.refresh_history()
        except Exception:
            pass
        try:
            self._overview_panel.refresh()
        except Exception:
            pass

    def _drain_pump(self) -> None:
        try:
            drain_ui_queue()
        except Exception:
            pass
        self.after(50, self._drain_pump)

    def _on_close(self) -> None:
        launch = getattr(self._baseline_panel, "_launch_panel", None)
        try:
            if launch and getattr(launch, "_runner", None) and launch._runner.is_alive:
                launch._runner.stop()
        except Exception:
            pass
        self.destroy()


def main() -> int:
    """Parse command-line inputs and run the main qa workbench workflow."""
    app = QAWorkbench()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
