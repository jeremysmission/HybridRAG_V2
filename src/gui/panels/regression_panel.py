"""Regression panel. It exposes quick checks used to catch known failures before a demo or release."""
# ============================================================================
# HybridRAG V2 -- Regression Panel (src/gui/panels/regression_panel.py)
# ============================================================================
# QA Workbench panel that exposes the schema-pattern regression fixture
# surface to operators and management:
#   - Loads the frozen 2026-04-15 fixture (or any fixture path)
#   - Runs src.regression.schema_pattern.harness against it
#   - Shows overall pass rate, per-family rollups, and per-case failures
#
# Mount-ready: drop into the panel registry (src/gui/panels/panel_registry.py)
# under the "regression" key, no other wiring required. Read-only and safe to
# run inside a live eval session.
# ============================================================================

from __future__ import annotations

import logging
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from src.gui.theme import current_theme, FONT, FONT_BOLD, FONT_MONO, FONT_SMALL
from src.gui.helpers.safe_after import safe_after
from src.regression.schema_pattern import (
    DEFAULT_FIXTURE_PATH,
    Report,
    load_fixture,
    run_fixture,
)

logger = logging.getLogger(__name__)


class RegressionPanel(tk.LabelFrame):
    """Schema-pattern regression panel.

    Sections:
      1. Fixture path + Run button
      2. Overall summary (total / passed / failed / pass rate)
      3. Per-family table (family, passed/total, pass rate)
      4. Failures detail (case_id, expected, actual, why)
    """

    def __init__(self, parent, model=None):
        t = current_theme()
        super().__init__(
            parent,
            text="Regression -- Schema Patterns",
            padx=16, pady=16,
            bg=t["panel_bg"], fg=t["accent"], font=FONT_BOLD,
        )
        self._model = model
        self._fixture_path_var = tk.StringVar(value=str(DEFAULT_FIXTURE_PATH))
        self._last_report: Report | None = None
        self._build_widgets(t)
        # Auto-load fixture metadata so operators see something on first paint.
        self.after(300, self._refresh_fixture_meta)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_widgets(self, t):
        # -- Section 1: fixture row --
        row = tk.Frame(self, bg=t["panel_bg"])
        row.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            row, text="Fixture:", bg=t["panel_bg"], fg=t["fg"], font=FONT,
        ).pack(side=tk.LEFT)

        self._path_entry = tk.Entry(
            row, textvariable=self._fixture_path_var,
            font=FONT_SMALL, bg=t["input_bg"], fg=t["input_fg"],
            insertbackground=t["fg"], relief=tk.FLAT, bd=2,
        )
        self._path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8), ipady=2)

        self._browse_btn = tk.Button(
            row, text="Browse", command=self._on_browse,
            bg=t["input_bg"], fg=t["fg"], font=FONT,
            relief=tk.FLAT, bd=0, padx=10, pady=4,
        )
        self._browse_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._run_btn = tk.Button(
            row, text="Run Regression", command=self._on_run,
            bg=t["accent"], fg=t["accent_fg"], font=FONT_BOLD,
            relief=tk.FLAT, bd=0, padx=14, pady=4,
        )
        self._run_btn.pack(side=tk.LEFT)

        # -- Section 2: summary --
        tk.Label(
            self, text="Summary", bg=t["panel_bg"], fg=t["fg"],
            font=FONT_BOLD, anchor=tk.W,
        ).pack(fill=tk.X, pady=(4, 2))

        self._summary_text = tk.Text(
            self, height=5, wrap=tk.WORD, state=tk.DISABLED,
            font=FONT_MONO, bg=t["input_bg"], fg=t["input_fg"],
            relief=tk.FLAT, bd=1,
        )
        self._summary_text.pack(fill=tk.X, pady=(0, 10))

        # -- Section 3: per-family table --
        tk.Label(
            self, text="By Family", bg=t["panel_bg"], fg=t["fg"],
            font=FONT_BOLD, anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 2))

        family_frame = tk.Frame(self, bg=t["panel_bg"])
        family_frame.pack(fill=tk.X, pady=(0, 10))

        cols = ("family", "passed", "total", "rate")
        self._family_tree = ttk.Treeview(
            family_frame, columns=cols, show="headings", height=6,
        )
        self._family_tree.heading("family", text="Family")
        self._family_tree.heading("passed", text="Passed")
        self._family_tree.heading("total", text="Total")
        self._family_tree.heading("rate", text="Pass %")
        self._family_tree.column("family", width=320, anchor=tk.W)
        self._family_tree.column("passed", width=70, anchor=tk.E)
        self._family_tree.column("total", width=70, anchor=tk.E)
        self._family_tree.column("rate", width=80, anchor=tk.E)
        self._family_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)

        fam_scroll = ttk.Scrollbar(
            family_frame, orient="vertical", command=self._family_tree.yview,
        )
        fam_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._family_tree.configure(yscrollcommand=fam_scroll.set)

        # -- Section 4: failures detail --
        tk.Label(
            self, text="Failures", bg=t["panel_bg"], fg=t["fg"],
            font=FONT_BOLD, anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 2))

        self._fail_text = tk.Text(
            self, height=10, wrap=tk.NONE, state=tk.DISABLED,
            font=FONT_MONO, bg=t["input_bg"], fg=t["input_fg"],
            relief=tk.FLAT, bd=1,
        )
        self._fail_text.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_browse(self):
        start = self._fixture_path_var.get() or str(DEFAULT_FIXTURE_PATH)
        start_dir = str(Path(start).parent) if Path(start).exists() else "."
        path = filedialog.askopenfilename(
            title="Select regression fixture",
            initialdir=start_dir,
            filetypes=[("JSON fixture", "*.json"), ("All files", "*.*")],
        )
        if path:
            self._fixture_path_var.set(path)
            self._refresh_fixture_meta()

    def _on_run(self):
        path = self._fixture_path_var.get().strip() or str(DEFAULT_FIXTURE_PATH)
        self._run_btn.config(state=tk.DISABLED, text="Running...")
        self._set_text(self._fail_text, "")
        for iid in self._family_tree.get_children():
            self._family_tree.delete(iid)
        self._set_text(self._summary_text, "Running regression...")

        def _worker():
            try:
                report = run_fixture(fixture_path=path)
                safe_after(self, 0, lambda: self._apply_report(report))
            except Exception as exc:
                logger.exception("regression run failed")
                safe_after(self, 0, lambda: self._apply_error(str(exc)))

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Result rendering
    # ------------------------------------------------------------------

    def _refresh_fixture_meta(self):
        path = self._fixture_path_var.get().strip() or str(DEFAULT_FIXTURE_PATH)
        try:
            fixture = load_fixture(path)
            cases = fixture.get("cases", [])
            text = (
                "Fixture loaded: {fid}\n"
                "Path: {path}\n"
                "Cases: {n} (across {f} families)\n"
                "Frozen at: {d}\n"
                "Click 'Run Regression' to execute."
            ).format(
                fid=fixture.get("fixture_id", "?"),
                path=path,
                n=len(cases),
                f=len(fixture.get("families", [])),
                d=fixture.get("frozen_at", "?"),
            )
            self._set_text(self._summary_text, text)
        except Exception as exc:
            self._set_text(
                self._summary_text,
                "Failed to load fixture: {}".format(exc),
            )

    def _apply_report(self, report: Report):
        self._last_report = report
        self._run_btn.config(state=tk.NORMAL, text="Run Regression")

        verdict_word = "PASS" if report.failed == 0 else "FAIL"
        summary = (
            "Result: {verdict}\n"
            "Fixture: {fid}\n"
            "Cases:   {p}/{t} passed ({r:.1%})\n"
            "Failed:  {f}"
        ).format(
            verdict=verdict_word,
            fid=report.fixture_id,
            p=report.passed, t=report.total, r=report.pass_rate,
            f=report.failed,
        )
        self._set_text(self._summary_text, summary)

        for iid in self._family_tree.get_children():
            self._family_tree.delete(iid)
        for f in report.families:
            self._family_tree.insert(
                "", tk.END,
                values=(f.family, f.passed, f.total, "{:.1%}".format(f.pass_rate)),
            )

        fails = [v for v in report.verdicts if not v.passed]
        if not fails:
            self._set_text(self._fail_text, "(no failures)")
            return

        lines = [
            "{:<35s} {:<8s} {:<22s} {:<10s} {:<10s}  {}".format(
                "case_id", "type", "text", "expected", "actual", "rule",
            ),
            "-" * 110,
        ]
        for v in fails:
            lines.append(
                "{:<35s} {:<8s} {:<22s} {:<10s} {:<10s}  {}".format(
                    v.case_id[:35],
                    v.entity_type[:8],
                    repr(v.text)[:22],
                    v.expected,
                    v.actual,
                    v.rule,
                )
            )
        self._set_text(self._fail_text, "\n".join(lines))

    def _apply_error(self, msg: str):
        self._run_btn.config(state=tk.NORMAL, text="Run Regression")
        self._set_text(self._summary_text, "Run failed: {}".format(msg))
        self._set_text(self._fail_text, "")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _set_text(widget: tk.Text, text: str):
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.config(state=tk.DISABLED)

    def apply_theme(self, t):
        self.configure(bg=t["panel_bg"], fg=t["accent"])
        for child in self.winfo_children():
            try:
                if isinstance(child, (tk.Frame, tk.Label)):
                    child.configure(bg=t["panel_bg"])
                elif isinstance(child, tk.Text):
                    child.configure(bg=t["input_bg"], fg=t["input_fg"])
            except Exception:
                pass
