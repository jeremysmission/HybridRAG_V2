"""Results viewer panel for the HybridRAG V2 production eval GUI.

Loads an eval results JSON produced by ``scripts/run_production_eval.py``
and renders all per-query results in a filterable Treeview alongside a
details pane showing the full record (query text, expected vs. routed
query type, top retrieved sources, timings, errors). Standalone: depends
only on the shared theme module and reads files directly, so it is safe
to instantiate in headless tests without a model object.
"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional

from src.gui.theme import (
    DARK,
    FONT,
    FONT_BOLD,
    FONT_MONO,
    FONT_SECTION,
    FONT_SMALL,
    FONT_TITLE,
    apply_ttk_styles,
    current_theme,
)


_DEFAULT_RESULTS_DIR = Path(r"C:\HybridRAG_V2\docs")


class ResultsPanel(tk.Frame):
    """Filterable viewer for production eval result JSON files."""

    def __init__(
        self,
        parent: tk.Misc,
        initial_path: Optional[Path] = None,
    ) -> None:
        super().__init__(parent, bg=DARK["bg"])

        # Make sure ttk styles are registered (idempotent).
        try:
            apply_ttk_styles(current_theme())
        except Exception:
            # Headless / no display -- styles not strictly required for tests.
            pass

        self._configure_treeview_style()

        self._all_results: List[Dict[str, Any]] = []
        self._visible_results: List[Dict[str, Any]] = []
        self._run_meta: Dict[str, Any] = {}
        self._current_path: Optional[Path] = Path(initial_path) if initial_path else None

        self._path_var = tk.StringVar(value=str(self._current_path) if self._current_path else "")
        self._verdict_var = tk.StringVar(value="All")
        self._persona_var = tk.StringVar(value="All")
        self._family_var = tk.StringVar(value="All")
        self._qtype_var = tk.StringVar(value="All")
        self._status_var = tk.StringVar(value="No results loaded")

        self._scorecard_vars: Dict[str, tk.StringVar] = {
            "PASS": tk.StringVar(value="-"),
            "PARTIAL": tk.StringVar(value="-"),
            "MISS": tk.StringVar(value="-"),
            "Routing": tk.StringVar(value="-"),
            "p50": tk.StringVar(value="-"),
            "p95": tk.StringVar(value="-"),
        }

        self._build_top_row()
        self._build_scorecard()
        self._build_filter_row()
        self._build_main_split()
        self._build_status_bar()

        if self._current_path is not None and self._current_path.exists():
            self.load_file(self._current_path)

    # ------------------------------------------------------------------
    # Style
    # ------------------------------------------------------------------
    def _configure_treeview_style(self) -> None:
        try:
            style = ttk.Style()
            style.configure(
                "Treeview",
                rowheight=24,
                font=FONT,
                background=DARK["panel_bg"],
                foreground=DARK["fg"],
                fieldbackground=DARK["panel_bg"],
                bordercolor=DARK["border"],
                borderwidth=0,
            )
            style.configure(
                "Treeview.Heading",
                font=FONT_BOLD,
                background=DARK["input_bg"],
                foreground=DARK["fg"],
                relief="flat",
            )
            style.map(
                "Treeview",
                background=[("selected", DARK["accent"])],
                foreground=[("selected", DARK["accent_fg"])],
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Layout builders
    # ------------------------------------------------------------------
    def _build_top_row(self) -> None:
        row = tk.Frame(self, bg=DARK["bg"])
        row.pack(side="top", fill="x", padx=12, pady=(12, 6))

        tk.Label(
            row,
            text="Results file:",
            bg=DARK["bg"],
            fg=DARK["label_fg"],
            font=FONT_BOLD,
        ).pack(side="left", padx=(0, 8))

        entry = tk.Entry(
            row,
            textvariable=self._path_var,
            bg=DARK["input_bg"],
            fg=DARK["fg"],
            insertbackground=DARK["fg"],
            relief="flat",
            font=FONT,
            highlightthickness=1,
            highlightbackground=DARK["border"],
            highlightcolor=DARK["accent"],
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=4)

        ttk.Button(
            row,
            text="Browse...",
            style="TButton",
            command=self._on_browse,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            row,
            text="Load Results",
            style="Accent.TButton",
            command=self._on_load_clicked,
        ).pack(side="left")

    def _build_scorecard(self) -> None:
        strip = tk.Frame(self, bg=DARK["panel_bg"], highlightthickness=1,
                         highlightbackground=DARK["border"])
        strip.pack(side="top", fill="x", padx=12, pady=6)

        cells = [
            ("PASS", DARK["green"]),
            ("PARTIAL", DARK["orange"]),
            ("MISS", DARK["red"]),
            ("Routing", DARK["accent"]),
            ("p50", DARK["fg"]),
            ("p95", DARK["fg"]),
        ]
        for i, (label, color) in enumerate(cells):
            cell = tk.Frame(strip, bg=DARK["panel_bg"])
            cell.pack(side="left", padx=14, pady=8)
            tk.Label(
                cell,
                text=label,
                bg=DARK["panel_bg"],
                fg=DARK["label_fg"],
                font=FONT_SMALL,
            ).pack(anchor="w")
            tk.Label(
                cell,
                textvariable=self._scorecard_vars[label],
                bg=DARK["panel_bg"],
                fg=color,
                font=FONT_SECTION,
            ).pack(anchor="w")

    def _build_filter_row(self) -> None:
        row = tk.Frame(self, bg=DARK["bg"])
        row.pack(side="top", fill="x", padx=12, pady=(0, 6))

        def _add(label_text: str, var: tk.StringVar, values: List[str]) -> ttk.Combobox:
            tk.Label(
                row,
                text=label_text,
                bg=DARK["bg"],
                fg=DARK["label_fg"],
                font=FONT_SMALL,
            ).pack(side="left", padx=(0, 4))
            cb = ttk.Combobox(
                row,
                textvariable=var,
                values=values,
                state="readonly",
                width=18,
                style="TCombobox",
            )
            cb.pack(side="left", padx=(0, 12))
            cb.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters())
            return cb

        self._verdict_cb = _add("Verdict:", self._verdict_var,
                                ["All", "PASS", "PARTIAL", "MISS"])
        self._persona_cb = _add("Persona:", self._persona_var, ["All"])
        self._family_cb = _add("Family:", self._family_var, ["All"])
        self._qtype_cb = _add("Query type:", self._qtype_var, ["All"])

        ttk.Button(
            row,
            text="Clear filters",
            style="Tertiary.TButton",
            command=self._on_clear_filters,
        ).pack(side="left")

    def _build_main_split(self) -> None:
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(side="top", fill="both", expand=True, padx=12, pady=6)

        # --- Left: Treeview ---
        left = tk.Frame(paned, bg=DARK["panel_bg"])
        paned.add(left, weight=3)

        columns = ("query_id", "persona", "verdict", "routing", "ms")
        self._tree = ttk.Treeview(
            left,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        self._tree.heading("query_id", text="Query ID")
        self._tree.heading("persona", text="Persona")
        self._tree.heading("verdict", text="Verdict")
        self._tree.heading("routing", text="Routing")
        self._tree.heading("ms", text="Retrieval ms")

        self._tree.column("query_id", width=90, anchor="w", stretch=False)
        self._tree.column("persona", width=170, anchor="w", stretch=True)
        self._tree.column("verdict", width=80, anchor="center", stretch=False)
        self._tree.column("routing", width=80, anchor="center", stretch=False)
        self._tree.column("ms", width=110, anchor="e", stretch=False)

        self._tree.tag_configure("PASS", foreground=DARK["green"])
        self._tree.tag_configure("MISS", foreground=DARK["red"])
        self._tree.tag_configure("PARTIAL", foreground=DARK["orange"])

        vsb = ttk.Scrollbar(left, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._tree.bind("<<TreeviewSelect>>", self._on_row_selected)

        # --- Right: details pane (scrollable Text) ---
        right = tk.Frame(paned, bg=DARK["panel_bg"])
        paned.add(right, weight=2)

        self._details = tk.Text(
            right,
            wrap="word",
            bg=DARK["panel_bg"],
            fg=DARK["fg"],
            insertbackground=DARK["fg"],
            relief="flat",
            padx=12,
            pady=12,
            font=FONT,
            highlightthickness=0,
            state="disabled",
        )
        dvsb = ttk.Scrollbar(right, orient="vertical", command=self._details.yview)
        self._details.configure(yscrollcommand=dvsb.set)
        self._details.pack(side="left", fill="both", expand=True)
        dvsb.pack(side="right", fill="y")

        self._details.tag_configure("title", font=FONT_TITLE, foreground=DARK["accent"],
                                    spacing3=8)
        self._details.tag_configure("section", font=FONT_SECTION,
                                    foreground=DARK["label_fg"], spacing1=8, spacing3=4)
        self._details.tag_configure("label", font=FONT_BOLD, foreground=DARK["label_fg"])
        self._details.tag_configure("body", font=FONT, foreground=DARK["fg"])
        self._details.tag_configure("mono", font=FONT_MONO, foreground=DARK["fg"])
        self._details.tag_configure("verdict_pass", font=FONT_BOLD, foreground=DARK["green"])
        self._details.tag_configure("verdict_partial", font=FONT_BOLD, foreground=DARK["orange"])
        self._details.tag_configure("verdict_miss", font=FONT_BOLD, foreground=DARK["red"])
        self._details.tag_configure("error", font=FONT_BOLD, foreground=DARK["red"])
        self._details.tag_configure("ok", foreground=DARK["green"])
        self._details.tag_configure("bad", foreground=DARK["red"])

    def _build_status_bar(self) -> None:
        bar = tk.Frame(self, bg=DARK["panel_bg"], highlightthickness=1,
                       highlightbackground=DARK["border"])
        bar.pack(side="bottom", fill="x", padx=12, pady=(6, 12))
        tk.Label(
            bar,
            textvariable=self._status_var,
            bg=DARK["panel_bg"],
            fg=DARK["label_fg"],
            font=FONT_SMALL,
            anchor="w",
        ).pack(side="left", padx=10, pady=4)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load_file(self, path: Path) -> bool:
        """Load an eval results JSON file. Returns True on success."""
        path = Path(path)
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            messagebox.showerror("Results not found", f"File does not exist:\n{path}")
            return False
        except json.JSONDecodeError as exc:
            messagebox.showerror("Malformed JSON",
                                 f"Could not parse {path.name}:\n{exc}")
            return False
        except OSError as exc:
            messagebox.showerror("Read error", f"Could not read {path}:\n{exc}")
            return False

        if not isinstance(data, dict):
            messagebox.showerror("Unexpected schema",
                                 "Top-level JSON value is not an object.")
            return False

        results = data.get("results")
        if not isinstance(results, list):
            messagebox.showerror("Unexpected schema",
                                 "JSON does not contain a 'results' array.")
            return False

        self._current_path = path
        self._path_var.set(str(path))
        self._run_meta = {k: v for k, v in data.items() if k != "results"}
        self._all_results = [r for r in results if isinstance(r, dict)]

        self._refresh_filter_options()
        self._update_scorecard()
        self._apply_filters()
        return True

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_browse(self) -> None:
        initial_dir = (
            str(self._current_path.parent)
            if self._current_path and self._current_path.exists()
            else str(_DEFAULT_RESULTS_DIR)
        )
        chosen = filedialog.askopenfilename(
            title="Select eval results JSON",
            initialdir=initial_dir,
            filetypes=[("JSON results", "*.json"), ("All files", "*.*")],
        )
        if chosen:
            self._path_var.set(chosen)
            self.load_file(Path(chosen))

    def _on_load_clicked(self) -> None:
        raw = self._path_var.get().strip()
        if not raw:
            messagebox.showerror("No file", "Choose a results JSON file first.")
            return
        self.load_file(Path(raw))

    def _on_clear_filters(self) -> None:
        self._verdict_var.set("All")
        self._persona_var.set("All")
        self._family_var.set("All")
        self._qtype_var.set("All")
        self._apply_filters()

    def _on_row_selected(self, _event: Optional[tk.Event] = None) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except (TypeError, ValueError):
            return
        if 0 <= idx < len(self._visible_results):
            self._render_details(self._visible_results[idx])

    # ------------------------------------------------------------------
    # Filtering / rendering
    # ------------------------------------------------------------------
    def _refresh_filter_options(self) -> None:
        personas = sorted({str(r.get("persona", "")) for r in self._all_results if r.get("persona")})
        families = sorted({str(r.get("expected_document_family", ""))
                           for r in self._all_results if r.get("expected_document_family")})
        qtypes = sorted({str(r.get("expected_query_type", ""))
                         for r in self._all_results if r.get("expected_query_type")})

        self._persona_cb.configure(values=["All"] + personas)
        self._family_cb.configure(values=["All"] + families)
        self._qtype_cb.configure(values=["All"] + qtypes)

        if self._persona_var.get() not in (["All"] + personas):
            self._persona_var.set("All")
        if self._family_var.get() not in (["All"] + families):
            self._family_var.set("All")
        if self._qtype_var.get() not in (["All"] + qtypes):
            self._qtype_var.set("All")

    def _update_scorecard(self) -> None:
        meta = self._run_meta
        total = meta.get("total_queries") or len(self._all_results) or 0

        def _pct(n: Any) -> str:
            try:
                n_int = int(n)
            except (TypeError, ValueError):
                return "-"
            if not total:
                return f"{n_int}"
            return f"{n_int} ({n_int / total * 100:.0f}%)"

        self._scorecard_vars["PASS"].set(_pct(meta.get("pass_count")))
        self._scorecard_vars["PARTIAL"].set(_pct(meta.get("partial_count")))
        self._scorecard_vars["MISS"].set(_pct(meta.get("miss_count")))
        self._scorecard_vars["Routing"].set(_pct(meta.get("routing_correct")))

        p50 = meta.get("p50_pure_retrieval_ms")
        p95 = meta.get("p95_pure_retrieval_ms")
        self._scorecard_vars["p50"].set(f"{p50} ms" if p50 is not None else "-")
        self._scorecard_vars["p95"].set(f"{p95} ms" if p95 is not None else "-")

    def _apply_filters(self) -> None:
        verdict = self._verdict_var.get()
        persona = self._persona_var.get()
        family = self._family_var.get()
        qtype = self._qtype_var.get()

        def _keep(r: Dict[str, Any]) -> bool:
            if verdict != "All" and r.get("verdict") != verdict:
                return False
            if persona != "All" and r.get("persona") != persona:
                return False
            if family != "All" and r.get("expected_document_family") != family:
                return False
            if qtype != "All" and r.get("expected_query_type") != qtype:
                return False
            return True

        self._visible_results = [r for r in self._all_results if _keep(r)]
        self._populate_tree()
        self._status_var.set(
            f"{len(self._visible_results)} of {len(self._all_results)} queries shown"
        )

    def _populate_tree(self) -> None:
        for iid in self._tree.get_children():
            self._tree.delete(iid)

        for idx, r in enumerate(self._visible_results):
            qid = r.get("id") or r.get("query_id") or "?"
            persona = r.get("persona") or "-"
            verdict = (r.get("verdict") or "").upper() or "-"
            routing_ok = bool(r.get("routing_correct"))
            routing = "OK" if routing_ok else "MISS"
            ms = r.get("retrieval_ms")
            ms_text = f"{ms}" if ms is not None else "-"

            tags = (verdict,) if verdict in ("PASS", "PARTIAL", "MISS") else ()
            self._tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(qid, persona, verdict, routing, ms_text),
                tags=tags,
            )

        self._clear_details()

    # ------------------------------------------------------------------
    # Details rendering
    # ------------------------------------------------------------------
    def _clear_details(self) -> None:
        self._details.configure(state="normal")
        self._details.delete("1.0", "end")
        self._details.configure(state="disabled")

    def _render_details(self, r: Dict[str, Any]) -> None:
        self._details.configure(state="normal")
        self._details.delete("1.0", "end")

        qid = r.get("id") or r.get("query_id") or "?"
        persona = r.get("persona") or "-"
        self._details.insert("end", f"{qid}  --  {persona}\n", "title")

        query_text = r.get("query") or r.get("query_text") or ""
        self._details.insert("end", "Query\n", "section")
        self._details.insert("end", f"{query_text}\n", "mono")

        verdict = (r.get("verdict") or "").upper()
        verdict_tag = {
            "PASS": "verdict_pass",
            "PARTIAL": "verdict_partial",
            "MISS": "verdict_miss",
        }.get(verdict, "body")
        self._details.insert("end", "\nVerdict: ", "label")
        self._details.insert("end", f"{verdict or '-'}\n", verdict_tag)

        self._details.insert("end", "Expected family: ", "label")
        self._details.insert("end", f"{r.get('expected_document_family', '-')}\n", "body")

        self._details.insert("end", "Expected query type: ", "label")
        self._details.insert("end", f"{r.get('expected_query_type', '-')}\n", "body")

        routed = r.get("routed_query_type", "-")
        routing_correct = bool(r.get("routing_correct"))
        self._details.insert("end", "Routed: ", "label")
        self._details.insert("end", f"{routed}  ", "body")
        self._details.insert(
            "end",
            "(OK)\n" if routing_correct else "(MISS)\n",
            "ok" if routing_correct else "bad",
        )

        self._details.insert("end", "\nTimings\n", "section")
        self._details.insert(
            "end",
            f"  router_ms        : {r.get('router_ms', '-')}\n"
            f"  retrieval_ms     : {r.get('retrieval_ms', '-')}\n"
            f"  embed_retrieve_ms: {r.get('embed_retrieve_ms', '-')}\n",
            "mono",
        )

        self._details.insert("end", "\nFlags\n", "section")
        self._details.insert(
            "end",
            f"  top_in_family    : {r.get('top_in_family', '-')}\n"
            f"  any_top5_in_fam  : {r.get('any_top5_in_family', '-')}\n"
            f"  entity_dependent : {r.get('entity_dependent', '-')}\n",
            "mono",
        )

        signals = r.get("family_signals")
        if isinstance(signals, list) and signals:
            self._details.insert("end", "\nFamily signals\n", "section")
            self._details.insert("end", "  " + ", ".join(str(s) for s in signals) + "\n", "body")

        top_results = r.get("top_results")
        self._details.insert("end", "\nTop results\n", "section")
        if isinstance(top_results, list) and top_results:
            for entry in top_results:
                if not isinstance(entry, dict):
                    continue
                rank = entry.get("rank", "?")
                score = entry.get("score", 0.0)
                in_fam = entry.get("in_family")
                source = entry.get("source_path") or entry.get("short_source") or "(unknown)"
                marker = "[in-fam]" if in_fam else "[      ]"
                try:
                    score_str = f"{float(score):.4f}"
                except (TypeError, ValueError):
                    score_str = str(score)
                self._details.insert(
                    "end",
                    f"  #{rank} {marker} score={score_str}\n",
                    "body",
                )
                self._details.insert("end", f"      {source}\n", "mono")
                preview = entry.get("text_preview")
                if preview:
                    self._details.insert("end", f"      {preview}\n", "mono")
        else:
            self._details.insert("end", "  (none)\n", "body")

        notes = r.get("notes")
        if notes:
            self._details.insert("end", "\nNotes\n", "section")
            self._details.insert("end", f"{notes}\n", "body")

        error = r.get("error")
        if error:
            self._details.insert("end", "\nError: ", "label")
            self._details.insert("end", f"{error}\n", "error")

        self._details.configure(state="disabled")
        self._details.see("1.0")
