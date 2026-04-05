# ============================================================================
# HybridRAG V2 -- ScrollableFrame (src/gui/scrollable.py)
# ============================================================================
# Reusable canvas+scrollbar wrapper for scrollable content.
# Child widgets go inside .inner (the frame embedded in the canvas).
# Mousewheel binds on enter/leave; inner frame width syncs with canvas.
#
# Usage:
#       sf = ScrollableFrame(parent, bg=t["bg"])
#       sf.pack(fill=BOTH, expand=True)
#       tk.Label(sf.inner, text="Hello").pack()
# ============================================================================

import tkinter as tk
from tkinter import ttk


class ScrollableFrame(tk.Frame):
    """Canvas + vertical Scrollbar with mousewheel support.

    All child widgets should be placed inside ``self.inner``.
    The inner frame width automatically matches the canvas width so
    pack(fill=X) children expand correctly.
    """

    # Class-level: which instance currently owns mousewheel events.
    _active_instance = None
    _global_bound = False

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)

        bg = kw.get("bg", kw.get("background", ""))

        self._canvas = tk.Canvas(self, highlightthickness=0)
        if bg:
            self._canvas.configure(bg=bg)

        self._scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self._canvas.yview)

        self.inner = tk.Frame(self._canvas)
        if bg:
            self.inner.configure(bg=bg)

        self.inner.bind(
            "<Configure>",
            lambda e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")))

        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self.inner, anchor="nw", tags="inner")

        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Keep inner frame width matched to canvas
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        # Mousewheel scrolling: claim/release on enter/leave
        self._canvas.bind("<Enter>", self._claim_mousewheel)
        self._canvas.bind("<Leave>", self._release_mousewheel)

    def _on_canvas_resize(self, event):
        """Sync inner frame width to canvas width."""
        self._canvas.itemconfig("inner", width=event.width)
        inner_h = self.inner.winfo_reqheight()
        if inner_h < event.height:
            self._canvas.itemconfig("inner", height=event.height)
        else:
            self._canvas.itemconfig("inner", height=inner_h)

    def _claim_mousewheel(self, event):
        """Mark this instance as the active scroll target."""
        ScrollableFrame._active_instance = self
        if not ScrollableFrame._global_bound:
            self._canvas.bind_all("<MouseWheel>", ScrollableFrame._route_mousewheel)
            ScrollableFrame._global_bound = True

    def _release_mousewheel(self, event):
        """Release scroll ownership when mouse leaves."""
        if ScrollableFrame._active_instance is self:
            ScrollableFrame._active_instance = None

    @staticmethod
    def _route_mousewheel(event):
        """Route mousewheel to whichever ScrollableFrame the mouse is over."""
        target = ScrollableFrame._active_instance
        if target is not None:
            target._canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def destroy(self):
        """Clear active instance ref before destroying the widget."""
        if ScrollableFrame._active_instance is self:
            ScrollableFrame._active_instance = None
        super().destroy()

    def apply_theme(self, t):
        """Re-apply theme colors to the canvas and inner frame."""
        bg = t.get("bg", "")
        self.configure(bg=bg)
        self._canvas.configure(bg=bg)
        self.inner.configure(bg=bg)
