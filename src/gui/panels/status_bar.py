"""Status bar. It gives a constant at-a-glance summary of system readiness at the bottom of the window."""
# ============================================================================
# HybridRAG V2 -- Status Bar (src/gui/panels/status_bar.py)
# ============================================================================
# Bottom status bar showing: chunks loaded, FTS readiness, entities loaded,
# LLM status, and query path of last query. Refreshes every 15 seconds.
# ============================================================================

import tkinter as tk
import threading
import logging

from src.gui.theme import current_theme, FONT

logger = logging.getLogger(__name__)


class StatusBar(tk.Frame):
    """Bottom status bar with system health indicators.

    Displays:
      - Chunks loaded (from LanceDB)
      - FTS readiness for the configured LanceDB store
      - Entities loaded (from EntityStore)
      - LLM status (available / not configured)
      - Last query path (SEMANTIC/ENTITY/AGGREGATE/TABULAR/COMPLEX)
    """

    REFRESH_MS = 15000  # 15 seconds

    def __init__(self, parent, model=None):
        t = current_theme()
        super().__init__(parent, relief=tk.FLAT, bd=1, bg=t["panel_bg"])
        self._model = model
        self._stop_event = threading.Event()
        self._refresh_timer_id = None
        self._last_query_path = ""

        self._build_widgets(t)
        self._schedule_refresh()

    def _build_widgets(self, t):
        """Build all status indicator widgets."""
        # -- Chunks indicator --
        self.chunks_label = tk.Label(
            self, text="Chunks: --", anchor=tk.W,
            padx=8, pady=4, bg=t["panel_bg"], fg=t["fg"], font=FONT,
        )
        self.chunks_label.pack(side=tk.LEFT)

        self._sep1 = tk.Frame(self, width=1, bg=t["separator"])
        self._sep1.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

        # -- FTS indicator --
        self.fts_label = tk.Label(
            self, text="FTS: --", anchor=tk.W,
            padx=8, pady=4, bg=t["panel_bg"], fg=t["gray"], font=FONT,
        )
        self.fts_label.pack(side=tk.LEFT)

        self._sep_fts = tk.Frame(self, width=1, bg=t["separator"])
        self._sep_fts.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

        # -- Entities indicator --
        self.entities_label = tk.Label(
            self, text="Entities: --", anchor=tk.W,
            padx=8, pady=4, bg=t["panel_bg"], fg=t["fg"], font=FONT,
        )
        self.entities_label.pack(side=tk.LEFT)

        self._sep2 = tk.Frame(self, width=1, bg=t["separator"])
        self._sep2.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

        # -- LLM status indicator --
        self.llm_label = tk.Label(
            self, text="LLM: checking...", anchor=tk.W,
            padx=8, pady=4, bg=t["panel_bg"], fg=t["gray"], font=FONT,
        )
        self.llm_label.pack(side=tk.LEFT)

        self._sep3 = tk.Frame(self, width=1, bg=t["separator"])
        self._sep3.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

        # -- Query path indicator (right-aligned) --
        self.path_label = tk.Label(
            self, text="Path: --", anchor=tk.E,
            padx=8, pady=4, bg=t["panel_bg"], fg=t["gray"], font=FONT,
        )
        self.path_label.pack(side=tk.RIGHT)

    def set_model(self, model):
        """Attach or replace the GUIModel reference."""
        self._model = model
        self._refresh_status()

    def set_query_path(self, path_name: str):
        """Update the last query path display."""
        t = current_theme()
        self._last_query_path = path_name

        # Color-code the query path
        color_map = {
            "SEMANTIC": t["accent"],
            "ENTITY": t["green"],
            "AGGREGATE": t["orange"],
            "TABULAR": t["orange"],
            "COMPLEX": t["red"],
        }
        color = color_map.get(path_name, t["fg"])
        self.path_label.config(text="Path: {}".format(path_name), fg=color)

    def _schedule_refresh(self):
        """Schedule next status refresh."""
        if not self._stop_event.is_set():
            self._refresh_status()
            self._refresh_timer_id = self.after(
                self.REFRESH_MS, self._schedule_refresh
            )

    def _refresh_status(self):
        """Update all status indicators from current model state."""
        t = current_theme()
        try:
            if self._model is None:
                self.chunks_label.config(text="Chunks: --", fg=t["gray"])
                self.fts_label.config(text="FTS: --", fg=t["gray"])
                self.entities_label.config(text="Entities: --", fg=t["gray"])
                self.llm_label.config(text="LLM: not initialized", fg=t["gray"])
                return

            # Chunks
            count = self._model.chunk_count
            self.chunks_label.config(
                text="Chunks: {:,}".format(count),
                fg=t["green"] if count > 0 else t["gray"],
            )

            # FTS readiness on the configured store
            if self._model.fts_ready is True:
                self.fts_label.config(text="FTS: ready", fg=t["green"])
            elif self._model.fts_ready is False:
                if getattr(self._model, "fts_state", "") == "index_present":
                    self.fts_label.config(text="FTS: present", fg=t["orange"])
                else:
                    self.fts_label.config(text="FTS: missing", fg=t["red"])
            else:
                self.fts_label.config(text="FTS: checking...", fg=t["gray"])

            # Entities + health warning when stores are empty
            ent_count = self._model.entity_count
            rel_count = self._model.relationship_count
            tbl_count = getattr(self._model, "table_count", 0) or 0
            if rel_count == 0 and tbl_count == 0:
                self.entities_label.config(
                    text="Entities: {:,} | Rels: 0 | Tables: 0 [EMPTY - run extraction]".format(ent_count),
                    fg=t["red"],
                )
            elif rel_count == 0:
                self.entities_label.config(
                    text="Entities: {:,} | Rels: 0 [no relationships]".format(ent_count),
                    fg=t["orange"],
                )
            else:
                self.entities_label.config(
                    text="Entities: {:,} | Rels: {:,}".format(ent_count, rel_count),
                    fg=t["green"] if ent_count > 0 else t["gray"],
                )

            # LLM
            if self._model.llm_available:
                self.llm_label.config(text="LLM: available", fg=t["green"])
            else:
                self.llm_label.config(text="LLM: not configured", fg=t["orange"])

        except Exception as e:
            logger.debug("Status bar refresh error: %s", e)

    def apply_theme(self, t):
        """Re-apply theme colors to all widgets."""
        self.configure(bg=t["panel_bg"])
        for w in (self.chunks_label, self.fts_label, self.entities_label,
                  self.llm_label, self.path_label):
            w.configure(bg=t["panel_bg"])
        for sep in (self._sep1, self._sep_fts, self._sep2, self._sep3):
            sep.configure(bg=t["separator"])
        self._refresh_status()

    def force_refresh(self):
        """Immediately refresh all indicators."""
        if self._model:
            self._model.refresh_counts()
        self._refresh_status()

    def stop(self):
        """Stop the periodic refresh timer."""
        self._stop_event.set()
        if self._refresh_timer_id is not None:
            try:
                self.after_cancel(self._refresh_timer_id)
            except Exception:
                pass
            self._refresh_timer_id = None
