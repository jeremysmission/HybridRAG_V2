"""HybridRAG V2 Eval GUI entry point.

Desktop app for the 400-query production golden eval workflow: launch a
run, browse results, compare two runs, and see the run history timeline.
Shares the theme, safe_after helper, and scrollable frame utilities with
the main V2 GUI; no new dependencies beyond the existing stack.

Launch from the repo root with:

    .venv\\Scripts\\python.exe scripts/eval_gui.py

or by double-clicking ``start_eval_gui.bat``.
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

V2_ROOT = Path(__file__).resolve().parent.parent
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

from src.gui.theme import (  # noqa: E402
    DARK,
    FONT,
    FONT_BOLD,
    FONT_TITLE,
    apply_ttk_styles,
)
from src.gui.helpers.safe_after import drain_ui_queue  # noqa: E402
from src.gui.eval_panels.launch_panel import LaunchPanel  # noqa: E402
from src.gui.eval_panels.results_panel import ResultsPanel  # noqa: E402
from src.gui.eval_panels.compare_panel import ComparePanel  # noqa: E402
from src.gui.eval_panels.history_panel import HistoryPanel  # noqa: E402


TABS = [
    ("Launch", LaunchPanel),
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
        self.minsize(980, 640)
        self.configure(bg=DARK["bg"])
        apply_ttk_styles(DARK)

        self._build_header()
        self._build_tabs()
        self._build_status_bar()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._drain_pump()

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=DARK["panel_bg"], height=48)
        header.pack(side=tk.TOP, fill=tk.X)
        header.pack_propagate(False)
        title = tk.Label(
            header,
            text="HybridRAG V2 -- Production Eval",
            font=FONT_TITLE,
            bg=DARK["panel_bg"],
            fg=DARK["fg"],
            padx=16,
        )
        title.pack(side=tk.LEFT, fill=tk.Y)
        self._header_status = tk.Label(
            header,
            text="",
            font=FONT,
            bg=DARK["panel_bg"],
            fg=DARK["label_fg"],
            padx=16,
        )
        self._header_status.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_tabs(self) -> None:
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(6, 0))
        self._panels = {}
        for label, cls in TABS:
            panel = cls(self._notebook)
            self._notebook.add(panel, text=label)
            self._panels[label] = panel

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

    def _on_close(self) -> None:
        launch = self._panels.get("Launch")
        try:
            if launch and getattr(launch, "_runner", None) and launch._runner.is_alive:
                launch._runner.stop()
        except Exception:
            pass
        self.destroy()


def main() -> int:
    app = EvalGUI()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
