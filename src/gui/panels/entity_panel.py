# ============================================================================
# HybridRAG V2 -- Entity Panel (src/gui/panels/entity_panel.py)
# ============================================================================
# Displays entity type summary, searchable relationship list, and basic
# entity lookup. Uses entity_store and relationship_store directly
# (read-only). New panel for V2 tri-store architecture.
# ============================================================================

import tkinter as tk
from tkinter import ttk
import threading
import logging

from src.gui.theme import current_theme, FONT, FONT_BOLD, FONT_SMALL, FONT_MONO
from src.gui.helpers.safe_after import safe_after
from src.gui.scrollable import ScrollableFrame

logger = logging.getLogger(__name__)


class EntityPanel(tk.LabelFrame):
    """Entity browser panel -- view entities, relationships, and type counts.

    Sections:
      1. Entity type summary (PERSON: X, PART: Y, SITE: Z, ...)
      2. Entity lookup (type dropdown + text pattern search)
      3. Relationship list (searchable by subject/object text)
    """

    def __init__(self, parent, model):
        t = current_theme()
        super().__init__(parent, text="Entities", padx=16, pady=16,
                         bg=t["panel_bg"], fg=t["accent"], font=FONT_BOLD)
        self._model = model
        self._build_widgets(t)
        # Load data after panel is visible
        self.after(300, self._refresh_summary)

    def _build_widgets(self, t):
        """Build all child widgets."""

        # -- Section 1: Entity type summary --
        summary_label = tk.Label(
            self, text="Entity Type Summary", font=FONT_BOLD,
            bg=t["panel_bg"], fg=t["fg"], anchor=tk.W,
        )
        summary_label.pack(fill=tk.X, pady=(0, 4))

        self._summary_text = tk.Text(
            self, height=6, wrap=tk.WORD, state=tk.DISABLED,
            font=FONT_MONO, bg=t["input_bg"], fg=t["input_fg"],
            relief=tk.FLAT, bd=1,
        )
        self._summary_text.pack(fill=tk.X, pady=(0, 12))

        # -- Section 2: Entity lookup --
        lookup_label = tk.Label(
            self, text="Entity Lookup", font=FONT_BOLD,
            bg=t["panel_bg"], fg=t["fg"], anchor=tk.W,
        )
        lookup_label.pack(fill=tk.X, pady=(0, 4))

        lookup_row = tk.Frame(self, bg=t["panel_bg"])
        lookup_row.pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            lookup_row, text="Type:", bg=t["panel_bg"],
            fg=t["fg"], font=FONT,
        ).pack(side=tk.LEFT)

        self._type_var = tk.StringVar(value="(any)")
        self._type_combo = ttk.Combobox(
            lookup_row, textvariable=self._type_var,
            values=["(any)"], state="readonly", width=14, font=FONT,
        )
        self._type_combo.pack(side=tk.LEFT, padx=(4, 8))

        tk.Label(
            lookup_row, text="Pattern:", bg=t["panel_bg"],
            fg=t["fg"], font=FONT,
        ).pack(side=tk.LEFT)

        self._pattern_entry = tk.Entry(
            lookup_row, font=FONT, bg=t["input_bg"], fg=t["input_fg"],
            insertbackground=t["fg"], relief=tk.FLAT, bd=2, width=24,
        )
        self._pattern_entry.pack(side=tk.LEFT, padx=(4, 8), ipady=2)
        self._pattern_entry.bind("<Return>", self._on_lookup)

        self._lookup_btn = tk.Button(
            lookup_row, text="Search", command=self._on_lookup, width=8,
            bg=t["accent"], fg=t["accent_fg"],
            font=FONT, relief=tk.FLAT, bd=0, padx=12, pady=4,
        )
        self._lookup_btn.pack(side=tk.LEFT)

        # Entity results area
        self._entity_results = tk.Text(
            self, height=8, wrap=tk.WORD, state=tk.DISABLED,
            font=FONT_SMALL, bg=t["input_bg"], fg=t["input_fg"],
            relief=tk.FLAT, bd=1,
        )
        self._entity_results.pack(fill=tk.BOTH, expand=True, pady=(4, 12))

        # -- Section 3: Relationship search --
        rel_label = tk.Label(
            self, text="Relationship Search", font=FONT_BOLD,
            bg=t["panel_bg"], fg=t["fg"], anchor=tk.W,
        )
        rel_label.pack(fill=tk.X, pady=(0, 4))

        rel_row = tk.Frame(self, bg=t["panel_bg"])
        rel_row.pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            rel_row, text="Entity:", bg=t["panel_bg"],
            fg=t["fg"], font=FONT,
        ).pack(side=tk.LEFT)

        self._rel_entry = tk.Entry(
            rel_row, font=FONT, bg=t["input_bg"], fg=t["input_fg"],
            insertbackground=t["fg"], relief=tk.FLAT, bd=2, width=24,
        )
        self._rel_entry.pack(side=tk.LEFT, padx=(4, 8), ipady=2)
        self._rel_entry.bind("<Return>", self._on_rel_search)

        self._rel_btn = tk.Button(
            rel_row, text="Find Relations", command=self._on_rel_search,
            width=14, bg=t["accent"], fg=t["accent_fg"],
            font=FONT, relief=tk.FLAT, bd=0, padx=12, pady=4,
        )
        self._rel_btn.pack(side=tk.LEFT)

        # Relationship results
        self._rel_results = tk.Text(
            self, height=8, wrap=tk.WORD, state=tk.DISABLED,
            font=FONT_SMALL, bg=t["input_bg"], fg=t["input_fg"],
            relief=tk.FLAT, bd=1,
        )
        self._rel_results.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def _refresh_summary(self):
        """Load entity type summary and relationship predicate summary."""
        t = current_theme()
        entity_store = self._model.entity_store if self._model else None
        rel_store = self._model.relationship_store if self._model else None

        if entity_store is None:
            self._set_text(self._summary_text, "Entity store not available.")
            return

        def _load():
            try:
                type_summary = entity_store.entity_type_summary()
                total_entities = entity_store.count_entities()
                total_tables = entity_store.count_table_rows()

                rel_count = 0
                pred_summary = {}
                if rel_store:
                    rel_count = rel_store.count()
                    pred_summary = rel_store.predicate_summary()

                lines = ["Total entities: {:,}".format(total_entities)]
                lines.append("Total table rows: {:,}".format(total_tables))
                lines.append("Total relationships: {:,}".format(rel_count))
                lines.append("")

                if type_summary:
                    lines.append("-- Entity Types --")
                    for etype, count in sorted(
                        type_summary.items(), key=lambda x: -x[1]
                    ):
                        lines.append("  {:<16s} {:>6,}".format(etype, count))

                if pred_summary:
                    lines.append("")
                    lines.append("-- Relationship Predicates --")
                    for pred, count in sorted(
                        pred_summary.items(), key=lambda x: -x[1]
                    ):
                        lines.append("  {:<24s} {:>6,}".format(pred, count))

                text = "\n".join(lines)

                # Update type dropdown
                types = ["(any)"] + sorted(type_summary.keys())

                safe_after(self, 0, lambda: self._apply_summary(text, types))

            except Exception as exc:
                safe_after(
                    self, 0,
                    lambda: self._set_text(
                        self._summary_text,
                        "Error loading summary: {}".format(exc),
                    ),
                )

        threading.Thread(target=_load, daemon=True).start()

    def _apply_summary(self, text, types):
        """Apply summary text and type list on the main thread."""
        self._set_text(self._summary_text, text)
        self._type_combo.config(values=types)

    # ------------------------------------------------------------------
    # Entity lookup
    # ------------------------------------------------------------------

    def _on_lookup(self, event=None):
        """Search entities by type + text pattern."""
        entity_store = self._model.entity_store if self._model else None
        if entity_store is None:
            self._set_text(self._entity_results, "Entity store not available.")
            return

        etype = self._type_var.get()
        pattern = self._pattern_entry.get().strip()
        if etype == "(any)":
            etype = None
        text_pattern = "%{}%".format(pattern) if pattern else None

        def _search():
            try:
                results = entity_store.lookup_entities(
                    entity_type=etype,
                    text_pattern=text_pattern,
                    limit=50,
                )
                if not results:
                    safe_after(self, 0, lambda: self._set_text(
                        self._entity_results, "No entities found.",
                    ))
                    return

                lines = []
                for r in results:
                    lines.append(
                        "[{:.0%}] {}: {} -- {}".format(
                            r.confidence, r.entity_type, r.text,
                            r.source_path,
                        )
                    )
                    if r.context:
                        lines.append("       {}".format(r.context[:120]))
                    lines.append("")

                safe_after(self, 0, lambda: self._set_text(
                    self._entity_results, "\n".join(lines),
                ))
            except Exception as exc:
                safe_after(self, 0, lambda: self._set_text(
                    self._entity_results,
                    "Search error: {}".format(exc),
                ))

        threading.Thread(target=_search, daemon=True).start()

    # ------------------------------------------------------------------
    # Relationship search
    # ------------------------------------------------------------------

    def _on_rel_search(self, event=None):
        """Search relationships by entity text."""
        rel_store = self._model.relationship_store if self._model else None
        if rel_store is None:
            self._set_text(self._rel_results, "Relationship store not available.")
            return

        text = self._rel_entry.get().strip()
        if not text:
            self._set_text(self._rel_results, "Enter an entity name to search.")
            return

        def _search():
            try:
                results = rel_store.find_related(text, limit=50)
                if not results:
                    safe_after(self, 0, lambda: self._set_text(
                        self._rel_results, "No relationships found.",
                    ))
                    return

                lines = []
                for r in results:
                    lines.append(
                        "[{:.0%}] ({}) {} --[{}]--> ({}) {}".format(
                            r.confidence,
                            r.subject_type, r.subject_text,
                            r.predicate,
                            r.object_type, r.object_text,
                        )
                    )
                    if r.context:
                        lines.append("       {}".format(r.context[:120]))
                    lines.append("")

                safe_after(self, 0, lambda: self._set_text(
                    self._rel_results, "\n".join(lines),
                ))
            except Exception as exc:
                safe_after(self, 0, lambda: self._set_text(
                    self._rel_results,
                    "Search error: {}".format(exc),
                ))

        threading.Thread(target=_search, daemon=True).start()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _set_text(widget, text):
        """Set text in a disabled tk.Text widget."""
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def apply_theme(self, t):
        """Re-apply theme colors."""
        self.configure(bg=t["panel_bg"], fg=t["accent"])
        for child in self.winfo_children():
            if isinstance(child, tk.Frame):
                try:
                    child.configure(bg=t["panel_bg"])
                except Exception:
                    pass
            elif isinstance(child, tk.Label):
                child.configure(bg=t["panel_bg"])
            elif isinstance(child, tk.Text):
                child.configure(bg=t["input_bg"], fg=t["input_fg"])
