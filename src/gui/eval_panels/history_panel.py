"""Evaluation history panel. It shows prior benchmark runs so an operator can compare what changed over time."""
# ============================================================================
# HybridRAG V2 -- Eval History Panel (src/gui/eval_panels/history_panel.py)
# ============================================================================
# Scans docs/ for production_eval_results*.json files, parses each, and shows
# a sortable history table plus a dependency-free ASCII score timeline.
# ============================================================================

import json
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from src.gui.theme import (
    DARK,
    FONT,
    FONT_BOLD,
    FONT_MONO,
    FONT_TITLE,
    FONT_SECTION,
    FONT_SMALL,
    apply_ttk_styles,
)


# Resolve the V2 repo root from this module's location so the history
# scan works on any checkout path. Prior hardcoded C:\HybridRAG_V2\docs
# caused silent empty history on clones or alternate install paths.
_V2_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DOCS_DIR = _V2_ROOT / "docs"
EVAL_GLOB = "production_eval_results*.json"


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


def _stage_summary_line(stage_latency_summary: dict) -> str:
    """Support the history panel workflow by handling the stage summary line step."""
    preferred = [
        "vector_search",
        "structured_lookup",
        "entity_lookup",
        "relationship_lookup",
        "aggregate_lookup",
        "tabular_lookup",
        "rerank",
        "context_build",
    ]
    parts: list[str] = []
    for stage in preferred:
        stats = stage_latency_summary.get(stage)
        if not isinstance(stats, dict):
            continue
        p50 = stats.get("p50_ms")
        p95 = stats.get("p95_ms")
        count = stats.get("queries_with_stage")
        if p50 is None or p95 is None:
            continue
        suffix = f", n={count}" if count not in (None, "") else ""
        parts.append(f"{stage} {p50}/{p95} ms{suffix}")
    return "    ".join(parts)

COLUMNS = (
    "run_id",
    "timestamp",
    "label",
    "total",
    "pass",
    "partial",
    "miss",
    "routing",
    "p50",
    "strongest",
    "weakest",
    "filename",
)

COLUMN_LABELS = {
    "run_id": "Run ID",
    "timestamp": "Timestamp (UTC)",
    "label": "Pack / Config",
    "total": "Total",
    "pass": "PASS",
    "partial": "PARTIAL",
    "miss": "MISS",
    "routing": "Routing",
    "p50": "p50 (ms)",
    "strongest": "Strongest",
    "weakest": "Weakest",
    "filename": "File",
}

COLUMN_WIDTHS = {
    "run_id": 140,
    "timestamp": 180,
    "label": 240,
    "total": 60,
    "pass": 60,
    "partial": 70,
    "miss": 60,
    "routing": 80,
    "p50": 70,
    "strongest": 180,
    "weakest": 180,
    "filename": 320,
}


class HistoryPanel(tk.Frame):
    """Eval history browser: scans docs/ for production_eval_results*.json."""

    def __init__(self, parent, docs_dir: Path | None = None):
        super().__init__(parent, bg=DARK["bg"])

        self._docs_dir: Path = Path(docs_dir) if docs_dir else DEFAULT_DOCS_DIR
        self._records: list[dict] = []
        self._skipped: list[str] = []
        self._sort_state: dict[str, bool] = {}  # column -> ascending?
        self._iid_to_record: dict[str, dict] = {}
        self._detail_var = tk.StringVar(value="Select a run to inspect its benchmark summary.")

        # Make sure ttk styles are applied (idempotent, safe to re-run).
        try:
            apply_ttk_styles(DARK)
        except Exception:
            pass

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self):
        # ---- Top row ---------------------------------------------------
        top = tk.Frame(self, bg=DARK["bg"])
        top.pack(side="top", fill="x", padx=10, pady=(10, 6))

        tk.Label(
            top,
            text="Docs directory:",
            bg=DARK["bg"],
            fg=DARK["fg"],
            font=FONT,
        ).pack(side="left", padx=(0, 6))

        self._dir_var = tk.StringVar(value=str(self._docs_dir))
        self._dir_entry = tk.Entry(
            top,
            textvariable=self._dir_var,
            font=FONT,
            bg=DARK["input_bg"],
            fg=DARK["input_fg"],
            insertbackground=DARK["fg"],
            relief="flat",
            bd=2,
            width=60,
        )
        self._dir_entry.pack(side="left", padx=(0, 6), fill="x", expand=True)

        ttk.Button(
            top,
            text="Browse...",
            style="TButton",
            command=self._on_browse,
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            top,
            text="Refresh",
            style="Accent.TButton",
            command=self.refresh,
        ).pack(side="left", padx=(0, 12))

        self._status_label = tk.Label(
            top,
            text="Loaded 0 runs (0 skipped)",
            bg=DARK["bg"],
            fg=DARK["label_fg"],
            font=FONT_SMALL,
        )
        self._status_label.pack(side="left")

        # ---- Main paned window -----------------------------------------
        paned = tk.PanedWindow(
            self,
            orient="horizontal",
            bg=DARK["bg"],
            sashrelief="flat",
            sashwidth=6,
            bd=0,
        )
        paned.pack(side="top", fill="both", expand=True, padx=10, pady=6)

        # Left -- Treeview
        left = tk.Frame(paned, bg=DARK["panel_bg"])
        paned.add(left, minsize=400, stretch="always")

        # ttk styles specific to this Treeview
        style = ttk.Style()
        style.configure(
            "History.Treeview",
            background=DARK["panel_bg"],
            fieldbackground=DARK["panel_bg"],
            foreground=DARK["fg"],
            font=FONT,
            rowheight=24,
            bordercolor=DARK["border"],
            borderwidth=0,
        )
        style.configure(
            "History.Treeview.Heading",
            background=DARK["input_bg"],
            foreground=DARK["fg"],
            font=FONT_BOLD,
            relief="flat",
        )
        style.map(
            "History.Treeview",
            background=[("selected", DARK["accent"])],
            foreground=[("selected", DARK["accent_fg"])],
        )
        style.map(
            "History.Treeview.Heading",
            background=[("active", DARK["border"])],
        )

        tree_wrap = tk.Frame(left, bg=DARK["panel_bg"])
        tree_wrap.pack(fill="both", expand=True, padx=4, pady=4)

        self._tree = ttk.Treeview(
            tree_wrap,
            columns=COLUMNS,
            show="headings",
            style="History.Treeview",
            selectmode="browse",
        )
        for col in COLUMNS:
            self._tree.heading(
                col,
                text=COLUMN_LABELS[col],
                command=lambda c=col: self._sort_by(c),
            )
            anchor = "w" if col in ("run_id", "timestamp", "filename") else "center"
            self._tree.column(
                col,
                width=COLUMN_WIDTHS[col],
                anchor=anchor,
                stretch=(col == "filename"),
            )

        # tag colors
        self._tree.tag_configure("pass_max", foreground=DARK["green"])
        self._tree.tag_configure("miss_cell", foreground=DARK["red"])

        vsb = ttk.Scrollbar(
            tree_wrap, orient="vertical", command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._tree.bind("<Double-1>", self._on_double_click)
        self._tree.bind("<Button-3>", self._on_right_click)
        self._tree.bind("<<TreeviewSelect>>", self._on_select_row)

        # ---- Right -- Selected run + timeline --------------------------
        right = tk.Frame(paned, bg=DARK["panel_bg"])
        paned.add(right, minsize=300, stretch="always")

        tk.Label(
            right,
            text="Selected run",
            bg=DARK["panel_bg"],
            fg=DARK["accent"],
            font=FONT_SECTION,
            anchor="w",
        ).pack(side="top", fill="x", padx=12, pady=(8, 4))

        self._detail_label = tk.Label(
            right,
            textvariable=self._detail_var,
            bg=DARK["panel_bg"],
            fg=DARK["fg"],
            font=FONT_MONO,
            justify="left",
            anchor="w",
            wraplength=520,
        )
        self._detail_label.pack(side="top", fill="x", padx=12, pady=(0, 8))

        tk.Label(
            right,
            text="Score timeline",
            bg=DARK["panel_bg"],
            fg=DARK["accent"],
            font=FONT_SECTION,
            anchor="w",
        ).pack(side="top", fill="x", padx=12, pady=(8, 4))

        text_wrap = tk.Frame(right, bg=DARK["panel_bg"])
        text_wrap.pack(side="top", fill="both", expand=True, padx=4, pady=(0, 4))

        self._timeline = tk.Text(
            text_wrap,
            font=FONT_MONO,
            bg=DARK["panel_bg"],
            fg=DARK["fg"],
            insertbackground=DARK["fg"],
            bd=0,
            wrap="none",
            padx=12,
            pady=8,
            relief="flat",
            highlightthickness=0,
        )
        tl_vsb = ttk.Scrollbar(
            text_wrap, orient="vertical", command=self._timeline.yview
        )
        tl_hsb = ttk.Scrollbar(
            text_wrap, orient="horizontal", command=self._timeline.xview
        )
        self._timeline.configure(
            yscrollcommand=tl_vsb.set, xscrollcommand=tl_hsb.set
        )
        self._timeline.grid(row=0, column=0, sticky="nsew")
        tl_vsb.grid(row=0, column=1, sticky="ns")
        tl_hsb.grid(row=1, column=0, sticky="ew")
        text_wrap.rowconfigure(0, weight=1)
        text_wrap.columnconfigure(0, weight=1)
        self._timeline.configure(state="disabled")

        # try to set initial sash position around 60/40
        try:
            self.update_idletasks()
            total_w = max(self.winfo_width(), 1000)
            paned.sash_place(0, int(total_w * 0.6), 1)
        except Exception:
            pass

        # ---- Bottom status bar -----------------------------------------
        bottom = tk.Frame(self, bg=DARK["bg"])
        bottom.pack(side="bottom", fill="x", padx=10, pady=(4, 10))
        self._hint_label = tk.Label(
            bottom,
            text="Double-click a row to open its report JSON. "
                 "Right-click for more options.",
            bg=DARK["bg"],
            fg=DARK["label_fg"],
            font=FONT_SMALL,
            anchor="w",
        )
        self._hint_label.pack(side="left", fill="x", expand=True)

        # context menu
        self._ctx_menu = tk.Menu(
            self,
            tearoff=0,
            bg=DARK["menu_bg"],
            fg=DARK["menu_fg"],
            activebackground=DARK["accent"],
            activeforeground=DARK["accent_fg"],
            bd=0,
        )
        self._ctx_menu.add_command(
            label="Open JSON", command=self._ctx_open_json
        )
        self._ctx_menu.add_command(
            label="Open MD report", command=self._ctx_open_md
        )
        self._ctx_menu.add_command(
            label="Copy path", command=self._ctx_copy_path
        )
        self._ctx_target_iid: str | None = None

    # ------------------------------------------------------------- Loading --
    def refresh(self):
        """Re-scan docs_dir and repopulate everything. Idempotent."""
        # pull current value from entry, in case user typed it
        try:
            entered = self._dir_var.get().strip()
            if entered:
                self._docs_dir = Path(entered)
        except Exception:
            pass

        self._records = []
        self._skipped = []
        self._iid_to_record = {}

        if not self._docs_dir.exists() or not self._docs_dir.is_dir():
            self._update_status(missing=True)
            self._populate_tree()
            self._render_timeline()
            return

        try:
            files = sorted(self._docs_dir.glob(EVAL_GLOB))
        except Exception:
            files = []

        for fp in files:
            rec = self._parse_file(fp)
            if rec is None:
                self._skipped.append(fp.name)
            else:
                self._records.append(rec)

        # sort by timestamp ascending by default
        self._records.sort(key=lambda r: r.get("_sort_ts") or "")

        self._update_status()
        self._populate_tree()
        self._render_timeline()

    def _parse_file(self, fp: Path) -> dict | None:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return None
        if not isinstance(data, dict):
            return None

        try:
            mtime_iso = ""
            try:
                from datetime import datetime, timezone
                mtime_iso = datetime.fromtimestamp(
                    fp.stat().st_mtime, tz=timezone.utc
                ).isoformat()
            except Exception:
                mtime_iso = ""

            ts = data.get("timestamp_utc") or mtime_iso or ""

            prov = data.get("provenance") or {}
            run_summary = prov.get("run_summary") or {}
            score_summary = run_summary.get("score_summary") or {}
            latency_summary = run_summary.get("latency_summary") or {}
            stage_latency_summary = run_summary.get("stage_latency_summary") or {}
            artifact_paths = prov.get("artifact_paths") or {}
            queries_pack = (
                prov.get("queries_pack_name")
                or (Path(prov.get("queries_path", "")).name if prov.get("queries_path") else "")
                or ""
            )
            config_name = (
                prov.get("config_name")
                or (Path(prov.get("config_path", "")).name if prov.get("config_path") else "")
                or ""
            )

            def _stem(name: str) -> str:
                return Path(name).stem if name else ""

            if queries_pack and config_name:
                label = f"{_stem(queries_pack)} / {_stem(config_name)}"
            elif queries_pack:
                label = _stem(queries_pack)
            else:
                label = _stem(fp.name)

            rec = {
                "run_id": str(data.get("run_id", "") or ""),
                "timestamp_utc": str(data.get("timestamp_utc", "") or ""),
                "run_status": prov.get("run_status") or score_summary.get("status") or "",
                "label": label,
                "queries_pack": queries_pack,
                "queries_path": prov.get("queries_path") or "",
                "config_name": config_name,
                "config_path": prov.get("config_path") or "",
                "store_path": prov.get("store_path") or prov.get("lance_path") or "",
                "store_chunks": data.get("store_chunks"),
                "router_mode": prov.get("router_mode") or "",
                "provider": prov.get("provider") or "",
                "model": prov.get("model") or "",
                "gpu_device": prov.get("gpu_device") or data.get("gpu_device", ""),
                "total_queries": int(data.get("total_queries") or 0),
                "pass_count": int(data.get("pass_count") or 0),
                "partial_count": int(data.get("partial_count") or 0),
                "miss_count": int(data.get("miss_count") or 0),
                "routing_correct": int(data.get("routing_correct") or 0),
                "p50_pure_retrieval_ms": data.get("p50_pure_retrieval_ms"),
                "p95_pure_retrieval_ms": data.get("p95_pure_retrieval_ms"),
                "strongest_summary": ", ".join(
                    (run_summary.get("strongest_areas") or run_summary.get("strongest_query_types") or [])[:2]
                ),
                "weakest_summary": ", ".join(
                    (run_summary.get("weakest_areas") or run_summary.get("weakest_query_types") or [])[:2]
                ),
                "strongest_areas": run_summary.get("strongest_areas") or [],
                "weakest_areas": run_summary.get("weakest_areas") or [],
                "score_summary": score_summary,
                "latency_summary": latency_summary,
                "stage_latency_summary": stage_latency_summary,
                "elapsed": prov.get("elapsed_s")
                or data.get("elapsed_seconds")
                or data.get("elapsed_sec")
                or data.get("elapsed")
                or "",
                "filename": fp.name,
                "path": str(fp),
                "results_json_path": artifact_paths.get("results_json") or prov.get("results_json_path") or str(fp),
                "report_md_path": artifact_paths.get("report_md") or prov.get("report_md_path") or "",
                "_sort_ts": ts,
            }
            return rec
        except Exception:
            return None

    # ------------------------------------------------------------- Display --
    def _update_status(self, missing: bool = False):
        if missing:
            txt = (
                f"Directory not found: {self._docs_dir}  "
                f"(0 runs, 0 skipped)"
            )
            self._status_label.configure(text=txt, fg=DARK["orange"])
            return

        n = len(self._records)
        m = len(self._skipped)
        txt = f"Loaded {n} runs ({m} skipped)"
        if m:
            txt += " -- skipped: " + ", ".join(self._skipped[:3])
            if m > 3:
                txt += f" (+{m - 3} more)"
        self._status_label.configure(
            text=txt,
            fg=DARK["label_fg"] if m == 0 else DARK["orange"],
        )

    def _populate_tree(self):
        # clear
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        self._iid_to_record = {}

        if not self._records:
            self._detail_var.set("Select a run to inspect its benchmark summary.")
            return

        max_pass = max((r["pass_count"] for r in self._records), default=0)

        for idx, rec in enumerate(self._records):
            ts = rec["timestamp_utc"] or "(file mtime: " + (rec["_sort_ts"] or "?") + ")"
            # Clip timestamp to seconds for compact display
            ts_disp = ts.replace("T", " ")
            if "." in ts_disp:
                ts_disp = ts_disp.split(".")[0]
            if "+" in ts_disp:
                ts_disp = ts_disp.split("+")[0]

            p50 = rec.get("p50_pure_retrieval_ms")
            p50_disp = "" if p50 is None else str(p50)

            values = (
                rec["run_id"] or "(no id)",
                ts_disp,
                rec.get("label") or "",
                rec["total_queries"],
                rec["pass_count"],
                rec["partial_count"],
                rec["miss_count"],
                rec["routing_correct"],
                p50_disp,
                rec.get("strongest_summary") or "",
                rec.get("weakest_summary") or "",
                rec["filename"],
            )

            tags = []
            if rec["pass_count"] == max_pass and max_pass > 0:
                tags.append("pass_max")
            if rec["miss_count"] > 0:
                tags.append("miss_cell")

            iid = f"row{idx}"
            self._tree.insert(
                "", "end", iid=iid, values=values, tags=tuple(tags)
            )
            self._iid_to_record[iid] = rec

        latest_iid = next(reversed(self._iid_to_record), None)
        if latest_iid:
            self._tree.selection_set(latest_iid)
            self._tree.focus(latest_iid)
            self._render_selected_record(self._iid_to_record[latest_iid])

    def _render_timeline(self):
        self._timeline.configure(state="normal")
        self._timeline.delete("1.0", "end")

        if not self._records:
            self._timeline.insert(
                "1.0", "(no eval result files found)\n"
            )
            self._timeline.configure(state="disabled")
            return

        max_pass = max((r["pass_count"] for r in self._records), default=0)
        bar_w = 14

        header = (
            f"{'run_id':<20} {'pass / total':<14} {'routing':<11} timeline\n"
        )
        sep = "-" * (20 + 1 + 14 + 1 + 11 + 1 + bar_w + 2) + "\n"
        self._timeline.insert("end", header)
        self._timeline.insert("end", sep)

        for rec in self._records:
            run_id = (rec["run_id"] or rec["filename"])[:20]
            pc = rec["pass_count"]
            tot = rec["total_queries"]
            rc = rec["routing_correct"]
            pass_total = f"{pc} / {tot}"
            routing = f"{rc}/{tot}"

            if max_pass > 0:
                filled = int(round((pc / max_pass) * bar_w))
            else:
                filled = 0
            filled = max(0, min(bar_w, filled))
            bar = "[" + ("#" * filled) + ("." * (bar_w - filled)) + "]"

            line = (
                f"{run_id:<20} {pass_total:<14} {routing:<11} {bar}\n"
            )
            self._timeline.insert("end", line)

        if self._skipped:
            self._timeline.insert("end", "\nSkipped (unparseable):\n")
            for name in self._skipped:
                self._timeline.insert("end", f"  - {name}\n")

        self._timeline.configure(state="disabled")

    def _render_selected_record(self, rec: dict | None):
        if not rec:
            self._detail_var.set("Select a run to inspect its benchmark summary.")
            return

        total = rec.get("total_queries") or 0
        score_summary = rec.get("score_summary") or {}
        latency_summary = rec.get("latency_summary") or {}
        stage_latency_summary = rec.get("stage_latency_summary") or {}
        strongest = rec.get("strongest_areas") or []
        weakest = rec.get("weakest_areas") or []
        router_mode = rec.get("router_mode") or ""
        provider = rec.get("provider") or ""
        model = rec.get("model") or ""

        lines = [
            f"run_id:    {rec.get('run_id') or '(no id)'}",
            f"time:      {rec.get('timestamp_utc') or '?'}    status: {rec.get('run_status') or '?'}",
            f"pack:      {rec.get('queries_pack') or '?'}",
            f"config:    {rec.get('config_name') or '?'}",
            f"store:     {rec.get('store_path') or '?'}",
        ]
        if router_mode or provider or model:
            if provider or model:
                lines.append(
                    f"router:    {router_mode or 'llm'} ({' / '.join(part for part in (provider, model) if part)})"
                )
            else:
                lines.append(f"router:    {router_mode}")
        if total:
            lines.append(
                "score:     "
                f"PASS {rec.get('pass_count', 0)}/{total} "
                f"({_fmt_pct(score_summary.get('pass_rate_pct'))})    "
                f"PARTIAL {rec.get('partial_count', 0)}/{total}    "
                f"MISS {rec.get('miss_count', 0)}/{total}    "
                f"Routing {rec.get('routing_correct', 0)}/{total} "
                f"({_fmt_pct(score_summary.get('routing_rate_pct'))})"
            )
        if strongest:
            lines.append(f"strongest: {', '.join(strongest)}")
        if weakest:
            lines.append(f"weakest:   {', '.join(weakest)}")
        if latency_summary:
            lines.append(
                "latency:   "
                f"retr {latency_summary.get('p50_pure_retrieval_ms', '?')}/"
                f"{latency_summary.get('p95_pure_retrieval_ms', '?')} ms    "
                f"wall {latency_summary.get('p50_wall_clock_ms', '?')}/"
                f"{latency_summary.get('p95_wall_clock_ms', '?')} ms    "
                f"router {latency_summary.get('p50_router_ms', '?')}/"
                f"{latency_summary.get('p95_router_ms', '?')} ms    "
                f"elapsed {latency_summary.get('elapsed_s', rec.get('elapsed') or '?')}s"
            )
        stage_line = _stage_summary_line(stage_latency_summary)
        if stage_line:
            lines.append(f"stages:    {stage_line}")
        lines.append(f"json@:     {rec.get('results_json_path') or rec.get('path') or '?'}")
        lines.append(f"report@:   {rec.get('report_md_path') or '?'}")
        if rec.get("queries_path"):
            lines.append(f"queries@:  {rec['queries_path']}")
        if rec.get("config_path"):
            lines.append(f"config@:   {rec['config_path']}")

        self._detail_var.set("\n".join(lines))

    # --------------------------------------------------------------- Sort --
    def _sort_by(self, col: str):
        if not self._records:
            return
        ascending = not self._sort_state.get(col, False)
        self._sort_state[col] = ascending

        def key_fn(r):
            if col == "run_id":
                return r["run_id"] or ""
            if col == "timestamp":
                return r["_sort_ts"] or ""
            if col == "total":
                return r["total_queries"]
            if col == "pass":
                return r["pass_count"]
            if col == "partial":
                return r["partial_count"]
            if col == "miss":
                return r["miss_count"]
            if col == "routing":
                return r["routing_correct"]
            if col == "p50":
                v = r.get("p50_pure_retrieval_ms")
                return -1 if v is None else v
            if col == "strongest":
                return r.get("strongest_summary") or ""
            if col == "weakest":
                return r.get("weakest_summary") or ""
            if col == "filename":
                return r["filename"]
            if col == "label":
                return r.get("label") or ""
            return ""

        self._records.sort(key=key_fn, reverse=not ascending)
        self._populate_tree()
        self._render_timeline()

    # ---------------------------------------------------------- Browsing --
    def _on_browse(self):
        chosen = filedialog.askdirectory(
            initialdir=str(self._docs_dir)
            if self._docs_dir.exists()
            else os.getcwd(),
            title="Select docs directory",
        )
        if chosen:
            self._docs_dir = Path(chosen)
            self._dir_var.set(str(self._docs_dir))
            self.refresh()

    # ----------------------------------------------------------- Row UX --
    def _on_double_click(self, event):
        iid = self._tree.identify_row(event.y)
        if not iid:
            return
        rec = self._iid_to_record.get(iid)
        if not rec:
            return
        self._open_path(rec.get("path"))

    def _on_right_click(self, event):
        iid = self._tree.identify_row(event.y)
        if not iid:
            return
        self._tree.selection_set(iid)
        self._ctx_target_iid = iid
        try:
            self._ctx_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._ctx_menu.grab_release()

    def _ctx_open_json(self):
        rec = self._current_ctx_record()
        if rec:
            self._open_path(rec.get("path"))

    def _ctx_open_md(self):
        rec = self._current_ctx_record()
        if not rec:
            return
        md_path = rec.get("report_md_path") or ""
        if not md_path:
            path = rec.get("path") or ""
            if path.lower().endswith(".json"):
                md_path = path[:-5] + ".md"
            else:
                md_path = path + ".md"
        self._open_path(md_path)

    def _ctx_copy_path(self):
        rec = self._current_ctx_record()
        if not rec:
            return
        path = rec.get("path") or ""
        try:
            self.clipboard_clear()
            self.clipboard_append(path)
        except Exception:
            pass

    def _current_ctx_record(self) -> dict | None:
        if self._ctx_target_iid:
            return self._iid_to_record.get(self._ctx_target_iid)
        sel = self._tree.selection()
        if sel:
            return self._iid_to_record.get(sel[0])
        return None

    def _on_select_row(self, _event=None):
        sel = self._tree.selection()
        if not sel:
            self._render_selected_record(None)
            return
        self._render_selected_record(self._iid_to_record.get(sel[0]))

    def _open_path(self, path: str | None):
        if not path:
            return
        try:
            if sys.platform.startswith("win"):
                if os.path.exists(path):
                    os.startfile(path)  # type: ignore[attr-defined]
        except Exception:
            pass


# ----------------------------------------------------------- Standalone --
if __name__ == "__main__":
    root = tk.Tk()
    root.title("HybridRAG V2 -- Eval History")
    root.geometry("1400x800")
    root.configure(bg=DARK["bg"])
    apply_ttk_styles(DARK)
    panel = HistoryPanel(root)
    panel.pack(fill="both", expand=True)
    root.mainloop()
