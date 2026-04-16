"""V2 GUI panel helpers for the button smash harness.

Provides a get_tab_specs() function that returns tab info compatible
with the harness's panel switching logic, and a switch_tab() function
that works with V2's ttk.Notebook architecture.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import List, Optional


@dataclass
class TabSpec:
    key: str       # tab label (e.g. "Overview", "RAGAS")
    index: int     # notebook tab index
    notebook: ttk.Notebook


def get_tab_specs(app: tk.Tk | None = None) -> List[TabSpec]:
    """Discover all ttk.Notebook tabs in the given app window."""
    if app is None:
        return []
    specs: List[TabSpec] = []
    for nb in _find_notebooks(app):
        for idx in range(nb.index("end")):
            label = nb.tab(idx, "text")
            specs.append(TabSpec(key=label, index=idx, notebook=nb))
    return specs


def switch_tab(app: tk.Tk, key: str) -> bool:
    """Switch to the named tab. Returns True if found."""
    for spec in get_tab_specs(app):
        if spec.key == key:
            spec.notebook.select(spec.index)
            return True
    return False


def _find_notebooks(widget: tk.Widget) -> List[ttk.Notebook]:
    """Recursively find all Notebook widgets."""
    found: List[ttk.Notebook] = []
    if isinstance(widget, ttk.Notebook):
        found.append(widget)
    for child in widget.winfo_children():
        found.extend(_find_notebooks(child))
    return found
