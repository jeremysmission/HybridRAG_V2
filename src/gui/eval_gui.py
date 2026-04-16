"""HybridRAG V2 Eval GUI -- canonical module entry point.

Desktop app for the 400-query production golden eval workflow: launch a
run, browse results, compare two runs, and see the run history timeline.
Shares theme, safe_after, and scrollable helpers with the main V2 GUI.

Launch (matches start_gui.bat pattern exactly):

    .venv\\Scripts\\python.exe -m src.gui.eval_gui

or double-click ``start_eval_gui.bat``. The ``scripts/eval_gui.py`` shim
also forwards here for backward compat with direct-script invocation.
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

V2_ROOT = Path(__file__).resolve().parents[2]
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))


def _sanitize_tk_env() -> None:
    """Auto-heal common Tk startup failures caused by bad environment vars.

    Ported from ``src/gui/launch_gui.py``. Windows workstations occasionally
    inherit stale ``TCL_LIBRARY`` / ``TK_LIBRARY`` / ``PYTHONHOME`` env vars
    from a prior Python install that was removed or upgraded. When those
    point at directories that no longer exist, Tkinter can silently fall
    back to a system Python Tcl bootstrap which in turn spawns the GUI
    window under the wrong interpreter. Clearing the stale vars and
    re-resolving them from ``sys.base_prefix/tcl/`` keeps the GUI pinned
    to the launching interpreter.
    """
    from glob import glob

    for var, must_have in (
        ("TCL_LIBRARY", "init.tcl"),
        ("TK_LIBRARY", "tk.tcl"),
    ):
        val = os.environ.get(var)
        if not val:
            continue
        marker = os.path.join(val, must_have)
        if not (os.path.isdir(val) and os.path.isfile(marker)):
            os.environ.pop(var, None)

    pyhome = os.environ.get("PYTHONHOME")
    if pyhome and not os.path.isdir(pyhome):
        os.environ.pop("PYTHONHOME", None)

    tcl_root = os.path.join(sys.base_prefix, "tcl")
    if os.path.isdir(tcl_root):
        if not os.environ.get("TCL_LIBRARY"):
            for d in sorted(glob(os.path.join(tcl_root, "tcl*"))):
                if os.path.isfile(os.path.join(d, "init.tcl")):
                    os.environ["TCL_LIBRARY"] = d
                    break
        if not os.environ.get("TK_LIBRARY"):
            for d in sorted(glob(os.path.join(tcl_root, "tk*"))):
                if os.path.isfile(os.path.join(d, "tk.tcl")):
                    os.environ["TK_LIBRARY"] = d
                    break


_sanitize_tk_env()


from src.gui.theme import (  # noqa: E402
    DARK,
    FONT,
    FONT_BOLD,
    FONT_TITLE,
    apply_ttk_styles,
)
from src.gui.helpers.safe_after import drain_ui_queue  # noqa: E402
from src.gui.eval_panels.aggregation_panel import AggregationPanel  # noqa: E402
from src.gui.eval_panels.count_panel import CountPanel  # noqa: E402
from src.gui.eval_panels.launch_panel import LaunchPanel  # noqa: E402
from src.gui.eval_panels.ragas_panel import RagasPanel  # noqa: E402
from src.gui.eval_panels.results_panel import ResultsPanel  # noqa: E402
from src.gui.eval_panels.compare_panel import ComparePanel  # noqa: E402
from src.gui.eval_panels.history_panel import HistoryPanel  # noqa: E402
from src.gui.eval_panels.overview_panel import OverviewPanel  # noqa: E402


TABS = [
    ("Overview", OverviewPanel),
    ("Launch", LaunchPanel),
    ("Aggregation", AggregationPanel),
    ("Count", CountPanel),
    ("RAGAS", RagasPanel),
    ("Results", ResultsPanel),
    ("Compare", ComparePanel),
    ("History", HistoryPanel),
]


class EvalGUI(tk.Tk):
    """Top-level window for the eval GUI."""

    def __init__(self):
        super().__init__()
        self.title("HybridRAG V2 -- Eval GUI")
        self.geometry("1200x840")
        self.minsize(800, 400)
        self.configure(bg=DARK["bg"])
        apply_ttk_styles(DARK)

        self._build_header()
        self._build_status_bar()
        self._build_scroll_area()
        self._build_tabs()
        self._wire_panel_callbacks()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._drain_pump()

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=DARK["header_bg"], height=48)
        header.pack(side=tk.TOP, fill=tk.X)
        header.pack_propagate(False)
        title = tk.Label(
            header,
            text="HybridRAG V2 -- Production Eval",
            font=FONT_TITLE,
            bg=DARK["header_bg"],
            fg=DARK["fg"],
            padx=16,
        )
        title.pack(side=tk.LEFT, fill=tk.Y)
        self._header_status = tk.Label(
            header,
            text="",
            font=FONT,
            bg=DARK["header_bg"],
            fg=DARK["label_fg"],
            padx=16,
        )
        self._header_status.pack(side=tk.RIGHT, fill=tk.Y)
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
        guide = V2_ROOT / "docs" / "EVAL_GUI_USER_GUIDE.docx"
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

        self._scroll_canvas.bind(
            "<Configure>",
            lambda e: self._scroll_canvas.itemconfigure(
                self._canvas_window, width=e.width,
            ),
        )
        self.bind_all(
            "<MouseWheel>",
            lambda e: self._scroll_canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units",
            ),
        )

    def _build_tabs(self) -> None:
        self._notebook = ttk.Notebook(self._scroll_inner)
        self._notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(6, 0))
        self._panels = {}
        for label, cls in TABS:
            panel = cls(self._notebook)
            self._notebook.add(panel, text=label)
            self._panels[label] = panel

    def _wire_panel_callbacks(self) -> None:
        launch = self._panels.get("Launch")
        if launch and hasattr(launch, "set_run_callbacks"):
            launch.set_run_callbacks(
                on_run_start=self._on_launch_run_start,
                on_run_done=self._on_launch_run_done,
            )
        ragas = self._panels.get("RAGAS")
        if ragas and hasattr(ragas, "set_run_callbacks"):
            ragas.set_run_callbacks(
                on_run_start=self._on_ragas_run_start,
                on_run_done=self._on_ragas_run_done,
            )

    def _build_status_bar(self) -> None:
        bar = tk.Frame(self, bg=DARK["panel_bg"], height=24)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)
        self._status_label = tk.Label(
            bar,
            text=f"Repo: {V2_ROOT}",
            font=FONT,
            bg=DARK["panel_bg"],
            fg=DARK["label_fg"],
            padx=10,
        )
        self._status_label.pack(side=tk.LEFT, fill=tk.Y)
        interp_lbl = tk.Label(
            bar,
            text=f"Python: {Path(sys.executable).name}  ({sys.executable})",
            font=FONT,
            bg=DARK["panel_bg"],
            fg=DARK["label_fg"],
            padx=10,
        )
        interp_lbl.pack(side=tk.LEFT, fill=tk.Y)
        gpu_env = os.environ.get("CUDA_VISIBLE_DEVICES", "0")
        gpu_lbl = tk.Label(
            bar,
            text=f"CUDA_VISIBLE_DEVICES={gpu_env}",
            font=FONT,
            bg=DARK["panel_bg"],
            fg=DARK["label_fg"],
            padx=10,
        )
        gpu_lbl.pack(side=tk.RIGHT, fill=tk.Y)

    def _drain_pump(self) -> None:
        try:
            drain_ui_queue()
        except Exception:
            pass
        self.after(50, self._drain_pump)

    def _on_launch_run_start(self, payload: dict) -> None:
        queries_name = Path(payload.get("queries_path") or "").name or "?"
        config_name = Path(payload.get("config_path") or "").name or "?"
        self._header_status.configure(text=f"Running: {queries_name} / {config_name}")

    def _on_launch_run_done(self, payload: dict) -> None:
        status = payload.get("status") or "?"
        run_id = payload.get("run_id") or "?"
        self._header_status.configure(text=f"Last run: {status} ({run_id})")

        results_json = (
            (payload.get("artifact_paths") or {}).get("results_json")
            or payload.get("results_json")
            or ""
        )
        if results_json:
            results_panel = self._panels.get("Results")
            try:
                results_path = Path(results_json)
                if results_panel and results_path.exists():
                    results_panel.load_file(results_path)
            except Exception:
                pass

        history_panel = self._panels.get("History")
        try:
            if history_panel:
                history_panel.refresh()
        except Exception:
            pass

    def _on_ragas_run_start(self, payload: dict) -> None:
        queries_name = Path(payload.get("queries_path") or "").name or "?"
        mode = "analysis-only" if payload.get("analysis_only") else "execute"
        self._header_status.configure(text=f"Running RAGAS: {queries_name} / {mode}")

    def _on_ragas_run_done(self, payload: dict) -> None:
        status = payload.get("status") or "?"
        run_id = payload.get("run_id") or "?"
        self._header_status.configure(text=f"Last RAGAS: {status} ({run_id})")

    def _on_close(self) -> None:
        launch = self._panels.get("Launch")
        try:
            if launch and getattr(launch, "_runner", None) and launch._runner.is_alive:
                launch._runner.stop()
        except Exception:
            pass
        self.destroy()


def main() -> int:
    """Parse command-line inputs and run the main eval gui workflow."""
    app = EvalGUI()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
