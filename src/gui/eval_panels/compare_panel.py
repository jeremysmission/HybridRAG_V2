"""ComparePanel -- side-by-side diff of two production eval result JSONs.

Loads a baseline (before) and candidate (after) eval results file, then
shows headline score deltas, per-query gain/loss/unchanged categorization,
and a filterable Treeview of changed queries with verdict transitions and
routing flips. Designed for the HybridRAG V2 eval GUI.

Self-contained: no imports from other eval panels or the main app shell.
"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_results(path: Path) -> dict:
    """Load and minimally validate an eval results JSON.

    Raises ValueError if the file cannot be parsed or is missing the
    required top-level structure.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Results file root must be a JSON object")
    if "results" not in data or not isinstance(data["results"], list):
        raise ValueError("Results file missing 'results' list")
    return data


def _by_id(results: list[dict]) -> dict:
    """Index a results list by query id (`id` field)."""
    out: dict = {}
    for r in results:
        if not isinstance(r, dict):
            continue
        qid = r.get("id") or r.get("query_id")
        if qid:
            out[str(qid)] = r
    return out


def _categorize(before: dict, after: dict) -> tuple[str, str]:
    """Categorize a single query's transition.

    Returns (category, human_label) where category is one of
    GAIN / LOSS / UNCHANGED and human_label is a short verdict arrow
    such as "MISS -> PASS" or "PASS (routing flipped)".
    """
    bv = (before.get("verdict") or "").upper()
    av = (after.get("verdict") or "").upper()
    rank = {"MISS": 0, "PARTIAL": 1, "PASS": 2}
    br = rank.get(bv, -1)
    ar = rank.get(av, -1)

    if bv == av:
        b_route = bool(before.get("routing_correct"))
        a_route = bool(after.get("routing_correct"))
        if b_route != a_route:
            label = f"{bv} (routing flipped)"
        else:
            label = f"{bv}"
        return ("UNCHANGED", label)

    if ar > br:
        return ("GAIN", f"{bv} -> {av}")
    if ar < br:
        return ("LOSS", f"{bv} -> {av}")
    return ("UNCHANGED", f"{bv} -> {av}")


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class ComparePanel(tk.Frame):
    """Tkinter panel that diffs two eval results JSON files."""

    FILTER_OPTIONS = ["Changed only", "Gains", "Losses", "Unchanged", "All"]

    def __init__(self, parent):
        super().__init__(parent, bg=DARK["bg"])
        apply_ttk_styles()

        # ---- state ----
        self._baseline_path: Optional[Path] = None
        self._candidate_path: Optional[Path] = None
        self._baseline_data: Optional[dict] = None
        self._candidate_data: Optional[dict] = None
        # rows: list of dicts with keys: qid, persona, before_label, after_label,
        #       category, delta_label, query_text
        self._rows: list[dict] = []

        # ---- tk vars ----
        self._baseline_var = tk.StringVar()
        self._candidate_var = tk.StringVar()
        self._baseline_status = tk.StringVar(value="")
        self._candidate_status = tk.StringVar(value="")
        self._filter_var = tk.StringVar(value="Changed only")
        self._persona_var = tk.StringVar(value="All")

        self._build_layout()
        self._update_compare_state()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        title = tk.Label(
            self,
            text="Eval Compare -- baseline vs. candidate",
            bg=DARK["bg"],
            fg=DARK["fg"],
            font=FONT_TITLE,
        )
        title.pack(anchor="w", padx=12, pady=(12, 6))

        # ---- Row A: file pickers ----
        row_a = tk.Frame(self, bg=DARK["bg"])
        row_a.pack(fill="x", padx=12, pady=(4, 8))

        baseline_frame = self._build_picker(
            row_a,
            "Baseline (before):",
            self._baseline_var,
            self._baseline_status,
            self._on_browse_baseline,
        )
        baseline_frame.pack(side="left", fill="x", expand=True, padx=(0, 8))

        candidate_frame = self._build_picker(
            row_a,
            "Candidate (after):",
            self._candidate_var,
            self._candidate_status,
            self._on_browse_candidate,
        )
        candidate_frame.pack(side="left", fill="x", expand=True, padx=(8, 0))

        compare_row = tk.Frame(self, bg=DARK["bg"])
        compare_row.pack(fill="x", padx=12, pady=(0, 10))
        self._compare_btn = ttk.Button(
            compare_row,
            text="Compare",
            style="Accent.TButton",
            command=self._on_compare,
        )
        self._compare_btn.pack(fill="x", expand=True)

        # ---- Row B: headline deltas ----
        self._headline_frame = tk.Frame(self, bg=DARK["panel_bg"])
        self._headline_frame.pack(fill="x", padx=12, pady=(0, 8))
        self._headline_labels: dict[str, tk.Label] = {}
        for key in ("pass", "partial", "miss", "routing", "p50"):
            lbl = tk.Label(
                self._headline_frame,
                text="",
                bg=DARK["panel_bg"],
                fg=DARK["label_fg"],
                font=FONT_BOLD,
                padx=14,
                pady=8,
            )
            lbl.pack(side="left")
            self._headline_labels[key] = lbl
        self._set_headline_placeholder()

        # ---- Row C: filters ----
        row_c = tk.Frame(self, bg=DARK["bg"])
        row_c.pack(fill="x", padx=12, pady=(0, 6))

        tk.Label(
            row_c, text="Show:", bg=DARK["bg"], fg=DARK["label_fg"], font=FONT
        ).pack(side="left")
        self._filter_combo = ttk.Combobox(
            row_c,
            textvariable=self._filter_var,
            values=self.FILTER_OPTIONS,
            state="readonly",
            width=16,
        )
        self._filter_combo.pack(side="left", padx=(6, 14))
        self._filter_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_tree())

        tk.Label(
            row_c, text="Persona:", bg=DARK["bg"], fg=DARK["label_fg"], font=FONT
        ).pack(side="left")
        self._persona_combo = ttk.Combobox(
            row_c,
            textvariable=self._persona_var,
            values=["All"],
            state="readonly",
            width=24,
        )
        self._persona_combo.pack(side="left", padx=(6, 14))
        self._persona_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_tree())

        ttk.Button(
            row_c,
            text="Clear",
            style="Tertiary.TButton",
            command=self._on_clear,
        ).pack(side="left")

        # ---- Row D: treeview ----
        tree_frame = tk.Frame(self, bg=DARK["bg"])
        tree_frame.pack(fill="both", expand=True, padx=12, pady=(4, 6))

        style = ttk.Style()
        style.configure(
            "Compare.Treeview",
            background=DARK["panel_bg"],
            fieldbackground=DARK["panel_bg"],
            foreground=DARK["fg"],
            rowheight=24,
            font=FONT,
            borderwidth=0,
        )
        style.configure(
            "Compare.Treeview.Heading",
            background=DARK["input_bg"],
            foreground=DARK["fg"],
            font=FONT_BOLD,
            relief="flat",
        )
        style.map(
            "Compare.Treeview",
            background=[("selected", DARK["accent"])],
            foreground=[("selected", DARK["accent_fg"])],
        )

        columns = ("query_id", "persona", "before", "after", "delta")
        self._tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            style="Compare.Treeview",
            selectmode="browse",
        )
        headings = {
            "query_id": ("Query ID", 110),
            "persona": ("Persona", 200),
            "before": ("Before", 110),
            "after": ("After", 110),
            "delta": ("Delta", 240),
        }
        for col, (label, width) in headings.items():
            self._tree.heading(col, text=label)
            self._tree.column(col, width=width, anchor="w", stretch=(col == "delta"))

        self._tree.tag_configure("GAIN", foreground=DARK["green"])
        self._tree.tag_configure("LOSS", foreground=DARK["red"])
        self._tree.tag_configure("UNCHANGED", foreground=DARK["gray"])
        self._tree.tag_configure("NEW", foreground=DARK["label_fg"])
        self._tree.tag_configure("REMOVED", foreground=DARK["label_fg"])

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._tree.bind("<<TreeviewSelect>>", self._on_select_row)

        # ---- Details pane ----
        details_frame = tk.Frame(self, bg=DARK["panel_bg"])
        details_frame.pack(fill="x", padx=12, pady=(2, 12))
        tk.Label(
            details_frame,
            text="Details",
            bg=DARK["panel_bg"],
            fg=DARK["accent"],
            font=FONT_SECTION,
        ).pack(anchor="w", padx=10, pady=(6, 0))
        self._details = tk.Text(
            details_frame,
            height=6,
            bg=DARK["panel_bg"],
            fg=DARK["fg"],
            font=FONT_MONO,
            wrap="word",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
        )
        self._details.pack(fill="x", padx=10, pady=(2, 8))
        self._details.configure(state="disabled")

    def _build_picker(
        self,
        parent: tk.Widget,
        label_text: str,
        path_var: tk.StringVar,
        status_var: tk.StringVar,
        browse_cmd,
    ) -> tk.Frame:
        frame = tk.Frame(parent, bg=DARK["panel_bg"])
        tk.Label(
            frame,
            text=label_text,
            bg=DARK["panel_bg"],
            fg=DARK["label_fg"],
            font=FONT_BOLD,
        ).pack(anchor="w", padx=10, pady=(8, 2))

        row = tk.Frame(frame, bg=DARK["panel_bg"])
        row.pack(fill="x", padx=10, pady=(0, 4))

        entry = tk.Entry(
            row,
            textvariable=path_var,
            bg=DARK["input_bg"],
            fg=DARK["input_fg"],
            insertbackground=DARK["fg"],
            relief="flat",
            font=FONT,
        )
        entry.pack(side="left", fill="x", expand=True, ipady=4)

        ttk.Button(
            row,
            text="Browse...",
            style="TButton",
            command=browse_cmd,
        ).pack(side="left", padx=(8, 0))

        tk.Label(
            frame,
            textvariable=status_var,
            bg=DARK["panel_bg"],
            fg=DARK["label_fg"],
            font=FONT_SMALL,
        ).pack(anchor="w", padx=10, pady=(0, 8))

        return frame

    # ------------------------------------------------------------------
    # File picking
    # ------------------------------------------------------------------
    def _on_browse_baseline(self) -> None:
        path = self._ask_results_file("Select baseline (before) results JSON")
        if path:
            self._try_load(path, role="baseline")

    def _on_browse_candidate(self) -> None:
        path = self._ask_results_file("Select candidate (after) results JSON")
        if path:
            self._try_load(path, role="candidate")

    def _ask_results_file(self, title: str) -> Optional[str]:
        return filedialog.askopenfilename(
            title=title,
            filetypes=[("Eval results JSON", "*.json"), ("All files", "*.*")],
        )

    def _try_load(self, path_str: str, role: str) -> None:
        path = Path(path_str)
        try:
            data = _load_results(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            messagebox.showerror(
                "Compare panel",
                f"Could not load {path.name}:\n{exc}",
            )
            return

        n = len(data.get("results", []))
        if role == "baseline":
            self._baseline_path = path
            self._baseline_data = data
            self._baseline_var.set(str(path))
            self._baseline_status.set(f"Loaded {n} queries")
        else:
            self._candidate_path = path
            self._candidate_data = data
            self._candidate_var.set(str(path))
            self._candidate_status.set(f"Loaded {n} queries")

        self._update_compare_state()

    def _update_compare_state(self) -> None:
        if self._baseline_data and self._candidate_data:
            self._compare_btn.state(["!disabled"])
        else:
            self._compare_btn.state(["disabled"])

    # ------------------------------------------------------------------
    # Compare logic
    # ------------------------------------------------------------------
    def _on_compare(self) -> None:
        if not (self._baseline_data and self._candidate_data):
            return

        before_idx = _by_id(self._baseline_data.get("results", []))
        after_idx = _by_id(self._candidate_data.get("results", []))

        rows: list[dict] = []
        all_ids = set(before_idx) | set(after_idx)
        for qid in sorted(all_ids):
            before = before_idx.get(qid)
            after = after_idx.get(qid)
            if before and after:
                category, label = _categorize(before, after)
                rows.append(
                    {
                        "qid": qid,
                        "persona": after.get("persona") or before.get("persona") or "",
                        "before_label": (before.get("verdict") or "").upper(),
                        "after_label": (after.get("verdict") or "").upper(),
                        "category": category,
                        "delta_label": label,
                        "query_text": after.get("query") or before.get("query") or "",
                        "before_routing": before.get("routed_query_type") or "",
                        "after_routing": after.get("routed_query_type") or "",
                        "before_routing_ok": bool(before.get("routing_correct")),
                        "after_routing_ok": bool(after.get("routing_correct")),
                    }
                )
            elif after and not before:
                rows.append(
                    {
                        "qid": qid,
                        "persona": after.get("persona") or "",
                        "before_label": "-",
                        "after_label": (after.get("verdict") or "").upper(),
                        "category": "NEW",
                        "delta_label": "+added",
                        "query_text": after.get("query") or "",
                        "before_routing": "",
                        "after_routing": after.get("routed_query_type") or "",
                        "before_routing_ok": False,
                        "after_routing_ok": bool(after.get("routing_correct")),
                    }
                )
            elif before and not after:
                rows.append(
                    {
                        "qid": qid,
                        "persona": before.get("persona") or "",
                        "before_label": (before.get("verdict") or "").upper(),
                        "after_label": "-",
                        "category": "REMOVED",
                        "delta_label": "-removed",
                        "query_text": before.get("query") or "",
                        "before_routing": before.get("routed_query_type") or "",
                        "after_routing": "",
                        "before_routing_ok": bool(before.get("routing_correct")),
                        "after_routing_ok": False,
                    }
                )

        self._rows = rows
        self._refresh_personas()
        self._refresh_headline()
        self._refresh_tree()
        self._clear_details()

    def _refresh_personas(self) -> None:
        personas = sorted({r["persona"] for r in self._rows if r["persona"]})
        values = ["All"] + personas
        self._persona_combo.configure(values=values)
        if self._persona_var.get() not in values:
            self._persona_var.set("All")

    # ------------------------------------------------------------------
    # Headline deltas
    # ------------------------------------------------------------------
    def _set_headline_placeholder(self) -> None:
        for key, lbl in self._headline_labels.items():
            lbl.configure(text=f"{key.upper()}: --", fg=DARK["label_fg"])

    def _refresh_headline(self) -> None:
        b = self._baseline_data or {}
        a = self._candidate_data or {}

        def fmt(key: str, label: str, lower_is_better: bool = False) -> tuple[str, str]:
            bv = int(b.get(key) or 0)
            av = int(a.get(key) or 0)
            delta = av - bv
            if delta == 0:
                color = DARK["label_fg"]
                sign = "+0"
            elif (delta > 0) ^ lower_is_better:
                color = DARK["green"]
                sign = f"+{delta}"
            else:
                color = DARK["red"]
                sign = f"{delta}"
            return (f"{label}: {bv} -> {av} ({sign})", color)

        text, color = fmt("pass_count", "PASS")
        self._headline_labels["pass"].configure(text=text, fg=color)

        # PARTIAL: neither direction is strictly "good" -- color gray when
        # zero, otherwise just show direction in label_fg to avoid implying
        # judgement on partials in isolation.
        bv = int(b.get("partial_count") or 0)
        av = int(a.get("partial_count") or 0)
        delta = av - bv
        sign = f"+{delta}" if delta > 0 else (f"{delta}" if delta < 0 else "+0")
        self._headline_labels["partial"].configure(
            text=f"PARTIAL: {bv} -> {av} ({sign})",
            fg=DARK["label_fg"],
        )

        text, color = fmt("miss_count", "MISS", lower_is_better=True)
        self._headline_labels["miss"].configure(text=text, fg=color)

        text, color = fmt("routing_correct", "Routing")
        self._headline_labels["routing"].configure(text=text, fg=color)

        bv = int(b.get("p50_pure_retrieval_ms") or 0)
        av = int(a.get("p50_pure_retrieval_ms") or 0)
        delta = av - bv
        if delta == 0:
            color = DARK["label_fg"]
        elif delta < 0:
            color = DARK["green"]
        else:
            color = DARK["red"]
        self._headline_labels["p50"].configure(
            text=f"P50 retrieval: {bv}ms -> {av}ms",
            fg=color,
        )

    # ------------------------------------------------------------------
    # Tree refresh / filtering
    # ------------------------------------------------------------------
    def _refresh_tree(self) -> None:
        for iid in self._tree.get_children():
            self._tree.delete(iid)

        flt = self._filter_var.get()
        persona = self._persona_var.get()

        for row in self._rows:
            cat = row["category"]
            if persona != "All" and row["persona"] != persona:
                continue
            if flt == "Gains" and cat != "GAIN":
                continue
            if flt == "Losses" and cat != "LOSS":
                continue
            if flt == "Unchanged" and cat != "UNCHANGED":
                continue
            if flt == "Changed only" and cat == "UNCHANGED":
                # Show routing flips even though verdict unchanged
                if "routing flipped" not in row["delta_label"]:
                    continue

            self._tree.insert(
                "",
                "end",
                iid=row["qid"],
                values=(
                    row["qid"],
                    row["persona"],
                    row["before_label"],
                    row["after_label"],
                    row["delta_label"],
                ),
                tags=(cat,),
            )

    # ------------------------------------------------------------------
    # Details pane
    # ------------------------------------------------------------------
    def _on_select_row(self, _event=None) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        qid = sel[0]
        row = next((r for r in self._rows if r["qid"] == qid), None)
        if row is None:
            return
        lines = [
            f"Query  : {row['qid']}  ({row['persona']})",
            f"Text   : {row['query_text']}",
            f"Before : verdict={row['before_label']}  routing={row['before_routing']}"
            f" (correct={row['before_routing_ok']})",
            f"After  : verdict={row['after_label']}  routing={row['after_routing']}"
            f" (correct={row['after_routing_ok']})",
            f"Delta  : {row['delta_label']}",
        ]
        self._write_details("\n".join(lines))

    def _write_details(self, text: str) -> None:
        self._details.configure(state="normal")
        self._details.delete("1.0", "end")
        self._details.insert("1.0", text)
        self._details.configure(state="disabled")

    def _clear_details(self) -> None:
        self._write_details("")

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------
    def _on_clear(self) -> None:
        self._filter_var.set("Changed only")
        self._persona_var.set("All")
        self._refresh_tree()
