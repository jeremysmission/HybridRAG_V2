"""Panel registry. It defines which screens exist and how the app imports them on demand."""
# ============================================================================
# HybridRAG V2 -- Panel Registry (src/gui/panels/panel_registry.py)
# ============================================================================
# Single source of truth for panel order and identity.
# V2 simplified: query, entity, settings only.
# No data panel, no mode toggle, no role selector.
# ============================================================================

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PanelSpec:
    """Immutable descriptor for a GUI panel.

    key:   Internal routing key (must be unique across registry).
    label: Human-readable tab label shown in NavBar.
    module_path: Dotted import path.
    class_name:  Class or factory to import from module_path.
    """
    key: str
    label: str
    module_path: str
    class_name: str


def _import_attr(module_path: str, attr: str) -> Any:
    """Import attr from module_path lazily."""
    mod = __import__(module_path, fromlist=[attr])
    return getattr(mod, attr)


# ---------------------------------------------------------------
# REGISTRY -- V2 panels: Query, Entity, Settings
# ---------------------------------------------------------------

_PANEL_DEFS = [
    {
        "key": "query",
        "label": "Query",
        "module": "src.gui.panels.query_panel",
        "cls": "QueryPanel",
    },
    {
        "key": "history",
        "label": "History",
        "module": "src.gui.panels.history_panel",
        "cls": "HistoryPanel",
    },
    {
        "key": "entity",
        "label": "Entities",
        "module": "src.gui.panels.entity_panel",
        "cls": "EntityPanel",
    },
    {
        "key": "regression",
        "label": "Regression",
        "module": "src.gui.panels.regression_panel",
        "cls": "RegressionPanel",
    },
    {
        "key": "settings",
        "label": "Settings",
        "module": "src.gui.panels.settings_panel",
        "cls": "SettingsPanel",
    },
]


def get_panels() -> list[PanelSpec]:
    """Return the ordered list of available panels."""
    panels: list[PanelSpec] = []
    seen_keys: set = set()

    for defn in _PANEL_DEFS:
        key = defn["key"]
        if key in seen_keys:
            logger.warning("Duplicate panel key '%s' -- skipped", key)
            continue
        panels.append(
            PanelSpec(key, defn["label"], defn["module"], defn["cls"])
        )
        seen_keys.add(key)

    return panels


def get_panel(key: str) -> Optional[PanelSpec]:
    """Return the PanelSpec for key, or None if not registered."""
    for p in get_panels():
        if p.key == key:
            return p
    return None
