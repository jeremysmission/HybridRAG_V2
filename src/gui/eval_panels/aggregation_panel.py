"""Aggregation benchmark panel for the eval workbench."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from tkinter import StringVar, filedialog, messagebox
import tkinter as tk
from tkinter import ttk

from src.gui.helpers.safe_after import safe_after
from src.gui.theme import DARK, FONT, FONT_BOLD, FONT_MONO, FONT_SMALL, FONT_TITLE

from .benchmark_runners import AggregationBenchmarkRunner

V2_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = V2_ROOT / "tests" / "aggregation_benchmark" / "aggregation_seed_manifest_2026-04-15.json"
DEFAULT_OUTPUT_DIR = V2_ROOT / "tests" / "aggregation_benchmark" / "results"


class AggregationPanel(tk.Frame):
    """Tkinter panel responsible for the Aggregation area of the interface."""
    def __init__(self, parent):
        super().__init__(parent, bg=DARK["bg"])
        self._runner = AggregationBenchmarkRunner(self._on_runner_event)
        self._var_manifest = StringVar(value=str(DEFAULT_MANIFEST))
        self._var_answers = StringVar(value="")
        self._var_output = StringVar(value=self._default_output_json())
        self._var_min_pass_rate = StringVar(value="1.0")
        self._var_phase = StringVar(value="idle")
        self._var_summary = StringVar(value="No aggregation benchmark run yet.")
        self._var_artifact = StringVar(value="Output JSON: -")
        self._last_output_json: Path | None = None
        self._build()
        self._set_running(False)
        self._set_output(None)

    def _build(self) -> None:
        outer = ttk.Frame(self, style="TFrame", padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text="Aggregation Benchmark",
            font=FONT_TITLE,
            foreground=DARK["fg"],
            background=DARK["bg"],
        ).pack(anchor="w", pady=(0, 10))

        form = ttk.LabelFrame(outer, text="Inputs", style="TLabelframe", padding=10)
        form.pack(fill=tk.X)
        self._row(form, "Manifest:", self._var_manifest, self._pick_manifest, 0)
        self._row(form, "Answers JSON:", self._var_answers, self._pick_answers, 1)
        self._row(form, "Output JSON:", self._var_output, self._pick_output, 2)

        gate_row = ttk.Frame(form, style="TFrame")
        gate_row.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(
            gate_row,
            text="Min pass rate:",
            font=FONT,
            foreground=DARK["label_fg"],
            background=DARK["bg"],
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Entry(gate_row, textvariable=self._var_min_pass_rate, width=6, font=FONT).pack(side=tk.LEFT)
        ttk.Label(
            gate_row,
            text="Blank answers file runs self-check mode.",
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
        self._btn_open = ttk.Button(ctrl, text="Open output", style="TButton", command=self._open_output)
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

    def _default_output_json(self) -> str:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return str(DEFAULT_OUTPUT_DIR / f"aggregation_benchmark_gui_{stamp}.json")

    def _pick_manifest(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=str(DEFAULT_MANIFEST.parent),
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if path:
            self._var_manifest.set(path)

    def _pick_answers(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=str(DEFAULT_MANIFEST.parent),
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if path:
            self._var_answers.set(path)

    def _pick_output(self) -> None:
        path = filedialog.asksaveasfilename(
            initialdir=str(DEFAULT_OUTPUT_DIR),
            initialfile=Path(self._var_output.get()).name,
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if path:
            self._var_output.set(path)

    def _on_start(self) -> None:
        if self._runner.is_alive:
            messagebox.showwarning("Aggregation benchmark", "A run is already in progress.")
            return
        manifest_path = Path(self._var_manifest.get().strip())
        answers_raw = self._var_answers.get().strip()
        answers_path = Path(answers_raw) if answers_raw else None
        output_path = Path(self._var_output.get().strip() or self._default_output_json())
        try:
            min_pass_rate = float(self._var_min_pass_rate.get().strip() or "1.0")
        except ValueError:
            messagebox.showerror("Aggregation benchmark", "Min pass rate must be a number.")
            return
        if not manifest_path.exists():
            messagebox.showerror("Aggregation benchmark", f"Manifest not found:\n{manifest_path}")
            return
        if answers_path and not answers_path.exists():
            messagebox.showerror("Aggregation benchmark", f"Answers JSON not found:\n{answers_path}")
            return
        if output_path.exists():
            proceed = messagebox.askyesno(
                "Overwrite output file?",
                f"The output file already exists and will be overwritten:\n\n{output_path}",
                default="no",
            )
            if not proceed:
                self._append_log("Run cancelled: operator declined overwrite.", "WARN")
                return

        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._var_output.set(str(output_path))
        self._var_phase.set("starting")
        self._var_summary.set("Running aggregation benchmark...")
        self._set_output(None)
        self._reset_progress()
        self._clear_log()
        self._set_running(True)
        self._append_log(f"Manifest: {manifest_path}", "INFO")
        self._append_log(f"Mode: {'self-check' if answers_path is None else 'score'}", "INFO")
        self._runner.start(
            manifest_path=manifest_path,
            answers_path=answers_path,
            output_path=output_path,
            min_pass_rate=min_pass_rate,
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

    def _set_output(self, output_path: Path | None) -> None:
        self._last_output_json = output_path
        self._var_artifact.set(f"Output JSON: {output_path}" if output_path else "Output JSON: -")
        self._btn_open.configure(state="normal" if output_path and output_path.exists() else "disabled")

    def _open_output(self) -> None:
        if self._last_output_json is None:
            return
        try:
            if sys.platform.startswith("win") and self._last_output_json.exists():
                os.startfile(str(self._last_output_json))  # type: ignore[attr-defined]
            else:
                messagebox.showinfo("Aggregation benchmark", str(self._last_output_json))
        except Exception as exc:
            messagebox.showerror("Aggregation benchmark", f"Could not open {self._last_output_json}:\n{exc}")

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
        artifact = (payload.get("artifact_paths") or {}).get("output_json")
        artifact_path = Path(artifact) if artifact else None
        if artifact_path and artifact_path.exists():
            self._set_output(artifact_path)
        else:
            self._set_output(None)

        error = payload.get("error")
        summary = payload.get("summary") or {}
        if error:
            self._append_log(error, "ERROR")
            self._var_summary.set(f"Aggregation benchmark failed.\nerror: {error}")
            return

        gate = "PASS" if summary.get("gate_pass") else "FAIL"
        self._var_summary.set(
            "\n".join(
                [
                    f"benchmark: {summary.get('benchmark_id', '?')}",
                    f"mode:      {summary.get('mode', '?')}",
                    f"gate:      {gate}",
                    (
                        f"score:     {summary.get('pass_count', 0)}/{summary.get('total_items', 0)} "
                        f"({float(summary.get('pass_rate', 0.0)):.3f})"
                    ),
                    f"elapsed_s: {payload.get('elapsed_s', '?')}",
                ]
            )
        )
        level = "OK" if summary.get("gate_pass") else "WARN"
        self._append_log(
            (
                f"Aggregation benchmark finished: {summary.get('pass_count', 0)}/"
                f"{summary.get('total_items', 0)} passed"
            ),
            level,
        )
