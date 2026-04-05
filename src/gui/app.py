# ============================================================================
# HybridRAG V2 -- Main GUI Application (src/gui/app.py)
# ============================================================================
# Single-window coordinator that owns the lifecycle of every panel.
# Handles backend initialization, config propagation, and view switching.
#
# Layout:
#   1. NavBar -- tabs built from panel_registry (query, entity, settings)
#   2. Content Frame (swaps views via pack_forget/pack, <1ms)
#   3. Status bar (chunks, entities, LLM, query path)
#
# No mode toggle, no role selector, no theme toggle -- V2 is single-mode
# dark theme only.
# ============================================================================

import tkinter as tk
import logging
import threading

from src.gui.panels.nav_bar import NavBar
from src.gui.panels.status_bar import StatusBar
from src.gui.panels.panel_registry import get_panels, _import_attr
from src.gui.theme import (
    DARK, FONT, FONT_BOLD, FONT_TITLE,
    current_theme, apply_ttk_styles,
)
from src.gui.helpers.safe_after import drain_ui_queue

logger = logging.getLogger(__name__)


class HybridRAGApp(tk.Tk):
    """Main application window for HybridRAG V2.

    Owns all panels and coordinates boot state, view switching,
    and backend references. Uses lazy view switching -- only the
    Query view is built at startup; other views built on first access.
    """

    def __init__(self, model=None, config=None):
        super().__init__()

        self.title("HybridRAG V2")
        self.geometry("900x780")
        self.minsize(700, 400)

        # Briefly bring the window to front on launch, then release topmost.
        try:
            self.attributes("-topmost", True)
            self.after(450, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

        # Store references
        self._model = model
        self._config = config
        self._views = {}
        self._current_view = None

        # Apply theme
        self._theme = current_theme()
        apply_ttk_styles(self._theme)
        self.configure(bg=self._theme["bg"])

        # Build UI structure
        self._build_nav_bar()
        self._build_status_bar()
        self._build_content_frame()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Heartbeat: drain the safe_after fallback queue every 50ms
        self._drain_pump()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_nav_bar(self):
        """Build the navigation bar at the top."""
        self.nav_bar = NavBar(self, on_switch=self.show_view, theme=self._theme)
        self.nav_bar.pack(fill=tk.X)

    def _build_status_bar(self):
        """Build the status bar at the bottom."""
        self.status_bar = StatusBar(self, model=self._model)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_content_frame(self):
        """Build the main content area and show the query panel."""
        self._content_frame = tk.Frame(self, bg=self._theme["bg"])
        self._content_frame.pack(fill=tk.BOTH, expand=True)

        # Build and show the query panel immediately
        self._build_query_view()
        self.show_view("query")

    def _build_query_view(self):
        """Build the query panel (always built at startup)."""
        from src.gui.panels.query_panel import QueryPanel

        panel = QueryPanel(self._content_frame, model=self._model)
        self._views["query"] = panel
        self.query_panel = panel

    def _build_view(self, name):
        """Lazy-build a view panel by registry key."""
        if name in self._views:
            return self._views[name]

        panels = {p.key: p for p in get_panels()}
        spec = panels.get(name)
        if spec is None:
            logger.warning("Unknown view: %s", name)
            return None

        try:
            cls = _import_attr(spec.module_path, spec.class_name)
            panel = cls(self._content_frame, model=self._model)
            self._views[name] = panel
            return panel
        except Exception as exc:
            logger.error("Failed to build view '%s': %s", name, exc)
            return None

    # ------------------------------------------------------------------
    # View switching
    # ------------------------------------------------------------------

    def show_view(self, name):
        """Switch to the named view panel."""
        # Build lazily if needed
        if name not in self._views:
            panel = self._build_view(name)
            if panel is None:
                return

        # Hide current view
        if self._current_view and self._current_view in self._views:
            self._views[self._current_view].pack_forget()

        # Show requested view
        self._views[name].pack(fill=tk.BOTH, expand=True)
        self._current_view = name
        self.nav_bar.select(name)

    # ------------------------------------------------------------------
    # safe_after drain pump
    # ------------------------------------------------------------------

    def _drain_pump(self):
        """Drain the safe_after queue every 50ms on the main thread."""
        try:
            drain_ui_queue()
        except Exception:
            pass
        self.after(50, self._drain_pump)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _on_close(self):
        """Handle window close."""
        logger.info("GUI closing...")
        try:
            self.status_bar.stop()
        except Exception:
            pass
        self.destroy()

    def set_model(self, model):
        """Attach or replace the GUIModel after background init."""
        self._model = model
        self.status_bar.set_model(model)

        # Update query panel if already built
        if "query" in self._views:
            qp = self._views["query"]
            qp._model = model
            qp.set_ready(model.pipeline is not None)

        # Force status bar refresh
        self.status_bar.force_refresh()
