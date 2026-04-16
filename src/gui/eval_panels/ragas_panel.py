"""RAGAS readiness/eval panel for the eval GUI and QA Workbench."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from tkinter import BooleanVar, StringVar, filedialog, messagebox
import tkinter as tk
from tkinter import ttk

from src.gui.helpers.safe_after import safe_after
from src.gui.theme import DARK, FONT, FONT_BOLD, FONT_MONO, FONT_SMALL, FONT_TITLE

from .benchmark_runners import RagasEvalRunner

V2_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_QUERIES = V2_ROOT / "tests" / "golden_eval" / "production_queries_400_2026-04-12.json"
DEFAULT_OUTPUT_DIR = V2_ROOT / "docs"
DEFAULT_TOP_K = 5


class RagasPanel(tk.Frame):
    """Tkinter panel responsible for the Ragas area of the interface."""
    def __init__(self, parent, on_run_start=None, on_run_done=None):
        super().__init__(parent, bg=DARK["bg"])
        self._runner = RagasEvalRunner(self._on_runner_event)
        self._on_run_start_cb = on_run_start
        self._on_run_done_cb = on_run_done
        self._var_queries = StringVar(value=str(DEFAULT_QUERIES))
        self._var_limit = StringVar(value="")
        self._var_analysis_only = BooleanVar(value=True)
        self._var_phase = StringVar(value="idle")
        self._var_summary = StringVar(value="No RAGAS run yet.")
        self._var_artifact = StringVar(value="Artifact: -\nProof: -")
        self._last_output_json: Path | None = None
        self._build()
        self._set_running(False)
        self._set_output(None, "")

    def set_run_callbacks(self, *, on_run_start=None, on_run_done=None) -> None:
        self._on_run_start_cb = on_run_start
        self._on_run_done_cb = on_run_done

    def _build(self) -> None:
        outer = ttk.Frame(self, style="TFrame", padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text="RAGAS",
            font=FONT_TITLE,
            foreground=DARK["fg"],
            background=DARK["bg"],
        ).pack(anchor="w", pady=(0, 10))

        form = ttk.LabelFrame(outer, text="Inputs", style="TLabelframe", padding=10)
        form.pack(fill=tk.X)
        self._row(form, "Query JSON:", self._var_queries, self._pick_queries, 0)

        opt_row = ttk.Frame(form, style="TFrame")
        opt_row.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(
            opt_row,
            text="Limit:",
            font=FONT,
            foreground=DARK["label_fg"],
            background=DARK["bg"],
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Entry(opt_row, textvariable=self._var_limit, width=8, font=FONT).pack(side=tk.LEFT)
        ttk.Checkbutton(
            opt_row,
            text="Analysis only",
            variable=self._var_analysis_only,
            style="TCheckbutton",
        ).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Label(
            opt_row,
            text=f"Execution mode uses top-k={DEFAULT_TOP_K} and writes a proof JSON under {DEFAULT_OUTPUT_DIR}.",
            font=FONT_SMALL,
            foreground=DARK["label_fg"],
            background=DARK["bg"],
        ).pack(side=tk.LEFT, padx=(12, 0))
        form.columnconfigure(1, weight=1)

        ctrl = ttk.Frame(outer, style="TFrame")
        ctrl.pack(fill=tk.X, pady=(12, 6))
        self._btn_start = ttk.Button(ctrl, text="Start", style="Accent.TButton", command=self._on_start)
        self._btn_start.pack(side=tk.LEFT, padx=(0, 6))
        self._btn_clear = ttk.Button(ctrl, text="Clear log", style="Tertiary.TButton", command=self._clear_log)
        self._btn_clear.pack(side=tk.LEFT, padx=(0, 6))
        self._btn_open = ttk.Button(ctrl, text="Open artifact", style="TButton", command=self._open_output)
        self._btn_open.pack(side=tk.LEFT)
        ttk.Label(
            ctrl,
            textvariable=self._var_phase,
            font=FONT_BOLD,
            foreground=DARK["accent"],
            background=DARK["bg"],
        ).pack(side=tk.RIGHT)

        self._progress = ttk.Progressbar(outer, orient="horizontal", mode="determinate", maximum=100)
        self._progress.pack(fill=tk.X, pady=(2, 4))
        self._progress_label = ttk.Label(
            outer,
            text="0 / 0",
            font=FONT_SMALL,
            foreground=DARK["label_fg"],
            background=DARK["bg"],
        )
        self._progress_label.pack(anchor="e", pady=(0, 8))

        summary_frame = ttk.LabelFrame(outer, text="Summary", style="TLabelframe", padding=8)
        summary_frame.pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            summary_frame,
            textvariable=self._var_summary,
            bg=DARK["bg"],
            fg=DARK["fg"],
            font=FONT_MONO,
            justify="left",
            anchor="w",
            wraplength=1100,
        ).pack(anchor="w", fill=tk.X)
        tk.Label(
            summary_frame,
            textvariable=self._var_artifact,
            bg=DARK["bg"],
            fg=DARK["label_fg"],
            font=FONT_SMALL,
            justify="left",
            anchor="w",
            wraplength=1100,
        ).pack(anchor="w", fill=tk.X, pady=(6, 0))

        log_frame = ttk.LabelFrame(outer, text="Live log", style="TLabelframe", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self._log = tk.Text(
            log_frame,
            height=16,
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
        scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self._log.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._log.configure(yscrollcommand=scroll.set, state="disabled")
        self._log.tag_configure("INFO", foreground=DARK["fg"])
        self._log.tag_configure("WARN", foreground=DARK["orange"])
        self._log.tag_configure("ERROR", foreground=DARK["red"])
        self._log.tag_configure("OK", foreground=DARK["green"])

    def _row(self, parent, label, var, command, row):
        ttk.Label(
            parent,
            text=label,
            font=FONT,
            foreground=DARK["label_fg"],
            background=DARK["bg"],
        ).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(parent, textvariable=var, font=FONT).grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Button(parent, text="Browse...", style="TButton", command=command).grid(
            row=row,
            column=2,
            sticky="w",
            padx=(6, 0),
            pady=2,
        )

    def _pick_queries(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=str(DEFAULT_QUERIES.parent),
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if path:
            self._var_queries.set(path)

    def _default_output_json(self) -> Path:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return DEFAULT_OUTPUT_DIR / f"ragas_eval_gui_{stamp}.json"

    def _on_start(self) -> None:
        if self._runner.is_alive:
            messagebox.showwarning("RAGAS", "A RAGAS run is already in progress.")
            return

        queries_path = Path(self._var_queries.get().strip())
        limit_raw = self._var_limit.get().strip()
        if not queries_path.exists():
            messagebox.showerror("RAGAS", f"Query JSON not found:\n{queries_path}")
            return
        if limit_raw:
            try:
                limit = int(limit_raw)
            except ValueError:
                messagebox.showerror("RAGAS", "Limit must be a positive integer or blank.")
                return
            if limit <= 0:
                messagebox.showerror("RAGAS", "Limit must be a positive integer or blank.")
                return
        else:
            limit = None

        output_path = self._default_output_json()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self._var_phase.set("starting")
        self._var_summary.set("Running RAGAS readiness/eval...")
        self._set_output(None, "")
        self._reset_progress()
        self._clear_log()
        self._set_running(True)
        self._append_log(f"Queries: {queries_path}", "INFO")
        self._append_log(f"Mode: {'analysis-only' if self._var_analysis_only.get() else 'execute'}", "INFO")
        if limit is not None:
            self._append_log(f"Limit: {limit}", "INFO")

        if self._on_run_start_cb:
            self._on_run_start_cb(
                {
                    "surface": "RAGAS",
                    "queries_path": str(queries_path),
                    "queries_pack_name": queries_path.name,
                    "analysis_only": self._var_analysis_only.get(),
                    "limit": limit,
                }
            )

        self._runner.start(
            queries_path=queries_path,
            output_path=output_path,
            limit=limit,
            analysis_only=self._var_analysis_only.get(),
            top_k=DEFAULT_TOP_K,
        )

    def _set_running(self, running: bool) -> None:
        self._btn_start.configure(state="disabled" if running else "normal")

    def _reset_progress(self) -> None:
        self._progress.configure(value=0, maximum=100)
        self._progress_label.configure(text="0 / 0")

    def _clear_log(self) -> None:
        self._log.configure(state="normal")
        self._log.delete("1.0", tk.END)
        self._log.configure(state="disabled")

    def _append_log(self, msg: str, level: str = "INFO") -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self._log.configure(state="normal")
        self._log.insert(tk.END, f"[{stamp}] {msg}\n", level)
        self._log.see(tk.END)
        self._log.configure(state="disabled")

    def _set_output(self, output_path: Path | None, proof_text: str) -> None:
        self._last_output_json = output_path
        artifact_text = f"Artifact: {output_path}" if output_path else "Artifact: -"
        proof_line = f"Proof: {proof_text or '-'}"
        self._var_artifact.set(f"{artifact_text}\n{proof_line}")
        self._btn_open.configure(state="normal" if output_path and output_path.exists() else "disabled")

    def _open_output(self) -> None:
        if self._last_output_json is None:
            return
        try:
            if sys.platform.startswith("win") and self._last_output_json.exists():
                os.startfile(str(self._last_output_json))  # type: ignore[attr-defined]
            else:
                messagebox.showinfo("RAGAS", str(self._last_output_json))
        except Exception as exc:
            messagebox.showerror("RAGAS", f"Could not open {self._last_output_json}:\n{exc}")

    def _on_runner_event(self, kind: str, payload: dict) -> None:
        safe_after(self, 0, self._dispatch_event, kind, payload)

    def _dispatch_event(self, kind: str, payload: dict) -> None:
        if kind == "log":
            self._append_log(payload.get("msg", ""), payload.get("level", "INFO"))
            return
        if kind == "phase":
            self._var_phase.set(payload.get("phase", "?"))
            return
        if kind == "progress":
            current = int(payload.get("current", 0))
            total = int(payload.get("total", 0)) or 1
            self._progress.configure(maximum=total, value=current)
            self._progress_label.configure(text=f"{current} / {total}")
            return
        if kind != "done":
            return

        self._set_running(False)
        self._var_phase.set(f"done ({payload.get('status', '?')})")
        artifacts = payload.get("artifact_paths") or {}
        output_json = artifacts.get("output_json")
        output_path = Path(output_json) if output_json else None
        proof_text = payload.get("proof_text") or ""
        self._set_output(output_path if output_path and output_path.exists() else None, proof_text)

        error = payload.get("error")
        summary = payload.get("summary") or {}
        if error:
            self._append_log(error, "ERROR")
            self._var_summary.set(f"RAGAS run failed.\nerror: {error}")
            if self._on_run_done_cb:
                self._on_run_done_cb(payload)
            return

        readiness = summary.get("readiness") or {}
        dependency = summary.get("dependencies") or {}
        metrics = summary.get("metric_summaries") or []
        mode = "analysis-only" if summary.get("analysis_only") else "execute"
        metric_line = "metrics:    none executed"
        if metrics:
            rendered = ", ".join(
                f"{item.get('name')} mean={item.get('mean')} n={item.get('count')}"
                for item in metrics
            )
            metric_line = f"metrics:    {rendered}"
        self._var_summary.set(
            "\n".join(
                [
                    f"queries:    {summary.get('queries_pack_name') or Path(summary.get('queries_path') or '').name or '?'}",
                    f"mode:       {mode}",
                    f"eligible:   {readiness.get('eligible_for_retrieval_metrics', 0)}/{readiness.get('total_queries', 0)}",
                    f"phase2c:    {readiness.get('fully_phase2c_enriched', 0)}/{readiness.get('total_queries', 0)}",
                    f"ragas:      {'installed' if dependency.get('ragas_installed') else 'missing'}",
                    metric_line,
                    f"elapsed_s:  {payload.get('elapsed_s', '?')}",
                ]
            )
        )
        self._append_log(
            f"RAGAS run finished with status {payload.get('status', '?')}.",
            "OK" if payload.get("status") == "PASS" else "WARN",
        )
        if self._on_run_done_cb:
            self._on_run_done_cb(payload)
