"""Count benchmark panel for the eval workbench."""

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

from .benchmark_runners import CountBenchmarkRunner

V2_ROOT = Path(__file__).resolve().parents[3]


class CountPanel(tk.Frame):
    """Tkinter panel responsible for the Count area of the interface."""
    def __init__(self, parent):
        super().__init__(parent, bg=DARK["bg"])
        from scripts import count_benchmark as cb

        self._runner = CountBenchmarkRunner(self._on_runner_event)
        self._var_targets = StringVar(value=str(cb.DEFAULT_TARGETS))
        self._var_lance_db = StringVar(value=str(cb.DEFAULT_LANCE_DB))
        self._var_entity_db = StringVar(value=str(cb.DEFAULT_ENTITY_DB))
        self._var_output_dir = StringVar(value=str(cb.DEFAULT_OUTPUT_DIR))
        self._var_predictions = StringVar(value="")
        self._var_include_deferred = BooleanVar(value=False)
        self._mode_vars = {
            "raw_mentions": BooleanVar(value=True),
            "unique_documents": BooleanVar(value=True),
            "unique_chunks": BooleanVar(value=True),
            "unique_rows": BooleanVar(value=True),
        }
        self._var_phase = StringVar(value="idle")
        self._var_summary = StringVar(value="No count benchmark run yet.")
        self._var_artifacts = StringVar(value="Artifacts: -")
        self._last_output_json: Path | None = None
        self._last_output_md: Path | None = None
        self._build()
        self._set_running(False)
        self._set_outputs(None, None)

    def _build(self) -> None:
        outer = ttk.Frame(self, style="TFrame", padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text="Count Benchmark",
            font=FONT_TITLE,
            foreground=DARK["fg"],
            background=DARK["bg"],
        ).pack(anchor="w", pady=(0, 10))

        form = ttk.LabelFrame(outer, text="Inputs", style="TLabelframe", padding=10)
        form.pack(fill=tk.X)
        self._row(form, "Targets JSON:", self._var_targets, self._pick_targets, 0)
        self._row(form, "LanceDB path:", self._var_lance_db, self._pick_lance_db, 1)
        self._row(form, "Entity DB:", self._var_entity_db, self._pick_entity_db, 2)
        self._row(form, "Output dir:", self._var_output_dir, self._pick_output_dir, 3)
        self._row(form, "Predictions JSON:", self._var_predictions, self._pick_predictions, 4)

        opt_row = ttk.Frame(form, style="TFrame")
        opt_row.grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            opt_row,
            text="Include deferred targets",
            variable=self._var_include_deferred,
            style="TCheckbutton",
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(
            opt_row,
            text="Modes:",
            font=FONT,
            foreground=DARK["label_fg"],
            background=DARK["bg"],
        ).pack(side=tk.LEFT, padx=(0, 6))
        for mode, var in self._mode_vars.items():
            ttk.Checkbutton(
                opt_row,
                text=mode,
                variable=var,
                style="TCheckbutton",
            ).pack(side=tk.LEFT, padx=(0, 8))

        form.columnconfigure(1, weight=1)

        ctrl = ttk.Frame(outer, style="TFrame")
        ctrl.pack(fill=tk.X, pady=(12, 6))
        self._btn_start = ttk.Button(ctrl, text="Start", style="Accent.TButton", command=self._on_start)
        self._btn_start.pack(side=tk.LEFT, padx=(0, 6))
        self._btn_stop = ttk.Button(ctrl, text="Stop", style="Tertiary.TButton", command=self._on_stop)
        self._btn_stop.pack(side=tk.LEFT, padx=(0, 6))
        self._btn_stop.configure(state="disabled")
        self._btn_clear = ttk.Button(ctrl, text="Clear log", style="Tertiary.TButton", command=self._clear_log)
        self._btn_clear.pack(side=tk.LEFT, padx=(0, 6))
        self._btn_open_json = ttk.Button(ctrl, text="Open JSON", style="TButton", command=self._open_json)
        self._btn_open_json.pack(side=tk.LEFT, padx=(0, 6))
        self._btn_open_md = ttk.Button(ctrl, text="Open MD", style="TButton", command=self._open_md)
        self._btn_open_md.pack(side=tk.LEFT)
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
            textvariable=self._var_artifacts,
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

    def _pick_targets(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=str((V2_ROOT / "tests" / "golden_eval").resolve()),
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if path:
            self._var_targets.set(path)

    def _pick_lance_db(self) -> None:
        path = filedialog.askdirectory(
            initialdir=str((V2_ROOT / "data" / "index").resolve()),
        )
        if path:
            self._var_lance_db.set(path)

    def _pick_entity_db(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=str((V2_ROOT / "data" / "index").resolve()),
            filetypes=[("SQLite", "*.sqlite3 *.db"), ("All files", "*.*")],
        )
        if path:
            self._var_entity_db.set(path)

    def _pick_output_dir(self) -> None:
        path = filedialog.askdirectory(
            initialdir=self._var_output_dir.get() or str((V2_ROOT / "tests").resolve()),
        )
        if path:
            self._var_output_dir.set(path)

    def _pick_predictions(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=str((V2_ROOT / "tests").resolve()),
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if path:
            self._var_predictions.set(path)

    def _selected_modes(self) -> tuple[str, ...]:
        return tuple(mode for mode, var in self._mode_vars.items() if var.get())

    def _on_start(self) -> None:
        if self._runner.is_alive:
            messagebox.showwarning("Count benchmark", "A run is already in progress.")
            return

        targets_path = Path(self._var_targets.get().strip())
        lance_db = Path(self._var_lance_db.get().strip())
        entity_db = Path(self._var_entity_db.get().strip())
        output_dir = Path(self._var_output_dir.get().strip())
        predictions_raw = self._var_predictions.get().strip()
        predictions_json = Path(predictions_raw) if predictions_raw else None
        modes = self._selected_modes()

        if not targets_path.exists():
            messagebox.showerror("Count benchmark", f"Targets JSON not found:\n{targets_path}")
            return
        if not lance_db.exists():
            messagebox.showerror("Count benchmark", f"LanceDB path not found:\n{lance_db}")
            return
        if not entity_db.exists():
            messagebox.showerror("Count benchmark", f"Entity DB not found:\n{entity_db}")
            return
        if predictions_json and not predictions_json.exists():
            messagebox.showerror("Count benchmark", f"Predictions JSON not found:\n{predictions_json}")
            return
        if not modes:
            messagebox.showerror("Count benchmark", "Select at least one count mode.")
            return

        output_dir.mkdir(parents=True, exist_ok=True)
        self._var_summary.set("Running count benchmark...")
        self._set_outputs(None, None)
        self._var_phase.set("starting")
        self._reset_progress()
        self._clear_log()
        self._set_running(True)
        self._append_log(f"Targets: {targets_path}", "INFO")
        self._append_log(f"Modes: {', '.join(modes)}", "INFO")
        if self._var_include_deferred.get():
            self._append_log("Including deferred targets.", "WARN")
        self._runner.start(
            targets_path=targets_path,
            lance_db=lance_db,
            entity_db=entity_db,
            output_dir=output_dir,
            modes=modes,
            include_deferred=self._var_include_deferred.get(),
            predictions_json=predictions_json,
        )

    def _on_stop(self) -> None:
        if self._runner.is_alive:
            self._runner.stop()

    def _set_running(self, running: bool) -> None:
        self._btn_start.configure(state="disabled" if running else "normal")
        self._btn_stop.configure(state="normal" if running else "disabled")

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

    def _set_outputs(self, json_path: Path | None, md_path: Path | None) -> None:
        self._last_output_json = json_path
        self._last_output_md = md_path
        self._btn_open_json.configure(state="normal" if json_path and json_path.exists() else "disabled")
        self._btn_open_md.configure(state="normal" if md_path and md_path.exists() else "disabled")
        if json_path or md_path:
            self._var_artifacts.set(
                "\n".join(
                    [
                        f"JSON: {json_path or '-'}",
                        f"MD:   {md_path or '-'}",
                    ]
                )
            )
        else:
            self._var_artifacts.set("Artifacts: -")

    def _open_path(self, path: Path | None) -> None:
        if path is None:
            return
        try:
            if sys.platform.startswith("win") and path.exists():
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                messagebox.showinfo("Count benchmark", str(path))
        except Exception as exc:
            messagebox.showerror("Count benchmark", f"Could not open {path}:\n{exc}")

    def _open_json(self) -> None:
        self._open_path(self._last_output_json)

    def _open_md(self) -> None:
        self._open_path(self._last_output_md)

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
        json_path = Path(artifacts["output_json"]) if artifacts.get("output_json") else None
        md_path = Path(artifacts["output_md"]) if artifacts.get("output_md") else None
        self._set_outputs(
            json_path if json_path and json_path.exists() else None,
            md_path if md_path and md_path.exists() else None,
        )

        error = payload.get("error")
        summary = payload.get("summary") or {}
        if error:
            self._append_log(error, "ERROR")
            self._var_summary.set(f"Count benchmark failed.\nerror: {error}")
            return

        prediction_total = summary.get("prediction_total") or 0
        lines = [
            f"lane:       {payload.get('lane_name', '?')}",
            f"targets:    {summary.get('selected_targets', 0)}",
            f"frozen:     {summary.get('expected_exact', 0)}/{summary.get('expected_total', 0)} exact",
        ]
        if prediction_total:
            lines.append(f"pred exact: {summary.get('prediction_exact', 0)}/{prediction_total}")
            lines.append(f"max error:  {summary.get('prediction_max_abs_error', '?')}")
        lines.append(f"elapsed_s:  {payload.get('elapsed_s', '?')}")
        self._var_summary.set("\n".join(lines))
        self._append_log(
            (
                f"Count benchmark finished: {summary.get('selected_targets', 0)} targets, "
                f"{summary.get('expected_exact', 0)}/{summary.get('expected_total', 0)} frozen exact"
            ),
            "OK",
        )
