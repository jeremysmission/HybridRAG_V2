"""Launch panel for the eval GUI.

Hosts file pickers for the query pack, config YAML, and output paths, a
Start / Stop pair, a live log window, a phase label, a progress bar, and
a scorecard that fills in on completion. All runner events flow through
safe_after so the worker thread never touches widgets directly.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from tkinter import StringVar, filedialog, messagebox
import tkinter as tk
from tkinter import ttk

from src.gui.theme import (
    DARK,
    FONT,
    FONT_BOLD,
    FONT_MONO,
    FONT_SECTION,
    FONT_SMALL,
    FONT_TITLE,
)
from src.gui.helpers.safe_after import safe_after

from .runner import EvalRunner


V2_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_QUERIES = V2_ROOT / "tests" / "golden_eval" / "production_queries_400_2026-04-12.json"
DEFAULT_CONFIG = V2_ROOT / "config" / "config.tier1_clean_2026-04-13.yaml"
DEFAULT_DOCS = V2_ROOT / "docs"


class LaunchPanel(tk.Frame):
    """File pickers + Start/Stop + live stream for one eval run."""

    def __init__(self, parent):
        super().__init__(parent, bg=DARK["bg"])
        self._runner = EvalRunner(self._on_runner_event)
        self._var_queries = StringVar(value=str(DEFAULT_QUERIES))
        self._var_config = StringVar(value=str(DEFAULT_CONFIG))
        self._var_report_md = StringVar(value=self._default_report_md())
        self._var_results_json = StringVar(value=self._default_results_json())
        self._var_gpu = StringVar(value="0")
        self._var_max_q = StringVar(value="")
        self._var_phase = StringVar(value="idle")

        self._build()
        self._set_running(False)

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------
    def _build(self) -> None:
        outer = ttk.Frame(self, style="TFrame", padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(
            outer,
            text="Production Eval Runner",
            font=FONT_TITLE,
            foreground=DARK["fg"],
            background=DARK["bg"],
        )
        title.pack(anchor="w", pady=(0, 10))

        form = ttk.LabelFrame(outer, text="Inputs", style="TLabelframe", padding=10)
        form.pack(fill=tk.X)

        self._row(form, "Query pack:", self._var_queries, self._pick_queries, 0)
        self._row(form, "Config YAML:", self._var_config, self._pick_config, 1)
        self._row(form, "Report MD:", self._var_report_md, self._pick_report_md, 2, save=True)
        self._row(form, "Results JSON:", self._var_results_json, self._pick_results_json, 3, save=True)

        gpu_row = ttk.Frame(form, style="TFrame")
        gpu_row.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(
            gpu_row,
            text="CUDA_VISIBLE_DEVICES:",
            font=FONT,
            foreground=DARK["label_fg"],
            background=DARK["bg"],
        ).pack(side=tk.LEFT, padx=(0, 6))
        gpu_entry = ttk.Entry(gpu_row, textvariable=self._var_gpu, width=4, font=FONT)
        gpu_entry.pack(side=tk.LEFT)

        ttk.Label(
            gpu_row,
            text="  Max queries (blank = all):",
            font=FONT,
            foreground=DARK["label_fg"],
            background=DARK["bg"],
        ).pack(side=tk.LEFT, padx=(12, 6))
        max_entry = ttk.Entry(gpu_row, textvariable=self._var_max_q, width=6, font=FONT)
        max_entry.pack(side=tk.LEFT)

        form.columnconfigure(1, weight=1)

        # Controls
        ctrl = ttk.Frame(outer, style="TFrame")
        ctrl.pack(fill=tk.X, pady=(12, 6))

        self._btn_start = ttk.Button(ctrl, text="Start", style="Accent.TButton", command=self._on_start)
        self._btn_start.pack(side=tk.LEFT, padx=(0, 6))
        self._btn_stop = ttk.Button(ctrl, text="Stop", style="Tertiary.TButton", command=self._on_stop)
        self._btn_stop.pack(side=tk.LEFT, padx=(0, 6))
        self._btn_clear = ttk.Button(ctrl, text="Clear log", style="Tertiary.TButton", command=self._clear_log)
        self._btn_clear.pack(side=tk.LEFT)

        phase_label = ttk.Label(
            ctrl,
            textvariable=self._var_phase,
            font=FONT_BOLD,
            foreground=DARK["accent"],
            background=DARK["bg"],
        )
        phase_label.pack(side=tk.RIGHT)

        # Progress bar
        self._progress = ttk.Progressbar(outer, orient="horizontal", mode="determinate", maximum=100)
        self._progress.pack(fill=tk.X, pady=(2, 6))
        self._progress_label = ttk.Label(
            outer,
            text="0 / 0",
            font=FONT_SMALL,
            foreground=DARK["label_fg"],
            background=DARK["bg"],
        )
        self._progress_label.pack(anchor="e", pady=(0, 6))

        # Scorecard strip
        score_frame = ttk.LabelFrame(outer, text="Scorecard", style="TLabelframe", padding=8)
        score_frame.pack(fill=tk.X, pady=(0, 8))
        self._score_labels = {}
        for idx, (key, label) in enumerate(
            [
                ("pass", "PASS"),
                ("partial", "PARTIAL"),
                ("miss", "MISS"),
                ("routing_correct", "Routing"),
                ("p50_pure_retrieval_ms", "p50 retr ms"),
                ("p95_pure_retrieval_ms", "p95 retr ms"),
                ("elapsed_s", "elapsed s"),
            ]
        ):
            col = idx * 2
            ttk.Label(
                score_frame,
                text=label,
                font=FONT_SMALL,
                foreground=DARK["label_fg"],
                background=DARK["bg"],
            ).grid(row=0, column=col, padx=4, sticky="w")
            value_lbl = ttk.Label(
                score_frame,
                text="-",
                font=FONT_BOLD,
                foreground=DARK["fg"],
                background=DARK["bg"],
            )
            value_lbl.grid(row=0, column=col + 1, padx=(0, 10), sticky="w")
            self._score_labels[key] = value_lbl

        # Log window
        log_frame = ttk.LabelFrame(outer, text="Live log", style="TLabelframe", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self._log = tk.Text(
            log_frame,
            height=14,
            wrap="none",
            font=FONT_MONO,
            bg=DARK["panel_bg"],
            fg=DARK["fg"],
            insertbackground=DARK["fg"],
            bd=0,
            padx=8,
            pady=6,
        )
        self._log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self._log.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._log.configure(yscrollcommand=log_scroll.set, state="disabled")

        self._log.tag_configure("INFO", foreground=DARK["fg"])
        self._log.tag_configure("WARN", foreground=DARK["orange"])
        self._log.tag_configure("ERROR", foreground=DARK["red"])
        self._log.tag_configure("OK", foreground=DARK["green"])

    def _row(self, parent, label, var, command, r, save=False):
        ttk.Label(
            parent,
            text=label,
            font=FONT,
            foreground=DARK["label_fg"],
            background=DARK["bg"],
        ).grid(row=r, column=0, sticky="w", padx=(0, 6), pady=2)
        entry = ttk.Entry(parent, textvariable=var, font=FONT)
        entry.grid(row=r, column=1, sticky="ew", pady=2)
        btn = ttk.Button(parent, text="Browse...", style="TButton", command=command)
        btn.grid(row=r, column=2, sticky="w", padx=(6, 0), pady=2)

    # ------------------------------------------------------------------
    # File pickers
    # ------------------------------------------------------------------
    def _pick_queries(self):
        path = filedialog.askopenfilename(
            initialdir=str(V2_ROOT / "tests" / "golden_eval"),
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
        )
        if path:
            self._var_queries.set(path)

    def _pick_config(self):
        path = filedialog.askopenfilename(
            initialdir=str(V2_ROOT / "config"),
            filetypes=[("YAML", "*.yaml *.yml"), ("All", "*.*")],
        )
        if path:
            self._var_config.set(path)

    def _pick_report_md(self):
        path = filedialog.asksaveasfilename(
            initialdir=str(DEFAULT_DOCS),
            initialfile=Path(self._var_report_md.get()).name,
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("All", "*.*")],
        )
        if path:
            self._var_report_md.set(path)

    def _pick_results_json(self):
        path = filedialog.asksaveasfilename(
            initialdir=str(DEFAULT_DOCS),
            initialfile=Path(self._var_results_json.get()).name,
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
        )
        if path:
            self._var_results_json.set(path)

    def _default_report_md(self) -> str:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return str(DEFAULT_DOCS / f"PRODUCTION_EVAL_RESULTS_GUI_{stamp}.md")

    def _default_results_json(self) -> str:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return str(DEFAULT_DOCS / f"production_eval_results_gui_{stamp}.json")

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------
    def _on_start(self):
        if self._runner.is_alive:
            messagebox.showwarning("Eval", "A run is already in progress.")
            return
        queries_path = Path(self._var_queries.get())
        config_path = Path(self._var_config.get())
        if not queries_path.exists():
            messagebox.showerror("Eval", f"Query pack not found:\n{queries_path}")
            return
        if not config_path.exists():
            messagebox.showerror("Eval", f"Config not found:\n{config_path}")
            return
        report_md = Path(self._var_report_md.get() or self._default_report_md())
        results_json = Path(self._var_results_json.get() or self._default_results_json())
        report_md.parent.mkdir(parents=True, exist_ok=True)
        results_json.parent.mkdir(parents=True, exist_ok=True)

        # Confirm overwrite of existing output files so an operator cannot
        # silently clobber a prior baseline when kicking off a fresh run.
        existing = [p for p in (results_json, report_md) if p.exists()]
        if existing:
            names = "\n  ".join(str(p) for p in existing)
            proceed = messagebox.askyesno(
                "Overwrite output files?",
                (
                    "The following output file(s) already exist and will be "
                    "overwritten by this run:\n\n  "
                    f"{names}\n\n"
                    "Proceed and overwrite?"
                ),
                default="no",
            )
            if not proceed:
                self._append_log("Run cancelled: operator declined overwrite.", "WARN")
                return

        max_q_raw = (self._var_max_q.get() or "").strip()
        max_q = int(max_q_raw) if max_q_raw.isdigit() and int(max_q_raw) > 0 else None

        self._reset_progress()
        self._reset_scorecard()
        self._clear_log()
        self._append_log(f"Starting run -- queries={queries_path.name} config={config_path.name}", "INFO")
        if max_q is not None:
            self._append_log(f"Limiting to first {max_q} queries (smoke mode).", "WARN")
        self._set_running(True)

        self._runner.start(
            queries_path=queries_path,
            config_path=config_path,
            report_md=report_md,
            results_json=results_json,
            gpu_index=(self._var_gpu.get() or "0").strip() or "0",
            max_queries=max_q,
        )

    def _on_stop(self):
        if not self._runner.is_alive:
            return
        self._runner.stop()

    def _set_running(self, running: bool) -> None:
        self._btn_start.configure(state="disabled" if running else "normal")
        self._btn_stop.configure(state="normal" if running else "disabled")

    def _reset_progress(self) -> None:
        self._progress.configure(value=0, maximum=100)
        self._progress_label.configure(text="0 / 0")

    def _reset_scorecard(self) -> None:
        for lbl in self._score_labels.values():
            lbl.configure(text="-", foreground=DARK["fg"])

    def _clear_log(self) -> None:
        self._log.configure(state="normal")
        self._log.delete("1.0", tk.END)
        self._log.configure(state="disabled")

    def _append_log(self, msg: str, level: str = "INFO") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log.configure(state="normal")
        self._log.insert(tk.END, f"[{timestamp}] {msg}\n", level)
        self._log.see(tk.END)
        self._log.configure(state="disabled")

    # ------------------------------------------------------------------
    # Runner callback (background thread -> safe_after -> main thread)
    # ------------------------------------------------------------------
    def _on_runner_event(self, kind: str, payload: dict) -> None:
        safe_after(self, 0, self._dispatch_event, kind, payload)

    def _dispatch_event(self, kind: str, payload: dict) -> None:
        try:
            if kind == "log":
                self._append_log(payload.get("msg", ""), payload.get("level", "INFO"))
            elif kind == "phase":
                phase = payload.get("phase", "?")
                self._var_phase.set(phase)
                self._append_log(f"Phase: {phase}", "INFO")
            elif kind == "progress":
                current = int(payload.get("current", 0))
                total = int(payload.get("total", 0)) or 1
                self._progress.configure(maximum=total, value=current)
                self._progress_label.configure(text=f"{current} / {total}")
            elif kind == "query":
                qid = payload.get("query_id", "?")
                verdict = payload.get("verdict", "?")
                persona = payload.get("persona", "?")
                level = "OK" if verdict == "PASS" else ("WARN" if verdict == "PARTIAL" else "ERROR")
                ms = payload.get("embed_retrieve_ms", 0)
                route_ok = "ok" if payload.get("routing_correct") else "miss"
                self._append_log(
                    f"  {qid:<8} [{persona[:14]:<14}] {verdict:<7} route={route_ok} {ms}ms",
                    level,
                )
            elif kind == "scorecard":
                self._fill_scorecard(payload)
            elif kind == "done":
                self._set_running(False)
                status = payload.get("status", "?")
                elapsed = payload.get("elapsed_s", 0)
                level = "OK" if status == "PASS" else ("WARN" if status == "STOPPED" else "ERROR")
                self._var_phase.set(f"done ({status})")
                self._append_log(f"Run finished: {status} in {elapsed}s", level)
                if status == "PASS":
                    results_json = payload.get("results_json")
                    report_md = payload.get("report_md")
                    self._append_log(f"  results: {results_json}", "INFO")
                    self._append_log(f"  report:  {report_md}", "INFO")
                err = payload.get("error")
                if err:
                    self._append_log(f"  error: {err}", "ERROR")
        except Exception as exc:
            self._append_log(f"dispatch error: {exc}", "ERROR")

    def _fill_scorecard(self, payload: dict) -> None:
        mapping = {
            "pass": (DARK["green"], payload.get("pass")),
            "partial": (DARK["orange"], payload.get("partial")),
            "miss": (DARK["red"], payload.get("miss")),
            "routing_correct": (DARK["accent"], payload.get("routing_correct")),
            "p50_pure_retrieval_ms": (DARK["fg"], payload.get("p50_pure_retrieval_ms")),
            "p95_pure_retrieval_ms": (DARK["fg"], payload.get("p95_pure_retrieval_ms")),
            "elapsed_s": (DARK["fg"], payload.get("elapsed_s")),
        }
        total = payload.get("total", 0)
        for key, (color, value) in mapping.items():
            lbl = self._score_labels.get(key)
            if lbl is None:
                continue
            if value is None:
                continue
            if key in ("pass", "partial", "miss", "routing_correct") and total:
                lbl.configure(text=f"{value}/{total}", foreground=color)
            else:
                lbl.configure(text=str(value), foreground=color)
