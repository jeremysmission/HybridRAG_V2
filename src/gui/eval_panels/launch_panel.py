"""Launch panel for the eval GUI.

Hosts file pickers for the query pack, config YAML, and output paths, a
Start / Stop pair, a live log window, a phase label, a progress bar, and
a scorecard that fills in on completion. All runner events flow through
safe_after so the worker thread never touches widgets directly.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from tkinter import StringVar, filedialog, messagebox
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

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

# Live operator defaults file. Not date-stamped because it is a runtime
# state file that gets rewritten on every 'Save as defaults' click. Kept
# at the repo root and gitignored so each checkout can have its own
# operator-preferred values without polluting the shared repo state.
DEFAULTS_FILE = V2_ROOT / ".eval_gui_defaults.json"

RunCallback = Callable[[dict], None]


class LaunchPanel(tk.Frame):
    """File pickers + Start/Stop + live stream for one eval run."""

    def __init__(
        self,
        parent,
        on_run_start: Optional[RunCallback] = None,
        on_run_done: Optional[RunCallback] = None,
    ):
        super().__init__(parent, bg=DARK["bg"])
        self._runner = EvalRunner(self._on_runner_event)
        self._on_run_start_cb = on_run_start
        self._on_run_done_cb = on_run_done

        saved = self._load_saved_defaults()
        self._defaults_source = "saved" if saved else "shipped"
        self._defaults_saved_at = saved.get("saved_at", "") if saved else ""

        self._var_queries = StringVar(
            value=saved.get("queries_path", str(DEFAULT_QUERIES)) if saved else str(DEFAULT_QUERIES)
        )
        self._var_config = StringVar(
            value=saved.get("config_path", str(DEFAULT_CONFIG)) if saved else str(DEFAULT_CONFIG)
        )
        # Output paths are deliberately NOT persisted in the defaults file --
        # they always refresh to a new timestamped filename on every panel
        # construction so day-2 runs write to a new artifact instead of
        # overwriting day-1's. Older saved defaults files from the buggy v1
        # may still contain 'report_md_template' / 'results_json_template'
        # keys; we ignore them on load and only re-generate on save.
        self._var_report_md = StringVar(value=self._default_report_md())
        self._var_results_json = StringVar(value=self._default_results_json())
        self._var_gpu = StringVar(value=saved.get("gpu_index", "0") if saved else "0")
        self._var_max_q = StringVar(value=saved.get("max_queries", "") if saved else "")
        self._var_phase = StringVar(value="idle")
        self._var_defaults_status = StringVar(value=self._defaults_status_text())
        self._var_last_run = StringVar(value="No completed run yet.")
        self._last_results_json: Optional[Path] = None
        self._last_report_md: Optional[Path] = None

        self._build()
        self._set_running(False)
        self._set_last_run_outputs()

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
        self._btn_clear.pack(side=tk.LEFT, padx=(0, 12))

        self._btn_save_defaults = ttk.Button(
            ctrl,
            text="Save as defaults",
            style="TButton",
            command=self._on_save_defaults,
        )
        self._btn_save_defaults.pack(side=tk.LEFT, padx=(0, 6))
        self._btn_reset_defaults = ttk.Button(
            ctrl,
            text="Reset defaults",
            style="Tertiary.TButton",
            command=self._on_reset_defaults,
        )
        self._btn_reset_defaults.pack(side=tk.LEFT)

        phase_label = ttk.Label(
            ctrl,
            textvariable=self._var_phase,
            font=FONT_BOLD,
            foreground=DARK["accent"],
            background=DARK["bg"],
        )
        phase_label.pack(side=tk.RIGHT)

        # Defaults-source indicator (tiny status line under the button row so
        # the operator can see whether shipped or personal defaults are loaded).
        defaults_status = ttk.Label(
            outer,
            textvariable=self._var_defaults_status,
            font=FONT_SMALL,
            foreground=DARK["label_fg"],
            background=DARK["bg"],
        )
        defaults_status.pack(anchor="w", pady=(0, 4))

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

        # Last-run summary keeps the unattended flow usable without forcing the
        # operator to scroll the live log or switch tabs after completion.
        summary_frame = ttk.LabelFrame(outer, text="Last Completed Run", style="TLabelframe", padding=8)
        summary_frame.pack(fill=tk.X, pady=(0, 8))

        self._last_run_label = tk.Label(
            summary_frame,
            textvariable=self._var_last_run,
            font=FONT_MONO,
            justify="left",
            anchor="w",
            wraplength=1100,
            bg=DARK["bg"],
            fg=DARK["fg"],
        )
        self._last_run_label.pack(anchor="w", fill=tk.X)

        summary_btns = ttk.Frame(summary_frame, style="TFrame")
        summary_btns.pack(fill=tk.X, pady=(8, 0))
        self._btn_open_results = ttk.Button(
            summary_btns,
            text="Open results JSON",
            style="TButton",
            command=self._open_last_results_json,
        )
        self._btn_open_results.pack(side=tk.LEFT, padx=(0, 6))
        self._btn_open_report = ttk.Button(
            summary_btns,
            text="Open report MD",
            style="TButton",
            command=self._open_last_report_md,
        )
        self._btn_open_report.pack(side=tk.LEFT)

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

    # ------------------------------------------------------------------
    # Persisted operator defaults
    # ------------------------------------------------------------------
    def _load_saved_defaults(self) -> dict:
        """Read the persisted operator-defaults file if it exists.

        Returns an empty dict if the file is missing, unreadable, or the
        schema does not match. Never raises -- a broken defaults file must
        not prevent the GUI from launching.
        """
        try:
            if not DEFAULTS_FILE.exists():
                return {}
            with DEFAULTS_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
        except Exception:
            return {}

    def _on_save_defaults(self) -> None:
        """Persist the current input-field values so next launch loads them.

        Output paths (Report MD / Results JSON) are deliberately NOT saved --
        they always refresh to a fresh timestamp on each panel construction
        so repeated runs write to distinct artifacts. Persisting literal
        timestamped paths would force every day-2 run to immediately hit
        the overwrite confirmation, which defeats the whole 'just press
        Start' flow this feature is supposed to enable.
        """
        payload = {
            "queries_path": (self._var_queries.get() or "").strip(),
            "config_path": (self._var_config.get() or "").strip(),
            "gpu_index": (self._var_gpu.get() or "0").strip() or "0",
            "max_queries": (self._var_max_q.get() or "").strip(),
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "schema_version": 2,
        }
        try:
            DEFAULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with DEFAULTS_FILE.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as exc:
            messagebox.showerror(
                "Save defaults",
                f"Could not write {DEFAULTS_FILE}:\n{exc}",
            )
            return

        self._defaults_source = "saved"
        self._defaults_saved_at = payload["saved_at"]
        self._var_defaults_status.set(self._defaults_status_text())
        self._append_log(
            f"Operator defaults saved to {DEFAULTS_FILE.name}",
            "OK",
        )

    def _on_reset_defaults(self) -> None:
        """Restore shipped defaults and delete any persisted file."""
        confirm = messagebox.askyesno(
            "Reset defaults?",
            (
                "This will restore the shipped default query pack, config, "
                "output templates, GPU index, and max-queries values, and "
                "delete the saved defaults file if present.\n\n"
                "Proceed?"
            ),
            default="no",
        )
        if not confirm:
            return

        try:
            if DEFAULTS_FILE.exists():
                DEFAULTS_FILE.unlink()
        except Exception as exc:
            messagebox.showerror(
                "Reset defaults",
                f"Could not delete {DEFAULTS_FILE}:\n{exc}",
            )
            return

        self._var_queries.set(str(DEFAULT_QUERIES))
        self._var_config.set(str(DEFAULT_CONFIG))
        self._var_report_md.set(self._default_report_md())
        self._var_results_json.set(self._default_results_json())
        self._var_gpu.set("0")
        self._var_max_q.set("")
        self._defaults_source = "shipped"
        self._defaults_saved_at = ""
        self._var_defaults_status.set(self._defaults_status_text())
        self._append_log("Operator defaults reset to shipped values.", "WARN")

    def _defaults_status_text(self) -> str:
        if self._defaults_source == "saved" and self._defaults_saved_at:
            return f"Defaults: saved on {self._defaults_saved_at}  ({DEFAULTS_FILE.name})"
        return "Defaults: shipped (no saved file)"

    def _default_report_md(self) -> str:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return str(DEFAULT_DOCS / f"PRODUCTION_EVAL_RESULTS_GUI_{stamp}.md")

    def _default_results_json(self) -> str:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return str(DEFAULT_DOCS / f"production_eval_results_gui_{stamp}.json")

    def set_run_callbacks(
        self,
        *,
        on_run_start: Optional[RunCallback] = None,
        on_run_done: Optional[RunCallback] = None,
    ) -> None:
        self._on_run_start_cb = on_run_start
        self._on_run_done_cb = on_run_done

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
        self._emit_run_start(
            {
                "queries_path": str(queries_path),
                "config_path": str(config_path),
                "report_md": str(report_md),
                "results_json": str(results_json),
                "gpu_index": (self._var_gpu.get() or "0").strip() or "0",
                "max_queries": max_q,
            }
        )

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

    def _set_last_run_outputs(
        self,
        *,
        results_json: Optional[Path] = None,
        report_md: Optional[Path] = None,
    ) -> None:
        self._last_results_json = results_json
        self._last_report_md = report_md
        self._btn_open_results.configure(
            state="normal" if results_json and results_json.exists() else "disabled"
        )
        self._btn_open_report.configure(
            state="normal" if report_md and report_md.exists() else "disabled"
        )

    def _open_output_path(self, path: Optional[Path]) -> None:
        if path is None:
            return
        try:
            if sys.platform.startswith("win") and path.exists():
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                messagebox.showinfo("Eval output", str(path))
        except Exception as exc:
            messagebox.showerror("Eval output", f"Could not open {path}:\n{exc}")

    def _open_last_results_json(self) -> None:
        self._open_output_path(self._last_results_json)

    def _open_last_report_md(self) -> None:
        self._open_output_path(self._last_report_md)

    def _emit_run_start(self, payload: dict) -> None:
        if self._on_run_start_cb is None:
            return
        try:
            self._on_run_start_cb(payload)
        except Exception:
            pass

    def _emit_run_done(self, payload: dict) -> None:
        if self._on_run_done_cb is None:
            return
        try:
            self._on_run_done_cb(payload)
        except Exception:
            pass

    def _build_last_run_summary(self, payload: dict) -> str:
        run_id = payload.get("run_id") or "?"
        timestamp = payload.get("timestamp_utc") or "?"
        status = payload.get("status") or "?"
        pack_name = payload.get("queries_pack_name") or "?"
        config_name = payload.get("config_name") or "?"
        store_path = payload.get("store_path") or "?"
        router_mode = payload.get("router_mode") or ""
        provider = payload.get("provider") or ""
        model = payload.get("model") or ""
        strongest = payload.get("strongest_areas") or []
        weakest = payload.get("weakest_areas") or []
        score_summary = payload.get("score_summary") or {}
        latency = payload.get("latency_summary") or {}
        artifact_paths = payload.get("artifact_paths") or {}
        results_json = artifact_paths.get("results_json") or payload.get("results_json") or "?"
        report_md = artifact_paths.get("report_md") or payload.get("report_md") or "?"

        lines = [
            f"status:    {status}    run_id: {run_id}",
            f"time:      {timestamp}",
            f"queries:   {pack_name}",
            f"config:    {config_name}",
            f"store:     {store_path}",
        ]
        if router_mode or provider or model:
            provider_bits = " / ".join(bit for bit in (provider, model) if bit)
            if provider_bits:
                lines.append(f"router:    {router_mode or 'llm'} ({provider_bits})")
            else:
                lines.append(f"router:    {router_mode}")
        total = score_summary.get("total_queries")
        if total:
            lines.append(
                "score:     "
                f"PASS {score_summary.get('pass_count', 0)}/{total} "
                f"({_fmt_pct(score_summary.get('pass_rate_pct'))})    "
                f"PARTIAL {score_summary.get('partial_count', 0)}/{total}    "
                f"MISS {score_summary.get('miss_count', 0)}/{total}    "
                f"Routing {score_summary.get('routing_correct', 0)}/{total} "
                f"({_fmt_pct(score_summary.get('routing_rate_pct'))})"
            )
        if strongest:
            lines.append(f"strongest: {', '.join(strongest)}")
        if weakest:
            lines.append(f"weakest:   {', '.join(weakest)}")
        if latency:
            lines.append(
                "latency:   "
                f"retr {latency.get('p50_pure_retrieval_ms', '?')}/"
                f"{latency.get('p95_pure_retrieval_ms', '?')} ms    "
                f"wall {latency.get('p50_wall_clock_ms', '?')}/"
                f"{latency.get('p95_wall_clock_ms', '?')} ms    "
                f"router {latency.get('p50_router_ms', '?')}/"
                f"{latency.get('p95_router_ms', '?')} ms    "
                f"elapsed {payload.get('elapsed_s', latency.get('elapsed_s', '?'))}s"
            )
        lines.append(f"results@:  {results_json}")
        lines.append(f"report@:   {report_md}")
        err = payload.get("error")
        if err:
            lines.append(f"error:     {err}")
        return "\n".join(lines)

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
                strongest = payload.get("strongest_query_types") or []
                weakest = payload.get("weakest_query_types") or []
                if strongest:
                    self._append_log(f"Strongest areas: {', '.join(strongest)}", "OK")
                if weakest:
                    self._append_log(f"Weakest areas: {', '.join(weakest)}", "WARN")
            elif kind == "done":
                self._set_running(False)
                status = payload.get("status", "?")
                elapsed = payload.get("elapsed_s", 0)
                level = "OK" if status == "PASS" else ("WARN" if status == "STOPPED" else "ERROR")
                self._var_phase.set(f"done ({status})")
                self._append_log(f"Run finished: {status} in {elapsed}s", level)
                run_id = payload.get("run_id")
                timestamp = payload.get("timestamp_utc")
                if run_id or timestamp:
                    self._append_log(
                        f"  run: {run_id or '?'} @ {timestamp or '?'}",
                        "INFO",
                    )
                pack_name = payload.get("queries_pack_name")
                config_name = payload.get("config_name")
                store_path = payload.get("store_path")
                if pack_name:
                    self._append_log(f"  pack:   {pack_name}", "INFO")
                if config_name:
                    self._append_log(f"  config: {config_name}", "INFO")
                if store_path:
                    self._append_log(f"  store:  {store_path}", "INFO")

                router_mode = payload.get("router_mode") or ""
                provider = payload.get("provider") or ""
                model = payload.get("model") or ""
                if router_mode:
                    if provider or model:
                        provider_bits = " / ".join(bit for bit in (provider, model) if bit)
                        self._append_log(f"  router: {router_mode} ({provider_bits})", "INFO")
                    else:
                        self._append_log(f"  router: {router_mode}", "INFO")

                score_summary = payload.get("score_summary") or {}
                total = score_summary.get("total_queries")
                if total:
                    self._append_log(
                        "  score: "
                        f"PASS {score_summary.get('pass_count', 0)}/{total} "
                        f"({_fmt_pct(score_summary.get('pass_rate_pct'))})  "
                        f"PARTIAL {score_summary.get('partial_count', 0)}/{total}  "
                        f"MISS {score_summary.get('miss_count', 0)}/{total}  "
                        f"Routing {score_summary.get('routing_correct', 0)}/{total} "
                        f"({_fmt_pct(score_summary.get('routing_rate_pct'))})",
                        "INFO",
                    )
                strongest = payload.get("strongest_areas") or []
                weakest = payload.get("weakest_areas") or []
                if strongest:
                    self._append_log(f"  strongest: {', '.join(strongest)}", "OK")
                if weakest:
                    self._append_log(f"  weakest:   {', '.join(weakest)}", "WARN")

                latency = payload.get("latency_summary") or {}
                if latency:
                    self._append_log(
                        "  latency: "
                        f"retr {latency.get('p50_pure_retrieval_ms', '?')}/"
                        f"{latency.get('p95_pure_retrieval_ms', '?')} ms  "
                        f"wall {latency.get('p50_wall_clock_ms', '?')}/"
                        f"{latency.get('p95_wall_clock_ms', '?')} ms  "
                        f"router {latency.get('p50_router_ms', '?')}/"
                        f"{latency.get('p95_router_ms', '?')} ms",
                        "INFO",
                    )

                artifact_paths = payload.get("artifact_paths") or {}
                results_json = artifact_paths.get("results_json") or payload.get("results_json")
                report_md = artifact_paths.get("report_md") or payload.get("report_md")
                if results_json:
                    self._append_log(f"  results: {results_json}", "INFO")
                if report_md:
                    self._append_log(f"  report:  {report_md}", "INFO")
                err = payload.get("error")
                if err:
                    self._append_log(f"  error: {err}", "ERROR")
                self._var_last_run.set(self._build_last_run_summary(payload))
                self._set_last_run_outputs(
                    results_json=Path(results_json) if results_json else None,
                    report_md=Path(report_md) if report_md else None,
                )
                self._emit_run_done(payload)
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


def _fmt_pct(value) -> str:
    """Turn internal values into human-readable text for the operator."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "?"
    text = f"{numeric:.1f}"
    if text.endswith(".0"):
        text = text[:-2]
    return f"{text}%"
